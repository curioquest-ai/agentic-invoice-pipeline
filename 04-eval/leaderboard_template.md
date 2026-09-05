# Leaderboard — paste your row from eval_report.md
| Team | Track | norm_acc | parse_fail | flag_prec | p50 latency | cost/doc | cost @ 1M docs/mo |
|---|---|---|---|---|---|---|---|
| example | B-api | 96.2% | 1 | 88% | 3.4s | ₹0.50 | ₹5,00,000 |

Winner is crowned PER COLUMN, not overall — that's the M1 triangle, remember.

**Read `flag_prec` next to accuracy.** A parser can transcribe badly, flag almost every
document, and still report 100% validator recall. Precision is what says the flags mean
something — 100% recall at 14% precision is a validator nobody can act on.
