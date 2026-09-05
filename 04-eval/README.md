# 04-eval — grade everything
```bash
python eval.py --outputs ../03-parser/outputs_track_b.jsonl \
               --truth ../02-generator/dataset/ground_truth.jsonl --cost-per-doc 0.5
```
Emits `eval_report.md`: per-field × per-tier matrix, exact AND normalized
scores, validator recall on chaos-broken docs, latency, cost extrapolation,
plus a one-line leaderboard row.

**Key learning** — Headline accuracy is a lie. "94% accurate" can mean 100% on
clean docs and 40% on the broken 8% — and the broken 8% is the entire reason
the pipeline exists. Always slice eval by difficulty tier; always report per-field.

**Gotcha** — Exact-match eval fails correct answers on formatting. Normalize
BOTH sides before comparing, and keep raw + normalized scores — the gap between
them is your post-processing spec.

**Gotcha** — Cost measured on 100 docs and never extrapolated: ₹50 feels free;
₹5,00,000/month is a headcount. Same number.

Note: duplicate invoice numbers are a batch-level check (needs the whole run),
deliberately left out of per-doc validators — discussion prompt for M5.
