# Engineering notes

Durable implementation knowledge about Retro Trivia: invariants and traps a
change to the door has to respect. Notes from before the move out of NetBBS
(October 2026) came from its worklog; issue numbers in them refer to
[Thiesi/NetBBS](https://github.com/Thiesi/NetBBS) issues.

## Row wrapping

Retro Trivia wraps a row twice, at two different layers, and only the outer one
is a safety net. `_box_line` pads a short row and returns a long one unchanged,
so it alone would push a border off the screen; `out_line` then passes every row
through `_wrap_output`, which recognises a row framed by `│...│` or `║...║`
(an ASCII `|` frame is not recognised) and re-wraps its content inside the
borders. Nothing overflows as a result, but the fallback wrap knows
nothing about the row it is splitting: a continuation starts hard against the
left border rather than under the text it continues, and a header built as one
string splits its own box border across two rows. A screen therefore has to size
its own rows to be legible, not merely to fit -- wrapped with a hanging indent
for text a caller reads (a truncated trivia answer can make a question
unanswerable), and shortened for decoration such as a progress meter or a
prompt. A prompt needs `_dlen(prompt) < width`, not `<=`: one that exactly fills
the row leaves the cursor nowhere to sit but the next line. The door draws at
`min(78, terminal_width)`, so the 40-column floor and the 78-column cap are live
paths for the same string.


## The round's screens

The splash and finale are a game-show stage; the screens between them are the
contestant's card on it, and they take only the stage's colours and devices.
Keep to that vocabulary rather than adding to it: one rounded card per screen
with its title in the top edge and its hint (`Q quits`) in the bottom one, the
double frame only for the results, gold keys that are dark until pressed, and
lit labels (the splash's lower third) for verdicts and the rank. Green and red
mean right and wrong and nothing else.

The bulb row in a question's top edge is the round so far -- right, wrong, the
current question, the rest -- and the results card repeats it as the record of
the round. It is dropped, never wrapped, when the edge has no room for it.

Plain callers see no colour, so anything that colour alone distinguishes needs
a shape as well: a lit label becomes `[LABEL]`, and a dim marquee bulb a dot.

The verdict's flicker is the only motion in a round. It follows the splash's
rules where they apply: it runs only with a live input to poll, never when
typing-ahead is waiting (it reads nothing, so it could only delay that caller),
never for a plain caller, and `DOOR_SPLASH=0` turns it off. Every step rewrites
the same row from its start, so the row must stay narrower than the terminal.
