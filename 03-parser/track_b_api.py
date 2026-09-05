"""Track B -- paid API via OpenRouter. PDF -> Claude with a forced tool call.

!! RUN END TO END, 2026-09-06: 100 documents via OpenRouter, zero errors,
!!   8.6 minutes. 100.0% normalised accuracy at 5.0s/doc -- every field, every
!!   tier -- and validator precision 100% with ZERO false alarms on 60 clean
!!   documents. The most accurate AND the fastest of the three tracks.
!! It scored 100% precisely BECAUSE it refused to fix anything: on the two
!!   cgst_wrong_math documents it returned the broken figures exactly as printed
!!   and let validators.py catch them. That is rule 2 working. See M3.

Cost: MEASURED. The 100-document run billed $1.15 -- $0.0115/doc, about
Rs.1.01 at 88/USD, so ~Rs.101 for the batch and ~Rs.10.1 LAKH at 1M docs/month.

We had ESTIMATED Rs.0.75/doc from published per-token rates. The real number is
26% higher, because a one-page invoice costs 3,562 prompt + 504 completion
tokens, not the 2,500 + 350 we assumed -- both about 43% off. At a million
documents a month that estimate was wrong by Rs.2.6 LAKH.

That is gotcha G6, and we walked into it ourselves: we had the accuracy for days
before we had the bill. This file now sends usage:{include:true} and records
cost_usd, the token counts and gen_id per document, so nobody has to guess
again. Cost is a measurement, not an estimate.

Needs: OPENROUTER_API_KEY in the repo-root .env (auto-loaded by common.py).
One key gets you every model on the platform, which is the point -- swap
--model and re-run the same eval to compare vendors on your own documents.

Run:  python track_b_api.py --dataset ../02-generator/dataset [--limit 5]

WHY OPENROUTER AND NOT THE ANTHROPIC SDK: OpenRouter is an OpenAI-compatible
gateway, so this file speaks the OpenAI wire format even though a Claude model
answers. That is deliberate and it is the lesson: the PATTERN below is portable,
the vendor is not. Same three ideas, different spelling.

WHY tool_choice IS FORCED: it makes the model answer *through your schema*
instead of writing prose you have to dig JSON out of -- no markdown fences, no
coerce_json(). Be precise about what that buys: a forced tool call guarantees a
tool_calls entry, NOT that its arguments validate. The parameter that guarantees
validation is strict mode, which needs additionalProperties:false plus required,
which pydantic's model_json_schema() does not emit. So the shape is guaranteed by
construction and correctness is still checked by Invoice.model_validate() in
common.py. Structured output removes a class of parsing bugs; it does not remove
your validation layer.

WHY engine="native": OpenRouter defaults to an OCR parser for PDFs. Our invoices
are born-digital -- there is a perfect text layer already -- so OCR would be
slower, costlier and less accurate, all three at once. That is gotcha G4, and it
is a real setting you have to opt out of, not a hypothetical.

DETERMINISM: there is no temperature knob. Sampling parameters were removed on
current Anthropic models and sending one returns an error -- the old
'temperature=0 always' advice still holds for Ollama in Track A, but it is
provider-specific, not a law.

Do not soften rule 2 of the shared prompt, or the model will start 'helpfully'
fixing the broken tax math the chaos engine planted, and your eval will silently
rot. That failure mode is M3.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from common import b64, run_track
from schema import EXTRACTION_PROMPT, INVOICE_JSON_SCHEMA

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# Override without editing this file: --model, or OPENROUTER_MODEL in .env.
# Swapping to a cheaper model and re-running the eval IS the workshop -- that
# comparison is the whole point of having one harness. Any tool-capable model on
# OpenRouter works; try anthropic/claude-haiku-4.5 for a fifth of the price.
MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-5")

# Ceiling on the generated tool call. A 20-item invoice can approach this; when
# it is hit the API returns finish_reason="length" and a TRUNCATED arguments
# string, which is why parse_one checks finish_reason below. Without that check
# a truncation arrives later as an unexplained pydantic ValidationError.
MAX_TOKENS = int(os.environ.get("TRACK_B_MAX_TOKENS", "2000"))

TIMEOUT = float(os.environ.get("TRACK_B_TIMEOUT", "120"))

# What the API said the last call cost. run_track() merges this into each JSONL
# row, so cost/doc is measured per document rather than estimated once and hoped
# over. Reset per call; never let a stale value leak into the next row.
LAST_USAGE: dict = {}


def _usage() -> dict:
    return dict(LAST_USAGE)


def parse_one(pdf: Path) -> dict:
    import httpx  # already present via the anthropic package; listed in requirements

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Put it in the repo-root .env "
            "(beside setup.sh), not in 03-parser/."
        )

    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        # OpenAI-shaped tool definition. Note `parameters` here where the
        # Anthropic SDK says `input_schema` -- same JSON Schema, different key.
        "tools": [{
            "type": "function",
            "function": {
                "name": "record_invoice",
                "description": "Record the extracted invoice fields verbatim.",
                "parameters": INVOICE_JSON_SCHEMA,
            },
        }],
        # Forced: the model cannot answer in prose, only through the schema.
        "tool_choice": {"type": "function", "function": {"name": "record_invoice"}},
        # Ask OpenRouter to return token counts AND the actual charge for this
        # call. Without this you get an accuracy number and no idea what it
        # cost -- which is gotcha G6, and we shipped exactly that mistake once.
        "usage": {"include": True},
        # Send the PDF to the model itself rather than OCR-ing it first. See the
        # docstring -- the default here is an OCR engine, and for born-digital
        # PDFs that is the wrong tool.
        "plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "file",
                 "file": {"filename": pdf.name,
                          "file_data": f"data:application/pdf;base64,{b64(pdf)}"}},
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }],
    }

    r = httpx.post(ENDPOINT, timeout=TIMEOUT, json=payload, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Optional attribution headers OpenRouter uses for its rankings.
        "HTTP-Referer": "https://github.com/saarthios/agentic-invoice-pipeline",
        "X-Title": "Build Agentic Workflows",
    })
    r.raise_for_status()
    body = r.json()

    # OpenRouter can return a 200 with an error object in the body.
    if "error" in body and not body.get("choices"):
        raise ValueError(f"OpenRouter error: {json.dumps(body['error'])[:300]}")

    choice = body["choices"][0]
    if choice.get("finish_reason") == "length":
        raise ValueError(
            f"hit max_tokens={MAX_TOKENS} -- the tool call was truncated mid-JSON. "
            "Raise TRACK_B_MAX_TOKENS; do not blame the schema."
        )

    u = body.get("usage") or {}
    LAST_USAGE.clear()
    LAST_USAGE.update({
        "gen_id": body.get("id"),                      # look this up later at
                                                       # /api/v1/generation?id=
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "cost_usd": u.get("cost"),                     # present because of usage.include
    })

    calls = (choice.get("message") or {}).get("tool_calls") or []
    if not calls:
        raise ValueError(
            f"no tool_calls in response (finish_reason={choice.get('finish_reason')}). "
            "If the model returned prose, tool_choice was not honoured -- check the model "
            "supports tool_choice at openrouter.ai/models."
        )
    # arguments is a JSON *string*, not an object -- that is the OpenAI shape.
    return json.loads(calls[0]["function"]["arguments"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="../02-generator/dataset")
    ap.add_argument("--limit", type=int, default=None,
                    help="smoke-test on first N docs before spending on 100")
    ap.add_argument("--model", default=None,
                    help="any tool-capable OpenRouter model, e.g. anthropic/claude-haiku-4.5")
    args = ap.parse_args()
    if args.model:
        MODEL = args.model
    print(f"[B] OpenRouter -> {MODEL}")
    out = "outputs_track_b.jsonl"
    run_track("B-api", args.dataset, "pdf", parse_one, out, args.limit, extra=_usage)

    # Measured cost, not estimated. This is the number to hand to eval.py.
    rows = [json.loads(l) for l in open(out, encoding="utf-8")]
    priced = [r for r in rows if r.get("cost_usd") is not None]
    if priced:
        usd = sum(r["cost_usd"] for r in priced)
        pt = sum(r.get("prompt_tokens") or 0 for r in priced)
        ct = sum(r.get("completion_tokens") or 0 for r in priced)
        inr = float(os.environ.get("USD_INR", "88"))
        per = usd / len(priced)
        print(f"\n[B] MEASURED over {len(priced)} docs: {pt:,} prompt + {ct:,} completion tokens")
        print(f"[B] ${usd:.4f} total  |  ${per:.5f}/doc  =  Rs.{per*inr:.2f}/doc")
        print(f"[B] at 1M docs/month: Rs.{per*inr*1_000_000:,.0f}")
        print(f"[B] grade it with:  --cost-per-doc {per*inr:.2f}")
    else:
        print("\n[B] no usage returned -- cost stays an estimate.")
