# LLM Finder

A single-file HTML app that answers, before you start building: **which model fits this job, can I self-host it, and what will it cost per month?**

Open `index.html` — double-click it, no server, no build step, no API key. Verified working from `file://`.

## What it does

Five questions, at most, as an accordion — the open one is the only one expanded, the rest collapse to a one-line summary of your answer and reopen on click:

1. **What are you building** — sets which benchmarks count for the ranking
2. **How you want to run it** — hosted API, your own hardware, or both; plus open-weights and data-residency requirements
3. **Your machine** — one-click browser probe, a paste-back shell one-liner, or a manual form (hidden entirely if you chose API-only)
4. **Volume** — requests/day, token shape, cacheable prefix share
5. **Hard constraints** — context floor, latency, required capabilities

Only question 1 is required. Everything else has a working default and results update live.

## How the answer is presented

**One recommendation, stated in a sentence.** The top of the page names a model and explains in plain prose why it won — what it scores, what it costs, whether it fits your machine — with four supporting numbers underneath. Not a table you have to interpret.

**Two trades, if they exist.** "If quality matters more" and "if cost matters more" cards, each naming the concrete gain and what it costs you. The cheaper option is only offered if it is still within 12 quality points — a free endpoint 70 points down is noise, not an alternative.

**Everything else is collapsed.** Shortlist, cost breakdown, hardware analysis and eliminations are separate sections you open when you want them.

**Deep dive without losing your place.** Clicking any model opens a side drawer with the full score derivation, per-index benchmark bars, pricing at your volume, capabilities, licence and a per-quantization fit table. Escape or click-away closes it; the page never scrolls or re-renders underneath you.

**Every piece of jargon has a `?`.** Cacheable prefix, KV cache, Q4_K_M, duty cycle, break-even, agentic index, partly-measured, offload — all explained on hover, focus or tap.

**"Use this — show me how"** opens a generated setup page for the chosen model, scoped to the brief you filled in: install and auth, a working call, and the cost traps specific to that model. Three paths where they exist — run it locally (Ollama / llama.cpp / vLLM at the quantization that fits your machine), OpenRouter (one API shape for the whole catalog), or the provider's native SDK. The "before you ship" checklist is generated from the model's own properties: what caching would save at its cache rate, what the batch tier would save, whether the two price sources disagree, whether its benchmark coverage is thin, and what its licence actually is.

**Refresh models** in the header re-reads all sources, bypassing both the 24-hour local cache and the browser's HTTP cache, and reports what changed. The status pill shows how stale the data is.

## Picking your machine

Three taps, no terminal: **Apple Silicon / NVIDIA / AMD / Cloud GPU / No GPU** → the specific chip or card → how much memory. VRAM and bandwidth are filled in from a built-in table; for unified-memory machines you pick the memory, because only you know it.

The one-click browser probe is still there as a shortcut, but demoted — it can only ever be an estimate, since browsers cap reported RAM at 8 GB and never expose VRAM. The terminal one-liner, which *is* exact, now lives under "Fine-tune specs" for when the numbers have to be right.

The interface also adapts to the mode: in "My machine" the shortlist's headline number becomes tokens/sec and whether it fits, with the API price demoted to a reference, because that is the number that actually decides it.

## Where the data comes from

Fetched live on load, cached in `localStorage` for 24 hours, refreshed in the background. All three endpoints are public, need no key, and send permissive CORS headers (checked with `Origin: null`, which is what a `file://` page sends).

| Source | Endpoint | Supplies |
|---|---|---|
| OpenRouter | `openrouter.ai/api/v1/models` | ~430 models: pricing incl. cache-read/write and long-context tiers, context length, modalities, supported parameters, open-weight flag, Artificial Analysis intelligence/coding/agentic indices |
| AI Pricing Guru | `aipricing.guru/api/pricing.json` | Independent **first-party provider list prices** with a source URL per model, and legacy/preview status |
| Hugging Face | `huggingface.co/api/models/{id}` | Exact parameter counts and license tags for open models — fetched lazily, only for the shortlist |

No provider is promoted. The ranking is a pure function of your answers and those numbers.

## Design decisions worth knowing

**Prices are cross-checked, not reconciled.** An aggregator's resale price is not always the provider's list price. Where the two sources differ by more than 5% the app shows both and links the provider's page rather than silently picking one. This fires on real models today.

**Partial benchmark coverage is penalised, not papered over.** Only about a quarter of scored models publish all three indices; most publish coding alone. The scorer renormalises the task weights over whichever indices a model actually has, discounts the result by how much of the task's criteria are genuinely measured, and labels the model "partly measured". Nothing is substituted for a missing score.

**Local throughput is derived, not looked up.** Decode is memory-bandwidth bound, so tokens/sec ≈ bandwidth × 0.72 ÷ active-weight bytes, using active parameters for MoE models. Memory need is weights at the given quantization × a KV-cache factor that scales with your context. Both are estimates; a real serving stack will differ.

**Electricity counts the marginal draw.** On a machine you already own, only the power *above idle* is charged against the LLM — you pay the idle load anyway. Enter a hardware cost and it switches to full draw including idle, since then the machine exists for this job.

**A `:batch` row is only treated as a batch tier when it is actually cheaper.** For several providers OpenRouter's batch variant is priced *above* the base rate; those are dropped rather than presented as a discount.

**Choosing "My machine" changes the ranking, not just the display — and fitting is a filter, not a score.** A model whose size is known and which does not fit is removed and listed under "what was ruled out", so you can still see what a bigger machine would buy. Among the models that *do* fit, quality and cost decide exactly as they do in hosted mode; the only remaining adjustment is a small penalty for a model that only runs by offloading to system RAM, because every token then crosses a much slower bus. A model whose parameter count cannot be looked up is kept rather than guessed away.

This used to be a flat +25 bonus for fitting, which on a 0–100 scale outranked roughly 65 points of benchmark: asking for local extraction on a 24 GB card returned a model scoring **11 of 100** ahead of one scoring **82**. Fitting is a yes/no constraint and is now modelled as one.

**The cost axis has a floor, so a rounding error cannot outbid the benchmarks.** Cost is scored log-scaled across the surviving pool, which used to stretch to the full 0–100 however small the absolute numbers were. At 1,000 requests a day that let a model scoring 49 beat one scoring 82 in order to save **$4.65 a month**. Monthly spends below `COST_FLOOR` ($20) now tie at the top of the cost axis and quality decides; above it the scale behaves as before, so at real volume price still dominates as it should.

**When your machine is the constraint, the verdict says what that costs you.** In "My machine" mode the tool also reports the best model you could rent instead and the ability gap between them, so the self-host-or-rent decision is on the screen rather than implied.

## Refreshing / hacking

- Force a refetch: clear the `llmfinder.catalog.v1` key in localStorage, or hard-reload after 24h.
- Add an accelerator: append to the `GPUS` table (`vram`, `bw` = memory bandwidth GB/s, `w` = load watts, `idle`, `uni` for unified memory).
- Add or retune a task: edit `TASKS` — `w` is the weighting over the three indices, `cost` is baseline cost sensitivity, `need` is a hard capability filter, `kw` drives the free-text inference.

- Reword an explainer: every tooltip lives in the `HELP` dictionary, keyed by the `data-help` attribute.

The file is organised in labelled sections: `DATA` → `HARDWARE` → `COST` → `TASKS & SCORING` → `HELP` → `RENDER` → `DRAWER` → `TOOLTIPS` → `WIRING`.

## Caveats

Prices change without notice — verify with the provider before committing budget. Several "open weights" licenses carry commercial conditions (Kimi K3 and GLM-5.3 both report `other`); read the license you intend to ship on. Benchmark indices are one vendor's methodology, not ground truth for your workload — treat the shortlist as a starting point for your own eval, not a verdict.
