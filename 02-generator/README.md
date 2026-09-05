# 02-generator — faker + chaos + bot
```bash
python bot.py --n 100 --seed 42     # needs 01-form running on :8000
```
Order of operations, and it is the rule of the day:
`faker_in.py` (clean, valid record) → `chaos.py` (logged corruption) →
**ground truth written** → form filled → PDF/PNG printed. Truth exists before
the document does.

Tier mix per 100: clean 60 / ok 20 / bad 12 / broken 8 — each corruption is
logged in `corruptions[]` so the eval can slice by difficulty.

**Key learning** — Real-world error distributions cluster — dates, digit
transpositions, missing IDs — they're not uniform random noise. A chaos engine
that models realistic failure modes is worth 10x one that sprinkles random typos.

**#1 mistake in the wild** — Generating synthetic data with no labels, then
hand-labeling later (or never). We wrote truth first.

**Gotcha** — OpenRPA earns its keep when the target is a Windows desktop app
with no API; for browsers, Playwright is the tool.
