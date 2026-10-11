"""Render a pixel-art banner from Retro Trivia's launch splash.

Reuses the splash's own neon letter shapes, tube colours, spotlit question mark,
stage floor, marquee bulbs and lower third, but composes them on a real pixel
canvas (320x160, scaled 4x to 1280x640, GitHub's social-preview size) instead
of half-block terminal cells.

usage: python art/render_banner.py retro_trivia.py art/banner.png [scale]

No dependencies beyond the standard library; it writes the PNG itself.
"""
import importlib.util
import math
import struct
import sys
import zlib

src, out_path = sys.argv[1], sys.argv[2]
SCALE = int(sys.argv[3]) if len(sys.argv) > 3 else 4
spec = importlib.util.spec_from_file_location("retro_trivia", src)
rt = importlib.util.module_from_spec(spec)
sys.modules["retro_trivia"] = rt
spec.loader.exec_module(rt)

W, H = 320, 160


def rgb(color):
    """A splash colour is (rgb, xterm-256 index); take the rgb."""
    return color[0]


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def shade(c, f):
    return tuple(max(0, min(255, round(v * f))) for v in c)


BG_TOP, BG_BOTTOM = (8, 3, 16), (22, 8, 32)
img = [[mix(BG_TOP, BG_BOTTOM, y / (H - 1)) for _ in range(W)] for y in range(H)]
BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def put(x, y, c):
    if 0 <= x < W and 0 <= y < H and c is not None:
        img[y][x] = c


def blend(x, y, c, a):
    if 0 <= x < W and 0 <= y < H:
        img[y][x] = mix(img[y][x], c, a)


def dither(x, y, c, a, levels=4):
    """Blend in steps, ordered-dithered, so soft light stays pixel art."""
    steps = a * levels
    whole = int(steps)
    if steps - whole > (BAYER[y % 4][x % 4] + 0.5) / 16:
        whole += 1
    if whole:
        blend(x, y, c, min(1.0, whole / levels))


F3 = {k: "".join(v.split()) for k, v in {
    "A": ".#. #.# ### #.# #.#", "B": "##. #.# ##. #.# ##.", "C": "### #.. #.. #.. ###",
    "D": "##. #.# #.# #.# ##.", "E": "### #.. ##. #.. ###", "F": "### #.. ##. #.. #..",
    "G": "### #.. #.# #.# ###", "H": "#.# #.# ### #.# #.#", "I": "### .#. .#. .#. ###",
    "L": "#.. #.. #.. #.. ###", "M": "#.# ### ### #.# #.#", "N": "##. #.# #.# #.# #.#",
    "O": "### #.# #.# #.# ###", "P": "### #.# ### #.. #..", "R": "##. #.# ##. #.# #.#",
    "S": "### #.. ### ..# ###", "T": "### .#. .#. .#. .#.", "U": "#.# #.# #.# #.# ###",
    "V": "#.# #.# #.# .#. .#.", "Y": "#.# #.# .#. .#. .#.", "'": ".#. .#. ... ... ...",
    " ": "... ... ... ... ...",
}.items()}


def text(x, y, s, color):
    for i, ch in enumerate(s):
        g = F3[ch]
        for r in range(5):
            for c in range(3):
                if g[r * 3 + c] == "#":
                    put(x + i * 4 + c, y + r, color)


def text_width(s):
    return len(s) * 4 - 1


# -- the marquee: a ring of bulbs, every third one lit ------------------------
bulbs = ([(x, 5) for x in range(6, W - 4, 8)] + [(W - 6, y) for y in range(13, H - 8, 8)]
         + [(x, H - 6) for x in range(W - 6, 3, -8)] + [(5, y) for y in range(H - 14, 8, -8)])
for i, (bx, by) in enumerate(bulbs):
    lit = i % 3 == 0
    core = rgb(rt._BULB_LIT) if lit else shade(rgb(rt._BULB_DIM), 0.75)
    if lit:
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                d = math.hypot(dx, dy)
                if 1.5 < d <= 4.2:
                    dither(bx + dx, by + dy, (255, 214, 120), 0.85 * (1 - d / 4.4))
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        put(bx + dx, by + dy, core)
    if lit:
        put(bx - 1, by - 1, mix(core, (255, 255, 255), 0.6))

# -- the spotlight, the question mark and the pool on the boards --------------
cx = W // 2
beam_top, beam_bottom = 72, 128
for y in range(beam_top, beam_bottom):
    depth = (y - beam_top) / (beam_bottom - beam_top)
    half = 7 + depth * 44
    for x in range(int(cx - half), int(cx + half) + 1):
        glow = max(0.0, 1 - abs(x - cx) / half)
        factor = 0.22 + 0.78 * glow * (1 - 0.4 * depth)
        dither(x, y, shade(rgb(rt._CONE), 0.6 + 0.6 * factor), 0.62 * factor)
for x in range(cx - 52, cx + 53):
    for y in range(126, 133):
        d = math.hypot((x - cx) / 52, (y - 129) / 3.6)
        if d <= 1:
            band = min(len(rt._FLOOR) - 1, int(d * len(rt._FLOOR)))
            dither(x, y, rgb(rt._FLOOR[band]), 0.95 - 0.35 * d)

art = rt._QUESTION_ART
QX, QY = 3, 3  # one character cell is 3 px wide; each half block 3 px tall
qw, qh = len(art[0]) * QX, len(art) * 2 * QY
qx0, qy0 = cx - qw // 2, 80
for r, line in enumerate(art):
    color = rgb(rt._QUESTION_RAMP[min(r, len(rt._QUESTION_RAMP) - 1)])
    for c, ch in enumerate(line):
        halves = {"█": (1, 1), "▀": (1, 0), "▄": (0, 1)}.get(ch, (0, 0))
        for half, on in enumerate(halves):
            if on:
                for dy in range(QY):
                    for dx in range(QX):
                        put(qx0 + c * QX + dx, qy0 + (r * 2 + half) * QY + dy, color)

# -- the sign: RETRO TRIVIA in neon tubes, each throwing its own glow ----------
letters, col = [], 0
for word_index, word in enumerate(("RETRO", "TRIVIA")):
    if word_index:
        col += 2  # the splash's three-column gap between words, less the letter gap
    for ch in word:
        glyph = rt._BIG_FONT[ch]
        letters.append((col, glyph))
        col += len(glyph[0]) + 1
cols = col - 1
LX, LY = 3, 3
logo_w, logo_h = cols * LX, 5 * 2 * LY
lx0, ly0 = cx - logo_w // 2, 25
lit = {}
for index, (c0, glyph) in enumerate(letters):
    tube = rgb(rt._NEON[index * (len(rt._NEON) - 1) // (len(letters) - 1)])
    for r, line in enumerate(glyph):
        for c, ch in enumerate(line):
            halves = {"█": (1, 1), "▀": (1, 0), "▄": (0, 1)}.get(ch, (0, 0))
            for half, on in enumerate(halves):
                if not on:
                    continue
                for dy in range(LY):
                    for dx in range(LX):
                        x = lx0 + (c0 + c) * LX + dx
                        y = ly0 + (r * 2 + half) * LY + dy
                        depth = (y - ly0) / (logo_h - 1)
                        lit[(x, y)] = (shade(tube, 1.18 - 0.42 * depth), tube)
# A bloom in each tube's own hue, then the hue-dark shadow, then the tubes.
bloom = {}
for (x, y), (_, tube) in lit.items():
    for dy in range(-5, 6):
        for dx in range(-5, 6):
            d = math.hypot(dx, dy)
            if d <= 5.2:
                key = (x + dx, y + dy)
                weight = (1 - d / 5.4) ** 2
                acc = bloom.setdefault(key, [0.0, 0.0, 0.0, 0.0])
                for i in range(3):
                    acc[i] += tube[i] * weight
                acc[3] += weight
for (x, y), (r_, g_, b_, w_) in bloom.items():
    if (x, y) not in lit and w_ > 0:
        dither(x, y, (round(r_ / w_), round(g_ / w_), round(b_ / w_)), min(0.5, w_ * 0.045))
for (x, y), (_, tube) in lit.items():
    if (x + 2, y + 2) not in lit:
        put(x + 2, y + 2, shade(tube, 0.3))
for (x, y), (color, _) in lit.items():
    put(x, y, color)

# -- the header, the tagline and the lower third ------------------------------
header = "LIVE FROM YOUR BBS"
hx = cx - text_width(header) // 2
text(hx, 14, header, rgb(rt._HEADER))
for sx in (hx - 9, hx + text_width(header) + 5):  # the header's two stars
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (0, 2), (0, -2), (2, 0), (-2, 0)):
        put(sx + 1 + dx, 16 + dy, rgb(rt._HEADER_STAR))
tagline = "THE CLASSIC BBS AND RETRO COMPUTING CHALLENGE"
text(cx - text_width(tagline) // 2, 62, tagline, rgb(rt._TAGLINE))

label, name = " TONIGHT'S CONTESTANT ", " YOU "
lw, nw = text_width(label) + 2, text_width(name) + 2
lt_x = cx - (lw + nw + 12) // 2
for y in range(138, 147):
    for x in range(lt_x, lt_x + lw):
        put(x, y, rgb(rt._LABEL_BG))
    for x in range(lt_x + lw, lt_x + lw + nw):
        put(x, y, rgb(rt._HANDLE_BG))
    for i, color in enumerate(rt._TAIL):  # the tail fades away into the stage
        for x in range(lt_x + lw + nw + i * 4, lt_x + lw + nw + i * 4 + 4):
            dither(x, y, rgb(color), 1 - i * 0.28)
text(lt_x + 1, 140, label, rgb(rt._LABEL_FG))
text(lt_x + lw + 1, 140, name, rgb(rt._HANDLE_FG))

# -- sparkles in the dark around the show -------------------------------------
seed = zlib.crc32(b"Retro Trivia") or 1
placed = 0
while placed < 16:
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    x = 14 + seed % (W - 28)
    seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    y = 12 + seed % (H - 24)
    if 20 <= y <= 70 and abs(x - cx) < 118 or 70 <= y <= 150 and abs(x - cx) < 64:
        continue  # keep clear of the sign, the tagline and the stage
    color = rgb(rt._SPARKLE[placed % len(rt._SPARKLE)])
    put(x, y, color)
    if placed % 3 == 0:
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            blend(x + dx, y + dy, color, 0.6)
    placed += 1

# -- write a PNG with nothing but the standard library -------------------------
rows = []
for y in range(H * SCALE):
    src_row = img[y // SCALE]
    line = bytearray(b"\x00")
    for x in range(W * SCALE):
        line.extend(bytes(src_row[x // SCALE]))
    rows.append(bytes(line))


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W * SCALE, H * SCALE, 8, 2, 0, 0, 0))
png += chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
with open(out_path, "wb") as f:
    f.write(png)
print(out_path, W * SCALE, H * SCALE)
