# 00-model-finder — pick your starting model, in 12 minutes

**Runs after you've picked your document (`00-idea-library/`) and before you write any code.**

```bash
open 00-model-finder/index.html      # macOS
xdg-open 00-model-finder/index.html  # Linux
```

Single HTML file. No server, no build, no API key. Double-click it.

---

## Why this exists, and why it is *not* a contradiction of M1

M1 says **pick the eval before the framework**. So why are we picking a model first?

Because we are not picking one. We are writing down a **hypothesis** that the harness will
spend the rest of the day trying to kill:

| 11:15 | this tool | *"Model X should win, at ₹Y/doc, and it fits my laptop."* |
|---|---|---|
| 15:00 | `04-eval/` | *"Here is what actually happened on your documents."* |

The tool ranks benchmarks and prices. It has never seen your documents, your chaos engine, or
your validators. Its own README says so:

> *Benchmark indices are one vendor's methodology, not ground truth for your workload —
> treat the shortlist as a starting point for your own eval, not a verdict.*

**A prediction made at 11:15 and overruled at 15:00 is the best possible demonstration of M1.**
Write the prediction down. That is the whole point of this step.

## The other reason: it stops you downloading a model that cannot run

In our own pre-flight rehearsal we lost roughly fifty minutes to this: pulled
`qwen2.5vl:7b` (~6 GB, 16 min), discovered it will not fit an 8 GB M2's 4.8 GiB Metal budget,
watched a smaller model thrash at 0.29 tokens/sec — about **30 minutes per document** — then
pulled a different model and started over.

Three taps in the **Your machine** question would have said so before the first byte
downloaded. If you take nothing else from this step, take the fit answer.

---

## Do this (12 minutes, then stop)

There are ~430 models, side drawers, and a tooltip on every term. It is genuinely interesting
and it will eat your morning if you let it. **Timebox it.** You are here for four numbers.

1. **What are you building** — describe your document task. This sets which benchmarks count.
2. **How you want to run it** — hosted API / your own hardware / both.
3. **Your machine** — three taps: chip family → specific chip → memory. Skip if API-only.
4. **Volume** — documents per month, *honestly*. 800 and 800,000 are different products.
5. **Hard constraints** — context floor, latency, required capabilities.

Only question 1 is required; everything else has a working default.

## Leave with these four numbers

Write them into your `00-idea-library/` spec and into section 04 of the field manual. They are
not decoration — three of them are consumed directly by later modules.

| # | What | Where it goes |
|---|---|---|
| 1 | **Recommended model + the track you'll actually run** | manual §04 `track`; picks your `03-parser` file |
| 2 | **Cost per document** | `eval.py --cost-per-doc <N>` at 15:00 |
| 3 | **Cost at your real monthly volume** | manual §04 `volume` — this is gotcha **G6** |
| 4 | **Does it fit my machine — yes / no** | decides Track A vs Track B *before* you download 6 GB |

**Record two answers for #1, not one.** The finder ranks the whole catalog, including models
this repo has no code path for. We ship three tracks:

| Track | Runs | File |
|---|---|---|
| A | any Ollama model, local | `03-parser/track_a_local.py` (`--model <name>`) |
| B | Anthropic API | `03-parser/track_b_api.py` |
| C | LlamaParse + LlamaIndex | `03-parser/track_c_llamaindex.py` |

There is no OpenRouter client in this repo. So if the finder recommends something we cannot
run today, note **both**: *what it recommended* and *the nearest track I can actually run*.
**The gap between those two is worth a sentence at demo day** — it is the honest version of
"open vs paid, decided per layer" from the 11:00 block.

---

## Before Sunday: open it once, at home

It fetches three public endpoints on load and caches the catalog in `localStorage` for
**24 hours**. Cold, with no network, it renders *"Could not reach the model catalog"* — there
is no bundled fallback catalog.

Venue wifi is where model pulls go to die, and it is where this goes to die too.

> **Open `index.html` on Saturday evening.** The 24-hour cache then covers an 11:00 Sunday
> start. Opening it on Friday does not.

Sources (all public, no key, permissive CORS):

| Source | Supplies |
|---|---|
| `openrouter.ai/api/v1/models` | ~430 models: pricing, context, modalities, open-weight flag, intelligence/coding/agentic indices |
| `aipricing.guru/api/pricing.json` | independent first-party provider list prices, with a source URL per model |
| `huggingface.co/api/models/{id}` | exact parameter counts and license tags, fetched lazily for the shortlist only |

---

## Closing the loop at 15:45

When you have a real number from `eval_report.md`, come back and compare:

- Did the recommended model win on *your* documents, or did the harness disagree?
- Was the predicted cost/doc anywhere near the measured one?
- At your real monthly volume, does the winner change?

That comparison — prediction versus measurement — is the sentence to open your demo with.

---

`UPSTREAM-README.md` is the tool's own documentation: scoring method, hardware model,
data sources, and how to retune the task weights. Read it if you want to argue with the
ranking, which you should.
