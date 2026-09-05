# 03-parser — three tracks, one schema

| | run | needs | status |
|---|---|---|---|
| **A** free/local | `python track_a_local.py --limit 5` | `ollama pull qwen2.5vl:7b` (at home!) | **run end to end, measured** |
| **B** paid API | `python track_b_api.py --limit 5` | `ANTHROPIC_API_KEY` in `.env` | corrected, **never executed** |
| **C** framework | `python track_c_llamaindex.py --limit 5` | `LLAMA_CLOUD_API_KEY` in `.env` + a ~180 MB install. Stage 2 is local by default — no second key | **run end to end, measured: 82.8%** |

Always smoke-test with `--limit 5` before spending time or money on 100.
All three emit the same `schema.Invoice` and the same `validators.validate()` flags —
different schemas = incomparable scores = no leaderboard.

All three take `--model` now, so you can swap models without editing source. That swap,
followed by a re-run of the same eval, *is* the workshop.

> **Honesty note.** Tracks **A and C** were both run end to end over all 100 documents and
> every number quoted for them is measured. **Track B has never been executed** — no Anthropic
> key. Smoke-test at `--limit 1` regardless.

---

## Which track, and what each one actually teaches

### A · free and local — *what it costs you to own the whole stack*
Ollama, on your laptop, ₹0. Two paths inside it: a **vision** path (PNG → Qwen2.5-VL) and a
**text** path (`--text-fallback`, pdfplumber → a small text model).

The lesson is not "local is cheaper". It is that **the resource you spend shifts from money
to memory and time**, and you have to measure that too. On a 16 GB machine the vision path is
fine. On 8 GB it is unusable — measured: the 7b will not fit the Metal budget at all, and a
3b runs at **0.29 tokens/sec, about 30 minutes per document**. The text path on the same
machine does **8 s/doc**. Same laptop, same documents, 200× apart.

### B · paid API — *what "structured output" actually means*
The reason to run B is one line:

```python
tool_choice={"type": "tool", "name": "record_invoice"}
```

**Forced tool choice** makes the model answer *through your schema* instead of writing prose
you then dig JSON out of. No markdown fences, no `coerce_json()`, no regex. That is what
structured output means, and the pattern outlives the vendor — the OpenAI equivalent is
`response_format` with `json_schema` + `strict: true`.

Be precise about what it buys, because it is easy to overclaim: a forced tool call guarantees
you get a **`tool_use` block**. It does **not** guarantee that `block.input` validates against
your schema. The parameter that guarantees validation is `strict: true`, and strict requires
`additionalProperties: false` plus `required` — neither of which pydantic's
`model_json_schema()` emits. So today the *shape* is guaranteed by construction and
*correctness* is still caught by `Invoice.model_validate()` in `common.py`.

**Structured output removes a class of parsing bugs. It does not remove your validation layer.**

### C · framework — *the two-stage pattern, and what it actually buys*
LlamaParse → markdown → LlamaIndex `structured_predict` against the same `Invoice`.

Stage 1 turns *any* document — scans, rotated tables, a 40-page contract — into clean
markdown. Stage 2 is plain text extraction. For real document variety, stage 1 is the part
you would not want to build yourself.

**We expected this to be overkill on born-digital PDFs. We were wrong, and we have the
numbers.** Same 100 documents, same schema, same validators, same scorer, and the *same local
model* in stage 2 — so the only variable is LlamaParse vs `pdfplumber`:

| | Track A | Track C | |
|---|---:|---:|---|
| **headline** | 72.9% | **82.8%** | **+9.9** |
| `item.rate` | 59% | **83%** | +24 |
| `item.amount` | 67% | **82%** | +15 |
| `item.hsn` | 25% | **40%** | +15 |
| `item.description` | 88% | **100%** | +12 |
| `item.qty` | 92% | **99%** | +7 |
| `total` | **80%** | 72% | −8 |
| p50 latency | **8.2 s** | 23.5 s | ~3× slower |

**Every line-item field improves; only the scalars are a wash.** That is the whole finding, and
it is not about text fidelity — `pdfplumber` reads the characters perfectly. It is about
**structure**: LlamaParse hands the model a markdown *table* with named columns, while
`pdfplumber` hands it a flat run of numbers the model has to segment itself. Give a small model
a table and it stops guessing which number is the rate and which is the amount.

Note gotcha **G4** is untouched by this — we are not comparing against OCR, and `pdfplumber`
still beats rasterising a born-digital page. What was wrong was the *extension* of G4 into
"therefore a document-conversion stage is pointless here."

One caveat, stated because it cuts against us: Track A's number comes from its improved v3
prompt, while Track C ran the base `EXTRACTION_PROMPT`. C won with the weaker prompt.

The cost is real: **3× the latency**, a LlamaParse page per document, a ~180 MB install, and
three unpinned packages. Whether +9.9 points is worth that is a decision you can now make with
numbers instead of taste — which is the entire point of the day.

**Stage 2 defaults to your local Ollama model**, so this track needs one key, not two — and
that default is the point. Keep stage 2 identical to Track A and the only variable left is
LlamaParse vs `pdfplumber`, which is the question Track C exists to answer. Bolt a paid API
onto stage 2 and you have mixed in Track B's question and can no longer tell which stage moved
your score. `TRACK_C_LLM=anthropic` if you want the paid path anyway.

The cost side is the other half of the lesson: three unpinned packages, no version floors, and
a model-id lookup that happens inside the framework before any request is sent. You pay the
framework tax before you extract a single field. And note what the abstraction takes away:
Track A hands Ollama the JSON schema via `format=` — constrained decoding, where the tokens
*cannot* leave the schema — while `structured_predict` gives you the framework's own handling
instead. Same model, same schema, weaker guarantee. **The framework buys you stage 1; the
schema and the validators stay yours.**

---

## What Track B costs — estimated, not measured

We cannot give you a real number, and the reason is itself the lesson.

At Sonnet 5's published **$2 / $10 per million** tokens, one of our one-page invoices is
roughly 2,500 input + 350 output tokens:

```
input   2,500 × $2/1M  = $0.0050
output    350 × $10/1M = $0.0035
                       ≈ $0.0085/doc  ≈ ₹0.75/doc
```

| | |
|---|---|
| today's 100 documents | **≈ ₹75** |
| at 1M documents/month | **≈ ₹7.5 lakh** — a headcount, not a rounding error |

**That is an estimate.** `track_b_api.py` never reads `resp.usage`, so the repo cannot report
what a document actually cost — which is gotcha **G6** ("cost measured but never
extrapolated") happening in our own code, on the one track that could measure it. If you want
the true figure: read `usage.input_tokens` / `usage.output_tokens` off the response, write
them into each JSONL row, and sum. It is about six lines.

---

## First failure by track

| Track | What breaks first | Fix |
|---|---|---|
| A | 8 GB laptop on the vision path — glacial, one doc never finishes | `--text-fallback` |
| A | `ConnectionError` on :11434 | `ollama serve &` |
| B | `authentication_error` | `ANTHROPIC_API_KEY=sk-ant-…` in repo-root `.env` |
| B | Every doc `ERR`, output file full, score 0% | a rejected request parameter — read the error text on row 1 rather than the wall of them |
| B | Unexplained `ValidationError` on a long invoice | `max_tokens` truncation. `parse_one` now names this explicitly; raise `TRACK_B_MAX_TOKENS` |
| C | `ModuleNotFoundError: llama_cloud_services` | the llama-index lines in `requirements.txt` are commented out on purpose (~180 MB). Uncomment, `pip install`, **at home** |
| C | Stage 2 hangs, then times out on a *tiny* prompt | **Measured, and the sharpest finding on this track.** llama-index's `Ollama` defaults `context_window=-1`, meaning the model's full 131,072 — Ollama then allocates a 128K KV cache on a laptop that cannot afford it. A 365-token prompt took **over 3 minutes and timed out**. Pinning `context_window=8192` (Track A's measured value) took the identical call to **5.5 s**. Now pinned in `_make_llm()`; override with `TRACK_C_NUM_CTX` |
| C | `DeprecationWarning` on import | `llama-cloud-services`' stated maintenance window ended **2026-05-01**. Successor: `pip install llama-cloud>=1.0`. It still works — we kept what we could verify |
| C | Raises inside `Anthropic(...)` before any network call | llama-index keeps its own model→context-window registry. Upgrade `llama-index-llms-anthropic`, or `--model` an id it knows |
| C | `LLAMA_CLOUD_API_KEY` missing | stage 1 needs it. Stage 2 does not need a key unless you set `TRACK_C_LLM=anthropic` |

**A 400 does not look like a crash.** `common._with_retry` retries once, `run_track` catches
per document, and you get a complete 100-row output file with zero fields and a 0% leaderboard
row. Read the `error` text on the *first* row; the other 99 say the same thing.

---

**Key learning** — Extraction transcribes; validation judges — never let the model do both.
An LLM asked to "extract and verify" will quietly repair broken tax math into consistency,
destroying the very signal (data-entry errors) this pipeline exists to surface. The scariest
failure is the silent correction.

**Gotcha** — JSON in a text response ≠ structured output — use tool-calling / JSON-schema mode
or you'll spend 20 minutes regex-ing markdown fences (`common.coerce_json` is the 20 minutes,
pre-spent — and if your track relies on it, something upstream is misconfigured).

**Gotcha** — Determinism knobs are provider-specific. `temperature=0` is right for Ollama in
Track A; current Anthropic models removed sampling parameters entirely and return **400** if
you send one. The principle travels; the parameter does not.

**Gotcha** — For born-digital PDFs like ours, pdfplumber text extraction beats OCR entirely.
OCR is for scans; check what you have before you rasterize.

**Gotcha** — Document content is DATA, not instructions. A hostile invoice that says "ignore
previous instructions" is an attack surface — rule 5 of the shared prompt is the first line of
defense; never eval-then-execute parsed text.
