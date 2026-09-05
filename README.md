# agentic-invoice-pipeline

**Build Agentic Workflows — hands-on workshop repo**
Host: **Priyank Mehta (SaarthiOS)** · GrowthX · Bengaluru · Sep 6, 2026

One pipeline, end to end: **manufacture** a messy GST-invoice dataset with known
answers → **parse** it with the stack of your choice → **grade** the parser
against the answers you manufactured. Leave with numbers, not vibes.

Runs fully standalone — you do not need to have attended the workshop, and the
default path below is **100% free and local** (Track A: Ollama + Playwright,
no API keys). Paid tracks are optional upgrades via BYOK (`.env`).

## The rule of the day
**Generate ground truth before you generate documents.** The bot writes the
truth line to `ground_truth.jsonl` *before* it fills the form. We are not
labeling documents; we are manufacturing documents from labels. Every module
depends on this ordering.

## Repo map
| Folder | What | You produce |
|---|---|---|
| `00-idea-library/` | 9 document types to choose from + spec template | your team's filled spec |
| `00-model-finder/` | Which model fits this job, on your machine, at your volume | a written prediction the eval will test |
| `01-form/` | Data-entry webform + invoice renderer (FastAPI) | running server on :8000 |
| `02-generator/` | faker + chaos engine + Playwright bot | `dataset/` — 100 PDFs+PNGs + `ground_truth.jsonl` |
| `03-parser/` | 3 tracks (A local / B API / C framework), one shared schema | `outputs_track_*.jsonl` |
| `04-eval/` | Field-level eval, tier-sliced, leaderboard row | `eval_report.md` |
| `checkpoints/` | Pre-baked dataset + perfect-parser reference outputs | unblocked in <2 min |
| `docs/` | The three things you read: the deck, the field manual, the step sheet. All offline, all open straight in a browser | — |

### The `docs/` folder
Open any of these directly in a browser — no server, no build step. They are also what GitHub Pages serves.

| File | Who it's for | What's in it |
|---|---|---|
| `docs/Agentic-Workflows-Field-Manual.html` | **attendees, before Sunday** | what to install, what to decide, the sixteen ways this goes wrong, the run of show |
| `docs/Workshop-Steps-TrackB.html` | **Track B teams** | the paid-API path: forced tool calls, what they do and don't guarantee, and what a document really costs |
| `docs/Workshop-Steps-TrackC.html` | **Track C teams** | the framework path: the two-stage pattern, and the three things that fail before the network does |
| `docs/Workshop-Steps.html` | **everyone, on the day** | the step sheet — made to be projected. Do this, check it worked, and here is the part that matters. Every command copy-paste ready. |
| `docs/index.html` | **the room** | the slide deck — ←/→ or click the right third, type a number + Enter to jump, `P` to print |
| `PREFLIGHT.md` | maintainers | findings from a full end-to-end rehearsal on an 8 GB laptop, and what was changed as a result |

---

## Step 0 — pick your document (10 min)
Open `00-idea-library/IDEAS.md` and choose the document your team lives with
all day. The **GST invoice is the pre-built reference**: everything below runs
on it unmodified, and it is the right default if you want your time on parsing
and eval rather than templates.

Picked something else? Fill `00-idea-library/SPEC_TEMPLATE.md` first, then swap
exactly three things and nothing else:

| Swap | Survives unchanged |
|---|---|
| document template (`01-form/templates`) | the form server, the A4/150-DPI geometry contract |
| faker + chaos rules for your fields (`02-generator`) | truth-first ordering, the 60/20/12/8 tier structure |
| schema fields + validator rules (`03-parser`) | `common.py`, and all of `04-eval` |

**Four couplings the "three things" line hides** — every one of them fails *silently*:
- **Keep the `inv_` filename prefix.** `common.py` globs `inv_*`; rename and you parse zero documents.
- **`bot.py fill_and_print()` is a rewrite**, not a keep — 13 of its 22 lines name invoice fields.
- **Flatten grouped fields**, or accept one all-or-nothing score for the group.
- **Put `date` in every date field's name** — the scorer normalises dates by field *name*.

The eval harness derives its field list from your ground truth and outputs, so
it grades any document unchanged. Pass your spec's catchable tags via
`eval.py --catchable "tag1,tag2"`. That the harness never changes while the
document does is the architecture lesson of the day.

## Step 1 — pick your starting model (12 min)
```bash
open 00-model-finder/index.html     # single file, no server, no key
```
Answer five questions — what you're building, how you want to run it, your machine, your
volume, your hard constraints — and leave with **four numbers**:

| # | What | Where it goes |
|---|---|---|
| 1 | recommended model **and** the nearest track you can actually run | picks your `03-parser` file |
| 2 | cost per document | `eval.py --cost-per-doc <N>` |
| 3 | cost at your real monthly volume | this is gotcha **G6** |
| 4 | does it fit my machine — yes / no | Track A vs B, *before* you download 6 GB |

**This does not contradict M1.** You are not choosing a winner, you are writing down a
hypothesis the harness will spend the day trying to kill. The tool ranks benchmarks and
prices; it has never seen your documents. At 15:00 the eval tells you whether it was right —
and a prediction that gets overruled is the best demonstration of M1 available to you.

The practical reason: in our pre-flight rehearsal we lost ~50 minutes pulling a 6 GB vision
model that could not fit an 8 GB M2, then watching a smaller one thrash at 0.29 tok/s. Three
taps in the **Your machine** question says so before the first byte downloads.

> **Open it once at home on Saturday.** It caches the model catalog for 24 hours; cold with
> no network it shows an empty state. Venue wifi is where this goes to die too.

Details, and the 12-minute discipline: `00-model-finder/README.md`.

---

## Run it end to end — OPEN SOURCE TRACK (₹0, no keys)

### 0 · Prerequisites
- Python 3.11+ and git
- [Ollama](https://ollama.com) installed (`curl -fsSL https://ollama.com/install.sh | sh` or `brew install ollama`)
- **16 GB RAM, 8 GB of it free**, for the 7B vision model. Measured on an 8 GB M2: the 7b
  will not fit the ~4.8 GiB Metal budget at all, and even a 3b runs at 0.3 tok/s — about
  **30 minutes per document**. On 8 GB, take the text path below (it is faster *and* more
  accurate here) or Track B.
- Do the big downloads **on good wifi, at home**. At a typical 3.5 MB/s: `qwen2.5vl:7b`
  ~6 GB ≈ **30 min**, `llama3.2:3b` ~2 GB ≈ **10 min**, Playwright's Chromium ~150 MB ≈ 1 min.

### 1 · Clone + setup
```bash
git clone <repo-url> && cd agentic-invoice-pipeline
./setup.sh                      # venv + pip deps + playwright chromium + .env from template
ollama pull qwen2.5vl:7b        # Track A's vision model (~6 GB / ~30 min — 16 GB RAM only)
ollama pull llama3.2:3b         # 8 GB laptop? this instead (~2 GB / ~10 min)
```
No `.env` editing needed for this track — Track A requires zero keys.

### 2 · Start the form server (terminal 1)
```bash
source .venv/bin/activate
cd 01-form && uvicorn app:app --port 8000
```
Open http://localhost:8000 — this is the data-entry form the bot will fill.

### 3 · Manufacture the dataset (terminal 2)
```bash
source .venv/bin/activate
cd 02-generator && python bot.py --n 100 --seed 42
```
Watch truth-first in action: each ground-truth line lands in `dataset/ground_truth.jsonl`
*before* its PDF exists. Check it **per document**, not with `ls -lt` — the truth file is
appended throughout the run, so its mtime is newer than 99 of the 100 PDFs even though
every line was written before its own document. Expect 100 PDFs + 100
PNGs, tier mix 60 clean / 20 ok / 12 bad / 8 broken.

PNGs render **A4 at 150 DPI (1241×1754)** — the same geometry `checkpoints/gen_checkpoint.py`
produces, so Track A grades bot users and checkpoint users on identical images. If you change
the resolution in one generator, change it in the other (see `checkpoints/README.md`).

> **No browser / Playwright trouble?** Skip the bot:
> `unzip checkpoints/dataset-100.zip -d checkpoints/` gives you the identical
> seed-42 dataset, or regenerate browserless:
> `pip install weasyprint && python checkpoints/gen_checkpoint.py --n 100 --seed 42`

### 4 · Parse with the local model
```bash
ollama serve &                                  # if not already running
cd 03-parser
python track_a_local.py --dataset ../02-generator/dataset --limit 5   # smoke test first
python track_a_local.py --dataset ../02-generator/dataset             # full run → outputs_track_a.jsonl
```
**8 GB laptop, or no vision model?** Take the text path — and note it is not a consolation
prize. These invoices are printed from HTML, so the PDF text layer is perfect and pdfplumber
beats vision outright (gotcha G4). Measured on an 8 GB M2: vision ~30 min/doc, text
**8 s/doc** with zero parse errors.
```bash
ollama pull llama3.2:3b   # NOT llama3.1:8b — at 4.9 GB it does not fit the laptops this rescues
python track_a_local.py --text-fallback --dataset ../02-generator/dataset
```
Any model can be swapped without editing source: `--model <name>`, or `TRACK_A_MODEL` /
`TRACK_A_TEXT_MODEL` in `.env`.

### 5 · Grade it
```bash
cd ../04-eval
python eval.py --outputs ../03-parser/outputs_track_a.jsonl \
               --truth   ../02-generator/dataset/ground_truth.jsonl --cost-per-doc 0
```
Read `eval_report.md`: per-field × per-tier matrix (exact / normalized), validator recall
**and precision**, p50 latency, and a one-line leaderboard row.

Read it in this order:
1. **Slice before you believe any headline.** The `broken` column is often worst — but not
   always. In our own rehearsal `item.amount` scored 59% clean / 100% broken, because the
   broken tier injects *business-rule* violations that don't make a document harder to *read*.
   The point isn't that broken is worst; it's that until you slice you don't know where your
   difficulty lives.
2. **Recall, then precision.** A parser that transcribes badly flags nearly everything and
   scores 100% recall at 16% precision. Both numbers or neither. (Recall only means anything
   at n≥100 — a 10-doc smoke run can legitimately read `0/0`.)
3. **Headline vs parsed-only.** If parsed-only sits far above the headline, you have a
   *stability* problem, not an extraction problem — and that's a different fix.
4. **Exact vs normalized.** The gap is your post-processing spec, written for free.

### 6 · Trust check (optional, 30s)
A perfect verbatim parser must score 100% on this harness — verify it yourself:
```bash
python - << 'PY'
import json, sys; sys.path.insert(0, "../03-parser")
from schema import Invoice; from validators import validate
rows = [json.loads(l) for l in open("../checkpoints/reference_outputs.jsonl")]
out = open("/tmp/perfect.jsonl", "w")
for r in rows:
    d = r.pop("doc_id"); inv = Invoice.model_validate(r)
    out.write(json.dumps({"doc_id": d, "track": "perfect", "fields": inv.model_dump(),
                          "validation_flags": validate(inv), "latency_s": 0}) + "\n")
PY
python eval.py --outputs /tmp/perfect.jsonl --truth ../checkpoints/dataset/ground_truth.jsonl
```
(Unzip `checkpoints/dataset-100.zip` first if you haven't. Expected: **100.0%**,
validator recall **10/10**, precision **100%**, false flags **0**. Any number below this is
your parser's fault, not the scorer's — which is the whole point of running it.)

---

## Optional paid tracks — BYOK
```bash
cp .env.example .env    # done by setup.sh already
$EDITOR .env            # every key is documented inline, per track
```
| Track | Key(s) in `.env` | Then run |
|---|---|---|
| **B** paid API | `ANTHROPIC_API_KEY` | `python 03-parser/track_b_api.py --limit 5` |
| **C** framework | `LLAMA_CLOUD_API_KEY` only — stage 2 runs on your local Ollama model | `python 03-parser/track_c_llamaindex.py --limit 5` |

`.env` is gitignored and auto-loaded by the parser scripts. Always smoke-test
with `--limit 5` before spending money on 100 docs. Same eval command grades
every track — that's the point: one schema, one harness, honest leaderboard.

## The five learnings (full wording in slides + folder READMEs)
1. **M1** Pick the eval before the framework.
2. **M2** Truth first, chaos on purpose, with a log.
3. **M3** Extraction transcribes; validation judges — the scariest failure is the silent correction.
4. **M4** Headline accuracy is a lie; slice by tier, normalize both sides.
5. **M5** The harness is the asset; the parser is disposable.
