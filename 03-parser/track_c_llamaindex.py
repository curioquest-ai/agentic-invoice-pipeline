"""Track C -- framework path. PDF -> LlamaParse (markdown) -> LLM extraction.

!! NEVER EXECUTED, AND NOT INSTALLED. The llama-index lines in requirements.txt
!! are commented out on purpose (the install is heavy), so nothing here has ever
!! run. It has been corrected from the provider docs, not from a green test.

Run:  pip install llama-cloud-services llama-index-core llama-index-llms-ollama
      python track_c_llamaindex.py --dataset ../02-generator/dataset [--limit 5]

ONE KEY, NOT TWO. Stage 2 defaults to your LOCAL Ollama model -- the same one
Track A already pulled -- so the only credential this track needs is
LLAMA_CLOUD_API_KEY for LlamaParse. Want the paid path instead?

      pip install llama-index-llms-anthropic
      TRACK_C_LLM=anthropic python track_c_llamaindex.py --limit 5

That default is deliberate. Track C exists to answer ONE question: what does the
framework's document-conversion stage buy me? Keep stage 2 identical to Track A
-- same local model, same schema, same eval -- and the only variable left is
LlamaParse vs pdfplumber. Bolt a paid API onto stage 2 and you have mixed in
Track B's question and can no longer tell which stage moved your score.

THREE THINGS FAIL BEFORE THE NETWORK DOES -- check them in this order:

  1. ModuleNotFoundError. Nothing is installed until you uncomment
     requirements.txt and pip install. This is failure #1 for everyone.
  2. The model id, inside llama-index -- not inside the API. The llama-index
     LLM packages ship their own model registries and look the id up at
     construction. A release older than the model you name raises there, before
     a single request is sent. Upgrade the package, or pass --model with an id
     the installed version knows.
  3. Credentials. LLAMA_CLOUD_API_KEY in the repo-root .env (plus an Anthropic
     key ONLY if you set TRACK_C_LLM=anthropic).

Three unpinned packages with no version floors is itself the lesson: this is the
framework tax, and you are paying it before you extract a single field.

Cost: Rs.0 on the default path -- LlamaParse's free tier covers today (~1000
pages/day at time of writing; verify at cloud.llamaindex.ai) and stage 2 runs on
your own machine. With TRACK_C_LLM=anthropic, stage 2 costs whatever Track B
costs, because it is the same model.

WHAT THE ABSTRACTION COSTS YOU, and this is worth saying out loud: Track A hands
Ollama the JSON schema directly via `format=`, which is constrained decoding --
the tokens literally cannot leave the schema. Going through llama-index's
structured_predict you get the framework's own structured-output handling
instead, which on a small local model is prompt-and-parse rather than a decoding
guarantee. Same model, same schema, weaker guarantee. If Track C scores below
Track A on identical hardware, look here before you blame LlamaParse.

What this track teaches that A and B don't: the two-stage enterprise pattern.
Stage 1 (LlamaParse) turns ANY document -- scans, tables, 40-page contracts --
into clean markdown. Stage 2 is plain text extraction against our schema.
For today's one-page invoices it is arguably overkill -- our PDFs are
born-digital, so pdfplumber already reads a perfect text layer for free (that is
gotcha G4, and Track A proves it at 8 s/doc). Say that out loud at demo time,
with your cost column open. For real document variety -- scans, rotated tables,
handwriting -- stage 1 is the part you would not want to build. The framework
buys you stage 1; the schema and validators are still yours.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from common import run_track
from schema import EXTRACTION_PROMPT, Invoice

# Stage 2 backend. Default is your local Ollama model, so this track needs no
# LLM key at all -- see the docstring for why that is the interesting default.
LLM_BACKEND = os.environ.get("TRACK_C_LLM", "ollama").lower()

_DEFAULT_MODEL = {"ollama": "llama3.2:3b", "anthropic": "claude-sonnet-5"}

# Same override story as Track A/B: --model, or TRACK_C_MODEL in .env. If
# llama-index does not recognise the id (see the docstring), this is the knob.
MODEL = os.environ.get("TRACK_C_MODEL", _DEFAULT_MODEL.get(LLM_BACKEND, "llama3.2:3b"))


def _make_llm():
    """Stage 2. Local by default; paid only if you ask for it."""
    if LLM_BACKEND == "ollama":
        from llama_index.llms.ollama import Ollama  # pip install llama-index-llms-ollama
        # LlamaParse + a local model is a slow pair; the default 30s timeout
        # trips on longer documents and reads as a hang.
        return Ollama(model=MODEL, request_timeout=180.0)
    if LLM_BACKEND == "anthropic":
        from llama_index.llms.anthropic import Anthropic  # pip install llama-index-llms-anthropic
        # No temperature: sampling parameters return HTTP 400 on current
        # Anthropic models. Track A still sets temperature=0 for Ollama -- that
        # advice is provider-specific, not universal.
        return Anthropic(model=MODEL)
    raise ValueError(f"TRACK_C_LLM must be 'ollama' or 'anthropic', got {LLM_BACKEND!r}")


def parse_one(pdf: Path) -> dict:
    from llama_cloud_services import LlamaParse
    from llama_index.core.prompts import PromptTemplate

    md = LlamaParse(result_type="markdown").load_data(str(pdf))   # stage 1
    text = "\n\n".join(d.text for d in md)

    llm = _make_llm()                                             # stage 2
    # structured_predict: LlamaIndex drives the tool-call against our Pydantic
    # model directly -- same guarantee as Track B, one abstraction up.
    tmpl = PromptTemplate(EXTRACTION_PROMPT + "\n\nDOCUMENT (markdown):\n{doc_text}")
    inv = llm.structured_predict(Invoice, tmpl, doc_text=text)
    return inv.model_dump()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="../02-generator/dataset")
    ap.add_argument("--limit", type=int, default=None,
                    help="smoke-test on first N docs before spending on 100")
    ap.add_argument("--model", default=None,
                    help="override the stage-2 model (use this if llama-index rejects the default id)")
    ap.add_argument("--llm", default=None, choices=["ollama", "anthropic"],
                    help="stage-2 backend. Default ollama (no key, runs locally)")
    args = ap.parse_args()
    if args.llm:
        LLM_BACKEND = args.llm
        MODEL = _DEFAULT_MODEL[LLM_BACKEND]
    if args.model:
        MODEL = args.model
    print(f"[C] stage 1 LlamaParse -> stage 2 {LLM_BACKEND}:{MODEL}")
    run_track("C-llamaindex", args.dataset, "pdf", parse_one, "outputs_track_c.jsonl", args.limit)
