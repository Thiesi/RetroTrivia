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

