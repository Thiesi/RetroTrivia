"""Render actual CP437 output for review (dev tools: pip install pillow pyte).

Usage: python art/render_terminal_preview.py [--font /path/to/mono.ttf]
"""

import argparse
import contextlib
import importlib.util
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import pyte


ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", default=("C:/Windows/Fonts/consola.ttf" if Path("C:/Windows").exists()
                                         else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("retro_trivia_preview", ROOT / "retro_trivia.py")
    rt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rt)
    rt._OUTPUT_ENCODING = "cp437"
    p = rt.Palette(False, basic=True)
    info = {"handle": "Jäger", "node_name": "Classic BBS"}
    rt.read_key = lambda: "A"
    actions = [
        ("Launch splash", lambda: [rt.out(frame) for frame in rt.splash_frames(p, info, 80, 24)]),
        ("Welcome", lambda: rt.draw_title(p, info)),
        ("Question", lambda: rt.ask_question(p, 1, 5, *rt.QUESTIONS[0][:2])),
        ("Final score", lambda: rt.draw_final_score(p, 4, 5, info)),
    ]
    font = ImageFont.truetype(args.font, 16)
    cell_w, cell_h = round(font.getlength("M")), 20
    colors = {"black": "000000", "red": "aa0000", "green": "00aa00", "brown": "aa5500",
              "blue": "0000aa", "magenta": "aa00aa", "cyan": "00aaaa", "white": "aaaaaa"}
    bright = dict(zip(colors, ["555555", "ff5555", "55ff55", "ffff55",
                               "5555ff", "ff55ff", "55ffff", "ffffff"]))
    panel_w, panel_h = 80 * cell_w + 24, 30 * cell_h + 48
    image = Image.new("RGB", (panel_w * 2, panel_h * 2), "#161616")
    draw = ImageDraw.Draw(image)
    for index, (label, action) in enumerate(actions):
        raw = io.BytesIO()
        terminal = io.TextIOWrapper(raw, encoding="cp437", newline="")
        with contextlib.redirect_stdout(terminal):
            action()
        screen = pyte.Screen(80, 40)
        pyte.Stream(screen).feed(raw.getvalue().decode("cp437"))
        left, top = (index % 2) * panel_w + 12, (index // 2) * panel_h + 36
        draw.text((left, top - 26), label + " / CP437 / 16 colours", font=font, fill="#dddddd")
        for row in range(30):
            for col in range(80):
                char = screen.buffer[row][col]
                fg = (bright if char.bold else colors).get(char.fg, "aaaaaa")
                bg = colors.get(char.bg, "000000")
                if char.reverse:
                    fg, bg = bg, fg
                x, y = left + col * cell_w, top + row * cell_h
                cell = Image.new("RGB", (cell_w, cell_h), "#" + bg)
                if char.data.strip():
                    ImageDraw.Draw(cell).text((0, 0), char.data, font=font, fill="#" + fg)
                image.paste(cell, (x, y))
    target = ROOT / "art" / "cp437-preview.png"
    image.save(target)
    print(target)


if __name__ == "__main__":
    main()
