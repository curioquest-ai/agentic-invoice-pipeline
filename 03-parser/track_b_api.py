"""Track B -- paid API. PDF -> Claude with forced tool-call output.

!! NEVER EXECUTED. This file has been corrected from the provider docs but has
!! not been run against the API -- we had no key during the pre-flight. Smoke-
!! test with --limit 1 before you trust it, and before you spend on 100.

Cost: UNMEASURED. Estimated ~Rs.0.75/doc -- a one-page invoice is roughly 2,500
input + 350 output tokens, and Sonnet 5 lists at $2/$10 per million. That is
~Rs.75 for today's 100 documents. We cannot give you a real number because this
file never records `resp.usage` -- which is gotcha G6 happening to us, in our
own repo. If you want the true figure, read usage off the response and sum it.

Needs: ANTHROPIC_API_KEY in the repo-root .env (see .env.example; auto-loaded by
common.py). `pip install anthropic`.

Run:  python track_b_api.py --dataset ../02-generator/dataset [--limit 5]

Why tool_choice is forced: it makes the model answer *through your schema*
instead of writing prose you have to dig JSON out of -- no markdown fences, no
coerce_json(). Be precise about what it buys: a forced tool call guarantees a
tool_use block, NOT that block.input validates. The parameter that guarantees
validation is `strict: true`, and strict needs additionalProperties:false plus
`required`, which pydantic's model_json_schema() does not emit. So the shape is
guaranteed by construction, and correctness is still checked by
Invoice.model_validate() in common.py. Structured output removes a class of
parsing bugs; it does not remove your validation layer.

Determinism: there is no temperature knob here. Sampling parameters were removed
on current Anthropic models and sending temperature returns HTTP 400 -- the
older 'temperature=0 always' advice still holds for Ollama in Track A, but it is
provider-specific, not a law. Thinking is disabled below instead: this is a
transcription task, reasoning tokens are pure cost, and adaptive thinking is ON
by default if you omit the parameter.

Do not soften rule 2 of the shared prompt, or the model will start 'helpfully'
fixing the broken tax math the chaos engine planted, and your eval will silently
rot. That failure mode is M3.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from common import b64, run_track
from schema import EXTRACTION_PROMPT, INVOICE_JSON_SCHEMA

# Override without editing this file: --model, or TRACK_B_MODEL in .env.
# Swapping to a smaller/cheaper model and re-running the eval IS the workshop --
# that comparison is the whole point of having one harness.
MODEL = os.environ.get("TRACK_B_MODEL", "claude-sonnet-5")

# Ceiling on the generated tool call. A 20-item invoice can approach this; when
# it is hit the API returns stop_reason="max_tokens" and a TRUNCATED tool_use
# block, which is why parse_one checks stop_reason below. Without that check a
# truncation arrives later as an unexplained pydantic ValidationError.
MAX_TOKENS = int(os.environ.get("TRACK_B_MAX_TOKENS", "2000"))


def parse_one(pdf: Path) -> dict:
    import anthropic  # pip install anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        # No temperature: sampling params return 400 on current models (see the
        # docstring). Thinking off -- transcription needs none, and it is on by
        # default when omitted.
        thinking={"type": "disabled"},
        tools=[{
            "name": "record_invoice",
            "description": "Record the extracted invoice fields verbatim.",
            "input_schema": INVOICE_JSON_SCHEMA,
        }],
        tool_choice={"type": "tool", "name": "record_invoice"},   # forced: answer through the schema
        messages=[{
            "role": "user",
            "content": [
                {"type": "document",
                 "source": {"type": "base64", "media_type": "application/pdf", "data": b64(pdf)}},
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }],
    )
    if resp.stop_reason == "max_tokens":
        raise ValueError(
            f"hit max_tokens={MAX_TOKENS} -- the tool call was truncated mid-JSON. "
            "Raise TRACK_B_MAX_TOKENS; do not blame the schema."
        )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    raise ValueError(f"no tool_use block in response (stop_reason={resp.stop_reason})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="../02-generator/dataset")
    ap.add_argument("--limit", type=int, default=None, help="smoke-test on first N docs before spending on 100")
    ap.add_argument("--model", default=None,
                    help="override the model for this run (e.g. a cheaper one, then re-run the eval)")
    args = ap.parse_args()
    if args.model:
        MODEL = args.model
    run_track("B-api", args.dataset, "pdf", parse_one, "outputs_track_b.jsonl", args.limit)
