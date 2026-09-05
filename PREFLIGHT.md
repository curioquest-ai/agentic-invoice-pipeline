# Pre-flight rehearsal — what breaks tomorrow

**Run:** 5 Sep 2026 · full end-to-end pass of this repo, following the field manual verbatim
**Machine:** Apple M2 · 8 GB unified · Metal budget 4.8 GiB (attendee-class laptop)
**Track:** A — free & local · **Documents:** 100 × 3 passes · **Findings:** 15 (4 blocking)

The pipeline works. The harness is sound. Four things will cost people the afternoon
if they ship as written.

---

## 1 · Verdict

| | |
|---|---|
| **100.0%** | Trust check — a perfect parser scores perfectly. The scorer is not the problem. |
| **byte-exact** | `bot.py --seed 42` reproduces the shipped checkpoint identically |
| **33 min** | One document silently hung the batch — no error, no timeout |
| **0.29 t/s** | Track A's documented vision model on 8 GB — ~30 min per document |

> **If you change only one thing tonight:** add `num_predict` to the Ollama options.
> Without it a single invoice can generate forever — 30,000 tokens and climbing — and
> because a hang is not an exception, `_with_retry` never fires. The attendee sees no
> error, no progress, and no reason. They miss the 15:45 leaderboard.

---

## 2 · What ran clean

Verified against the manual's own instructions, not a paraphrase.

- **`setup.sh`** — venv, deps, Chromium, `.env` from template. Clean on Python 3.12.
- **Form server** — `uvicorn app:app --port 8000`, both routes 200. Every input has a
  stable `id`, which is why the bot is fifteen lines of fills.
- **Data factory** — 10 docs in 5.1 s, 100 docs in ~50 s. Tier mix lands exactly
  **60 / 20 / 12 / 8**.
- **Seed-42 reproducibility** — locally generated ground truth is **byte-identical** to
  `checkpoints/dataset-100.zip`. The fallback path grades against the same answers.
- **Checkpoint unzip** — 100 PDFs, 100 PNGs, ground truth, reference outputs.
- **README step 6 trust check** — 100.0% normalised, validator recall 10/10, false flags 0.
  Copy-pastes and runs as written.
- **Clean data passes its own validators** — zero flags across all 60 clean documents, so
  the eval is not poisoned before it starts.

---

## 3 · Blocking findings (fix before 11:00)

### F-01 · A single document can hang the whole batch, forever, silently — `03-parser` · P1

On `inv_0005` — an invoice with exactly **one line item** — the model entered an unbounded
generation loop under constrained decoding: **30,215 tokens over 33 minutes** on one
document.

Three causes compound:
1. `schema.py` puts no `maxItems` on `items`, so nothing forces the array to close.
2. No track sets `num_predict`, so nothing bounds the response.
3. `common._with_retry` has no timeout, so a hang raises nothing and the retry never fires.

The first pass completed 100/100 only by luck — the bug was always there.

**Fix:** cap generation and bound the array. With the cap alone the same document failed in
55 s with a readable `JSONDecodeError` and the batch carried on. With `maxItems` added it
now **completes OK in 9.01 s** — the decoder can't run away, so it terminates naturally.

---

### F-02 · Track A's vision path does not run on an 8 GB Mac — `manual §05` · P1

M2, 8 GB unified, Metal budget **4.8 GiB**. Even `qwen2.5vl:3b` loads with
`reason=metal_partial_offload` and thrashes:

- **34 s** to encode one invoice image (3 batches × ~11.5 s)
- generation at **0.29 tokens/sec**
- ≈ **30 minutes per document**, two days for 100

The recommended `qwen2.5vl:7b` at 6 GB cannot fit the budget at all. The manual's
"~8 GB RAM for the 7B vision model" reads as a floor this machine meets. It does not.

**Fix:** state a hard floor of **16 GB free** for Track A vision, and route 8 GB machines
to the text path by default — not as a fallback.

---

### F-03 · The documented weak-laptop fallback is also too big — `03-parser` · P1

`extract_text_fallback()` hardcoded `llama3.1:8b` at **4.9 GB** — still over the 4.8 GiB
Metal budget on the machines it exists to rescue. The escape hatch had the same failure
mode as the thing it escapes.

**Fix:** `llama3.2:3b` (2.0 GB) fits entirely in GPU and ran at **7.6 s/doc** with zero
errors — roughly **200×** the vision path on this hardware.

---

### F-04 · setup.sh builds the venv on whatever Python is first on PATH — `setup.sh` · P1

Bare `python3 -m venv` picked **3.14.5** here — newer than anything `requirements.txt` is
tested against, and the usual casualties are Playwright and pdfplumber wheels. On a 2026
laptop this is common, and it costs the whole 11:30 block.

**Fix:** probe for 3.12 / 3.11 / 3.13 and fail loudly with an install hint.

---

## 4 · The patch set — APPLIED

```diff
── 03-parser/track_a_local.py ─────────────────────────── the hang
-        options={"temperature": 0},
+        options={"temperature": 0, "num_predict": NUM_PREDICT},

── 03-parser/schema.py ────────────────────── bound the array too
-    items: list[LineItem]
+    items: list[LineItem] = Field(max_length=20, description="Line items, in printed order")

── 03-parser/track_a_local.py ────────── stop hardcoding the model
-MODEL = "qwen2.5vl:7b"
+MODEL      = os.environ.get("TRACK_A_MODEL", "qwen2.5vl:7b")      # 16 GB+
+TEXT_MODEL = os.environ.get("TRACK_A_TEXT_MODEL", "llama3.2:3b")  # was llama3.1:8b
+ap.add_argument("--model", default=None)

── setup.sh ──────────────────────────── pin a tested interpreter
+for cand in python3.12 python3.11 python3.13 python3; do
+  ver=$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
+  case "$ver" in 3.11|3.12|3.13) PY="$cand"; break;; esac
+done
+[ -z "$PY" ] && { echo "✗ Need Python 3.11–3.13"; exit 1; }
```

**Verified:** `bash -n setup.sh` clean and the probe picks 3.12 · `maxItems: 20` present in
`INVOICE_JSON_SCHEMA` · `validators.py` and `faker_in.py` self-tests pass · `--model` in
`--help` · `inv_0005` completes OK in 9.01 s on the unmodified repo file.

---

## 5 · What the run actually measured

Three passes over the same 100 documents. Same schema, same validators, same harness —
only the prompt moved. That is **M5**, demonstrated rather than asserted.

| Pass | What changed | Accuracy | Parse fails | p50 |
|---|---|---:|---:|---:|
| v1 | Shipped prompt, text path | 71.8% | 0 | 6.72s |
| v2 | +3 rules: decimals, no-null, row count | 66.6% | 14 | 7.89s |
| **v3** | **Dropped the row-count rule only** | **72.9%** | **0** | 8.22s |

### The headline was lying, and the slice caught it

v2 looked like a clear regression: 71.8% → 66.6%, revert it. But `date` and `invoice_no` —
untouched by the prompt change — dropped from 100% to 86%, **exactly matching the 14 parse
failures**. Failed documents take zero credit on every field, so a *stability* regression
and an *accuracy* regression look identical in the report.

Regrading both passes on only the 86 documents v2 survived: **v1 70.9%, v2 72.1%.**
The prompt was better all along. One bad rule masked two good ones.

| Field | v1 | v3 | Δ | Why |
|---|---:|---:|---:|---|
| `gstin` | 24% | 57% | **+33** | 76 nulls, 0 mis-transcriptions — refusal to transcribe, not inability to read |
| `item.rate` | 47% | 59% | **+12** | Indian 2-2-3 grouping ate decimal points: `2,055.38` → `205538.0` |
| `item.description` | 86% | 88% | +2 | — |
| `total` | 78% | 80% | +2 | — |
| `item.hsn` | 42% | 25% | **−17** | Naming HSN made column bleed worse — `'6A 8536'`. **Unfixed.** |

The `gstin` tier row is the demo: **clean 22→52, ok 20→55, bad 42→75, broken 25→75.**
Every column moved, and we knew *why* before changing anything, because the diagnostic said
76 nulls and zero wrong reads.

---

## 6 · Findings that cost hours

### F-05 · "Validator recall 10/10" is reported as a win on a parser that flagged 59 of 60 clean docs — `04-eval` · P2

The report prints `recall 10/10 caught | false flags on clean docs: 59` — good news first,
on one line. Perfect recall is trivial when you flag almost everything. **Precision here is
14%**, and that is the number that matters.

**Fix:** compute and print precision beside recall, and say plainly that recall alone is worthless.

```python
precision = caught / (caught + false_pos) if (caught + false_pos) else 0
f"- Validator recall {caught}/{broken} | false flags {false_pos} "
f"| **precision {precision:.0%}** -- recall is worthless without this"
```

### F-06 · Parse failures silently contaminate every field score — `04-eval` · P2

A failed document zeroes all twelve fields. Defensible, but the report cannot distinguish
"my extraction got worse" from "my run got less stable" — I only untangled it by hand-slicing
to the common 86 documents.

**Fix:** print a second headline restricted to successfully-parsed documents. The gap between
the two names the kind of problem, the way exact-vs-normalised already names post-processing.

### F-07 · The 13:15 gate check reads as broken when it is fine — `manual §05` · P2

"Truth file older than the PDFs" holds for **birth** time (18:18:35 vs 18:18:37) but not
modification time — the truth file is appended throughout the run, so `ls -lt` puts it on
top, newer than 99 of 100 PDFs. An attendee checking the gate concludes the rule of the day
is broken.

**Fix:** check the per-document invariant instead — it proves the claim properly and cannot
be misread:

```bash
python - <<'PY'
import json
from pathlib import Path
d = Path("dataset")
for line in open(d/"ground_truth.jsonl"):
    r = json.loads(line)
    assert (d/f"{r['doc_id']}.pdf").exists(), f"{r['doc_id']}: truth written, PDF missing"
print("truth-first invariant holds for every doc")
PY
```

### F-08 · No download-time estimate for the model pull — `manual §05` · P2

"Do the big downloads on good wifi" has no number attached. Measured: 3.2 GB in ~16 minutes,
about 3.4 MB/s. The 6 GB `qwen2.5vl:7b` is therefore roughly **30 minutes**.

**Fix:** quote the minutes. People plan around numbers, not adjectives.

### F-09 · "~8 GB RAM" is ambiguous and this machine met it while failing — `manual §05` · P2

8 GB *total* is not 8 GB *free*. During the vision run the system sat at 14% free memory
with heavy pageouts.

**Fix:** say "16 GB total / 8 GB free" and give a one-line way to check.

---

## 7 · Worth fixing, not blocking

### F-10 · Track A feeds the vision model a 720p screenshot — `02-generator` · P3

`page.screenshot(full_page=True)` on a default viewport yields **1280×720**. Track B gets the
real PDF with a perfect text layer. GSTIN and HSN are small type at that scale, so the free
track carries a systematic resolution handicap — "Track A scored badly" may be a rendering
decision, not a model limit.

**Fix:** `browser.new_page(device_scale_factor=2)` → 2560×1440. Worth measuring before Sunday.

### F-11 · A 10-doc smoke run reports "validator recall 0/0" — `04-eval` · P3

At `--n 10` the single `broken` document drew `duplicate_invoice_no`, which `flag_audit()`
deliberately excludes as a cross-doc check. Not a bug, but it will raise hands.

**Fix:** say up front that recall is only meaningful at n ≥ 100.

### F-12 · The broken column may not collapse — and your slide promises it will — `slides · M4` · P3

M4 promises "100% on clean, 40% on the broken 8%". In this run it **inverted**:
`item.amount` scored 59% on clean and 100% on broken. The reason is structural — the `broken`
tier injects *business-rule* violations (`cgst_wrong_math`, `duplicate_invoice_no`) that do
not make a document harder to *read*. Difficulty here lives in number formatting, not tier.

**Fix:** reframe as *"slice by tier to discover where difficulty actually lives — sometimes it
is not where you assumed."* Truer, more useful, and it survives a run that does not cooperate.

### F-13 · Track C's dependencies are commented out, and the warning is buried — `requirements.txt` · P3

Deliberate — but the note lives in the troubleshooting table, so a Track C attendee who ran
`setup.sh` at home still arrives with a heavy install pending on venue wifi.

**Fix:** move it into §05 Setup, where they read before Sunday.

### F-14 · A truth-side validator ceiling check would earn its slide — new · P3

Running `validators.validate()` over ground truth — no model, two seconds — shows the ceiling
before anyone parses anything:

| tier | docs | flagged | what fired |
|---|---:|---:|---|
| clean | 60 | **0** | — |
| ok | 20 | 13 | `GSTIN_LOWERCASE` |
| bad | 12 | 8 | `TOTAL_MISMATCH` ×4, `GSTIN_MISSING` ×4 |
| broken | 8 | **2** | `CGST_SGST_UNEQUAL` ×2, `TOTAL_MISMATCH` ×2 |

Only **two of eight** "broken" documents are detectable per-document, because five are
duplicate invoice numbers a per-doc validator structurally cannot see, and one is a Hindi
description that isn't a rule violation at all.

**Fix:** add it to the 14:00 block. It makes gotcha G10 concrete instead of theoretical, and
it is the best demo-day discussion prompt in the repo.

---

## 8 · Tomorrow morning

- [x] **Apply the four patches** — `num_predict` first
- [x] **Add the hardware floor to §05** — 16 GB free for vision; 8 GB machines take the text path by default
- [x] **Document both model pulls with minutes** (manual + README)
- [x] **Fix the 13:15 gate check** so it cannot read as broken
- [x] **Add precision to the eval report** (F-05) and a parsed-only headline (F-06)
- [x] **Keep the trust check as-is** — README step 6 runs verbatim and proves the harness
- [x] **Keep the checkpoint promise** — seed 42 reproduces byte-identically

---

*Run end to end against the repo as shipped, following the field manual's own instructions
rather than a paraphrase. Every number here is reproducible from `--seed 42`.
Three parser passes, 300 documents graded, one hang caught.*

---

## 9 · Applied on 5 Sep, after the rehearsal

**Code**
- `03-parser/track_a_local.py` — `num_predict` cap on both call sites; `MODEL`/`TEXT_MODEL`
  from env with a `--model` flag; text fallback `llama3.1:8b` → `llama3.2:3b`
- `03-parser/schema.py` — `items` bounded at `maxItems: 20`
- `setup.sh` — probes 3.12/3.11/3.13, fails loudly otherwise; quotes pull times
- `04-eval/eval.py` — validator **precision** beside recall; **parsed-only headline**;
  `flag_prec` added to the leaderboard row
- `04-eval/leaderboard_template.md` — `flag_prec` column + why it matters

**Copy**
- Manual §05 — 16 GB floor with the measured numbers; pull times in minutes; text path
  promoted from fallback to the 8 GB default; Track C install warning moved into Setup
- Manual §05 gate 13:15 — per-document invariant, and an explicit "do not use `ls -lt`"
- Manual §05 eval reading order — recall *then* precision; headline vs parsed-only
- Manual §05 — new **"Know your validator ceiling"** section with the tier table (F-14)
- Manual failure library M4 — reframed so a run where `broken` isn't worst still proves it
- `slides/index.html` M4 — same reframe, plus a gotcha box with the inverted result
- `README.md` — all of the above, kept in sync

**Verified after patching:** `bash -n setup.sh` clean and probe picks 3.12 · `maxItems: 20`
in `INVOICE_JSON_SCHEMA` · validators + faker self-tests pass · all 9 manual edits render
under `node` · both HTML files' JS parses · `inv_0005` (the 33-minute hang) completes OK in
**9.01 s** · trust check still **100.0% / 10-10 / precision 100% / 0 false flags**.

**F-10 — done, and it was worse than first diagnosed.** The two generators did not
merely differ from an ideal; they differed from *each other*:

| path | PNG | |
|---|---|---|
| `bot.py` (before) | 1280 × 720 | landscape frame for a portrait A4 page |
| `gen_checkpoint.py` | 1241 × 1754 | A4 at 150 DPI, correct |

Checkpoint users were feeding their vision model **2.4× the pixels** of bot users while the
leaderboard claimed both were graded on the same documents. `checkpoints/README.md` said
"Same documents, same grading" — untrue for Track A.

Fixed by aligning `bot.py` to the checkpoint's geometry rather than inventing a third one:
an A4 viewport at `device_scale_factor = 150/96` → **1241 × 1755**. That means **no re-cut
of `dataset-100.zip` was needed** — ground truth stayed byte-identical to both the previous
run and the shipped checkpoint, so the zip remains valid.

One consequence had to be handled: the larger image costs **2983 prompt tokens** against
Ollama's 4096 default context, leaving only ~1100 for generation — and a context overflow
does not raise, it silently truncates. `track_a_local.py` now sets `num_ctx=8192`
(verified: `n_ctx_slot = 8192`, headroom 5209).

Also added: `PNG_DPI` constant in `gen_checkpoint.py` cross-referencing `bot.py`, a rewritten
`checkpoints/README.md` stating exactly what is and isn't identical between the two paths, and
failure card **G11 — "Your generator decides what the model can see"** in the manual
(now sixteen cards).

---

## 10 · Added after the rehearsal: `00-model-finder/`

**Step 1, between picking your document and writing any code.** A single-file HTML app
(bundled from `llm-finder`) that answers: which model fits this job, can I self-host it, and
what does it cost at my real monthly volume?

**Why it earns its 12 minutes:** the rehearsal's biggest time sink was discovering, the
expensive way, that `qwen2.5vl:7b` cannot fit an 8 GB M2 — a 16-minute pull, 33 minutes of
thrashing at 0.29 tok/s, then a second pull. Three taps in its **Your machine** question
answers that before the first byte downloads. It directly prevents F-02 and F-03 recurring
in the room.

**Why it does not contradict M1.** It produces a *hypothesis*; `04-eval` *falsifies* it. The
prediction is written down at 11:15 and the harness returns a verdict at 15:00 — which makes
M1 concrete instead of asserted. The tool's own docs agree: *"treat the shortlist as a
starting point for your own eval, not a verdict."*

**Where the time comes from:** nowhere. The 11:00 block was 30 minutes of lecture on the
cost/control/time-to-ship triangle. The second 15 minutes is now that triangle measured on
the attendee's own machine and volume. Net zero on the clock, lecture upgraded to exercise.

**Three conditions, all now written into the docs:**
1. **Pre-cache at home.** It fetches three live endpoints and caches for 24 h; cold and
   offline it renders an empty state — there is no bundled fallback catalog. The manual's
   prerequisites table now says *Saturday evening*, and says Friday is too early.
2. **Constrain to runnable tracks.** It ranks ~430 models including OpenRouter-only ones; this
   repo has code paths for Ollama, Anthropic and LlamaIndex only. Attendees record **two**
   answers — what it recommended, and the nearest track they can actually run. The gap is a
   demo-day talking point.
3. **Hard timebox, required artifact.** 12 minutes, and four numbers written into manual §04:
   model+track, cost/doc, cost at volume, fits-my-machine. Without those four the exercise
   was a toy.

**Files touched:** `00-model-finder/{index.html, README.md, UPSTREAM-README.md}` ·
`README.md` (repo map + Step 1 section) · manual (11:00 slot rewritten, new **11:15 gate**,
scope §04 gains a `prediction` field as its first question, setup prerequisites row, added to
the "Keep" table) · `slides/index.html` (new slide 7, between the idea library and the data
factory).
