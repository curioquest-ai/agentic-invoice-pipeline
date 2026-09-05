"""Data-entry form + invoice renderer.

Run:  uvicorn app:app --port 8000        (from 01-form/)

Two routes matter:
  GET  /              -> the data-entry form (what the Playwright bot fills)
  GET  /invoice/{id}  -> the rendered invoice (what the bot prints to PDF)

The server renders whatever it is given, verbatim -- it never validates or
fixes input. That is deliberate: this form stands in for every legacy ERP
entry screen in every enterprise, and those don't fix your typos either.
The chaos lives in the data, not the renderer.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "02-generator"))
from render_common import jinja_env, render_invoice_html  # noqa: E402

app = FastAPI(title="Invoice Data Entry")
DB: dict[int, dict] = {}   # in-memory is fine for a workshop; restart == reset


@app.get("/", response_class=HTMLResponse)
def form() -> str:
    return jinja_env().get_template("form.html").render()


@app.post("/submit")
def submit(payload: dict) -> JSONResponse:
    new_id = len(DB) + 1
    DB[new_id] = payload
    return JSONResponse({"id": new_id})


@app.get("/invoice/{inv_id}", response_class=HTMLResponse)
def invoice(inv_id: int) -> str:
    if inv_id not in DB:
        raise HTTPException(404, "no such invoice")
    return render_invoice_html(DB[inv_id])


@app.get("/count")
def count() -> dict:
    return {"submitted": len(DB)}
