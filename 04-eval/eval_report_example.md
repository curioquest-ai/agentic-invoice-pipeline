# Eval report -- track: perfect-parser

*(Example report: the simulated perfect parser on the checkpoint dataset -- your report will replace this file.)*

| Field | clean (exact/norm) | ok (exact/norm) | bad (exact/norm) | broken (exact/norm) | ALL (exact/norm) |
|---|---|---|---|---|---|
| vendor | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| gstin | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| invoice_no | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| date | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| cgst | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| sgst | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| total | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| item.description | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| item.hsn | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| item.qty | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| item.rate | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |
| item.amount | 100%/100% | 100%/100% | 100%/100% | 100%/100% | 100%/100% |

- Headline normalized accuracy (all fields, all tiers): **100.0%** -- now read the broken column above -- see M4, 'headline accuracy is a lie'.
- Accuracy on successfully-parsed docs only: **100.0%** (100/100 docs) -- if this is much higher than the headline, your problem is stability, not extraction quality.
- Parse failures (doc produced no output): 0
- Validator recall on chaos-broken docs: 10/10 caught  | false flags on clean docs: 0
- Validator **precision: 100%** (10 true / 10 total flagged docs) -- recall is worthless without this: a validator that flags everything scores 100% recall.
- p50 latency: 0.00s

Leaderboard row (paste into the shared sheet):
```
perfect-parser | norm_acc=100.0% | parse_fail=0 | flag_prec=100% | p50=0.00s | cost/doc=Rs.0
```