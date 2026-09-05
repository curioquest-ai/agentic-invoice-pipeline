# checkpoints — nobody stays blocked past 15 minutes
- `dataset-100.zip` — 100 PDFs + PNGs + `ground_truth.jsonl` + `reference_outputs.jsonl`,
  generated with `--seed 42` (identical truth to what `bot.py --seed 42` produces).
- `reference_outputs.jsonl` — what a PERFECT verbatim parser emits per doc.
  Uses: (1) diff your parser against it when your score looks wrong;
  (2) smoke-test the eval — a perfect parser must score 100% (it does; we checked).
- `gen_checkpoint.py` — regenerate without a browser (WeasyPrint path):
  `pip install weasyprint && python gen_checkpoint.py --n 100 --seed 42`
  (PNGs additionally need poppler's `pdftoppm` on PATH.)

Unzip and point any track's `--dataset` here. Same grading, zero shame — the
workshop is about the pipeline, not the yak-shave.

## What is and isn't identical between the two paths

`bot.py` (Chromium) and `gen_checkpoint.py` (WeasyPrint) share the records, the
chaos engine and the Jinja template, but not the rendering engine:

| | identical? | why it matters |
|---|---|---|
| `ground_truth.jsonl` | **yes, byte-for-byte** | the only thing the eval grades against |
| PNG geometry | **yes — 1241×1754, A4 at 150 DPI** | Track A's vision model reads these; a size mismatch would grade people on different images |
| PDF bytes | no — Chromium vs WeasyPrint | Tracks B/C read the text layer, which carries the same values |

The PNG contract is deliberate and is enforced in two places: `bot.py` sets an A4
viewport at `device_scale_factor = 150/96`, and `gen_checkpoint.py` uses
`pdftoppm -r 150`. **If you change one, change the other** — otherwise checkpoint
users and bot users are competing on different inputs while the leaderboard claims
they are not. (Before this was fixed, `bot.py` emitted 1280×720 landscape: 2.4×
fewer pixels than the checkpoint, on a portrait document.)
