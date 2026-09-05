# 03-parser — three tracks, one schema

| | run | needs | status |
|---|---|---|---|
| **A** free/local | `python track_a_local.py --limit 5` | `ollama pull qwen2.5vl:7b` (at home!) | **run end to end, measured** |
| **B** paid API | `python track_b_api.py --limit 5` | `ANTHROPIC_API_KEY` in `.env` | corrected, **never executed** |
| **C** framework | `python track_c_llamaindex.py --limit 5` | `LLAMA_CLOUD_API_KEY` in `.env` + a heavy install | corrected, **never executed** |

Always smoke-test with `--limit 5` before spending time or money on 100.
All three emit the same `schema.Invoice` and the same `validators.validate()` flags —
different schemas = incomparable scores = no leaderboard.

All three take `--model` now, so you can swap models without editing source. That swap,
followed by a re-run of the same eval, *is* the workshop.

> **Honesty note.** Track A was run end to end many times and every number quoted for it is
> measured. Tracks B and C were corrected from provider documentation but never executed —
> we had no API keys. Their first real run may surface something. Smoke-test at `--limit 1`.

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

### C · framework — *the two-stage pattern, and what a framework costs*
LlamaParse → markdown → LlamaIndex `structured_predict` against the same `Invoice`.

Stage 1 turns *any* document — scans, rotated tables, a 40-page contract — into clean
markdown. Stage 2 is plain text extraction. For real document variety, stage 1 is the part
you would not want to build yourself, and that is what the framework buys you.

For **today's** invoices it is arguably overkill, and you should say so at demo time: our PDFs
are born-digital, so `pdfplumber` already reads a perfect text layer for free. That is gotcha
**G4**, and Track A proves it at 8 s/doc and ₹0.

The cost side is the other half of the lesson: three unpinned packages, no version floors, and
a model-id lookup that happens inside the framework before any request is sent. You pay the
framework tax before you extract a single field. **The framework buys you stage 1; the schema
and the validators stay yours.**

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
| C | `ModuleNotFoundError: llama_cloud_services` | the llama-index lines in `requirements.txt` are commented out on purpose. Uncomment, `pip install`, **at home** |
| C | Raises inside `Anthropic(...)` before any network call | llama-index keeps its own model→context-window registry. Upgrade `llama-index-llms-anthropic`, or `--model` an id it knows |
| C | `LLAMA_CLOUD_API_KEY` missing | both keys are needed — LlamaParse *and* the extraction LLM |

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
