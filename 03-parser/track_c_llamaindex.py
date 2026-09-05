"""Track C -- framework path. PDF -> LlamaParse (markdown) -> LLM extraction.

!! NEVER EXECUTED, AND NOT INSTALLED. The llama-index lines in requirements.txt
!! are commented out on purpose (the install is heavy), so nothing here has ever
!! run. It has been corrected from the provider docs, not from a green test.

Run:  pip install llama-cloud-services llama-index-core llama-index-llms-anthropic
      python track_c_llamaindex.py --dataset ../02-generator/dataset [--limit 5]

THREE THINGS FAIL BEFORE THE NETWORK DOES -- check them in this order:

  1. ModuleNotFoundError. Nothing is installed until you uncomment
     requirements.txt and pip install. This is failure #1 for everyone.
  2. The model id, inside llama-index -- not inside the API.
     llama-index-llms-anthropic ships its own model->context-window registry and
     looks the id up in Anthropic(...). A release older than the model you name
     raises there, before a single request is sent. If that happens, upgrade
     llama-index-llms-anthropic or name a model the installed version knows.
  3. Credentials. LLAMA_CLOUD_API_KEY *and* an Anthropic key, both in the
     repo-root .env.

Three unpinned packages with no version floors is itself the lesson: this is the
framework tax, and you are paying it before you extract a single field.

Cost: LlamaParse free tier covers today (~1000 pages/day at time of writing --
verify current limits at cloud.llamaindex.ai). The extraction step costs the
same as Track B, since it is the same model.

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

# Same override story as Track A/B: --model, or TRACK_C_MODEL in .env. If
# llama-index does not recognise the id (see the docstring), this is the knob.
MODEL = os.environ.get("TRACK_C_MODEL", "claude-sonnet-5")


def parse_one(pdf: Path) -> dict:
    from llama_cloud_services import LlamaParse
    from llama_index.core.prompts import PromptTemplate
    from llama_index.llms.anthropic import Anthropic

    md = LlamaParse(result_type="markdown").load_data(str(pdf))
    text = "\n\n".join(d.text for d in md)

    # No temperature: sampling parameters return HTTP 400 on current Anthropic
    # models. Track A still sets temperature=0 for Ollama -- that advice is
    # provider-specific, not universal.
    llm = Anthropic(model=MODEL)
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
                    help="override the extraction model (use this if llama-index rejects the default id)")
    args = ap.parse_args()
    if args.model:
        MODEL = args.model
    run_track("C-llamaindex", args.dataset, "pdf", parse_one, "outputs_track_c.jsonl", args.limit)
