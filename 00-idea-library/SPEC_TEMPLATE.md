# Document Spec — <your document type>
Team: ____________   Chosen from: 00-idea-library/IDEAS.md card #__

## Fields
| Key (snake_case; dates contain "date") | Type | Example as printed |
|---|---|---|
| | | |

## Format rules (regex/length/checksum — validators.py material)
1.

## Math / cross-field rules (deterministic arithmetic — validators.py material)
1.

## Chaos taxonomy (chaos.py material)
| Tier | Share /100 | Corruption tag | What it does | Validator should catch? |
|---|---|---|---|---|
| clean | 60 | — | nothing | — |
| ok |  |  |  | no |
| bad |  |  |  |  |
| broken |  |  |  | yes |

Catchable tags (comma-separated, passed to eval as --catchable):

## The three files you swap (everything else stays)
- [ ] 01-form/templates/<doc>_template.html  (+ form fields if using the bot path)
- [ ] 02-generator/faker + chaos rules for this document
- [ ] 03-parser/schema.py fields + validators.py rules

Files you do NOT touch: common.py, 04-eval/eval.py.
  But note what that really means: `bot.py`'s *flow* survives while the body of
  `fill_and_print()` is rewritten field by field; `common.py` survives only if you keep
  the `inv_` filename prefix it globs for; and `eval.py` survives if you pass your own
  `--catchable` tags (and `--row-key`, if it cannot infer your repeated-row list).. If you feel
the urge to edit the eval to fit your document, your field naming broke the
convention — fix the spec, not the harness.
