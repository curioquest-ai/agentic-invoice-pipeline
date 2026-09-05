"""Track A -- free / local. PNG -> Qwen2.5-VL via Ollama, structured output.

Cost: Rs.0. Needs 16 GB RAM (8 GB free) for the 7b vision model -- measured on an
8 GB M2 it does not fit the Metal budget at all, and a 3b runs at 0.29 tok/s,
~30 min/doc. On 8 GB use --text-fallback, which is faster AND more accurate here.
`ollama pull qwen2.5vl:7b` BEFORE the venue (~6GB, ~30 min; venue wifi is where
model pulls go to die).

Run:  python track_a_local.py --dataset ../02-generator/dataset [--limit 5]

Ollama's `format` parameter accepts a full JSON schema -- the open-source
equivalent of tool-calling. Use it. temperature=0 here: extraction is a
transcription task; sampling variety is a bug, not creativity. Note this knob is
provider-specific -- current Anthropic models removed sampling parameters
altogether and return 400 if you send one, so Tracks B and C control determinism
differently. The principle travels; the parameter does not.

Fallback inside this track (weak laptop / no vision model): pdfplumber text
extraction + a small text model. See extract_text_fallback() -- and note the
gotcha: for born-digital PDFs like ours, pdfplumber beats OCR entirely.
OCR (tesseract/paddle) is for scans; check what you have before you rasterize.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common import b64, coerce_json, run_track
from schema import EXTRACTION_PROMPT, INVOICE_JSON_SCHEMA

# Override without editing this file: --model, or export/put in .env.
#   16 GB free : qwen2.5vl:7b  (default -- best accuracy)
#    8 GB free : qwen2.5vl:3b  (7b cannot fit a ~4.8 GiB Metal budget)
MODEL = os.environ.get("TRACK_A_MODEL", "qwen2.5vl:7b")

# Text fallback model. Was llama3.1:8b (4.9 GB) -- too big for the very
# laptops the fallback exists to rescue. A 3b fits entirely in GPU.
TEXT_MODEL = os.environ.get("TRACK_A_TEXT_MODEL", "llama3.2:3b")

# Hard ceiling on generated tokens. Constrained decoding guarantees VALID
# JSON, not TERMINATING JSON: with an unbounded items[] a model can emit
# array elements forever. Observed: 30,215 tokens over 33 minutes on a
# one-line-item invoice, with no error, because a hang is not an exception
# and common._with_retry therefore never fires. A runaway doc must FAIL.
NUM_PREDICT = int(os.environ.get("TRACK_A_NUM_PREDICT", "1024"))

# Context window for the vision path. Our A4-at-150-DPI invoice PNG costs ~2772
# vision tokens; add the prompt and you are at 2983 of Ollama's 4096 default,
# leaving barely 1100 for output. Raise it so prompt+image+output always fit --
# a context overflow is silent, and a silently truncated document is exactly the
# failure this pipeline exists to catch.
NUM_CTX = int(os.environ.get("TRACK_A_NUM_CTX", "8192"))


def parse_one(png: Path) -> dict:
    import ollama  # pip install ollama

    resp = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": EXTRACTION_PROMPT, "images": [b64(png)]}],
        format=INVOICE_JSON_SCHEMA,          # constrained decoding to our schema
        # num_ctx must cover PROMPT + IMAGE + OUTPUT. Measured on our A4-at-150-DPI
        # PNGs: prompt+image = 2983 tokens. Ollama's 4096 default would leave only
        # ~1100 for generation, and an overflow here does not raise -- it silently
        # truncates the context and you get a plausible, wrong answer.
        options={"temperature": 0, "num_predict": NUM_PREDICT, "num_ctx": NUM_CTX},
    )
    return coerce_json(resp["message"]["content"])


def extract_text_fallback(pdf: Path) -> dict:
    """Text-only path: pdfplumber + small text LLM. Same prompt, same schema."""
    import ollama
    import pdfplumber  # pip install pdfplumber

    with pdfplumber.open(str(pdf)) as f:
        text = "\n".join(page.extract_text() or "" for page in f.pages)
    resp = ollama.chat(
        model=TEXT_MODEL,
        messages=[{"role": "user", "content": f"{EXTRACTION_PROMPT}\n\nDOCUMENT TEXT:\n{text}"}],
        format=INVOICE_JSON_SCHEMA,
        options={"temperature": 0, "num_predict": NUM_PREDICT},
    )
    return coerce_json(resp["message"]["content"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="../02-generator/dataset")
    ap.add_argument("--limit", type=int, default=None, help="parse only the first N docs (smoke test)")
    ap.add_argument("--text-fallback", action="store_true")
    ap.add_argument("--model", default=None,
                    help="override the ollama model for this run (e.g. qwen2.5vl:3b on an 8 GB laptop)")
    args = ap.parse_args()
    if args.model:
        MODEL = TEXT_MODEL = args.model
    if args.text_fallback:
        run_track("A-local-text", args.dataset, "pdf", extract_text_fallback,
                  "outputs_track_a.jsonl", args.limit)
    else:
        run_track("A-local", args.dataset, "png", parse_one,
                  "outputs_track_a.jsonl", args.limit)
