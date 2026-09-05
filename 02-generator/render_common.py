"""Shared by 01-form/app.py (live workshop path) and checkpoints/gen_checkpoint.py
(no-browser fallback path). One template, one formatter -> both paths print
pixel-identical invoices, so checkpoint users are graded on the same documents.
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "01-form" / "templates"


def fmt_inr(n: float) -> str:
    """Indian digit grouping: 1245000.5 -> '12,45,000.50'. Realism matters --
    parsers that only know Western 3-3-3 grouping stumble here."""
    s = f"{n:.2f}"
    whole, frac = s.split(".")
    sign = ""
    if whole.startswith("-"):
        sign, whole = "-", whole[1:]
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"{sign}{whole}.{frac}"


def jinja_env() -> Environment:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    env.filters["inr"] = fmt_inr
    return env


def render_invoice_html(record: dict) -> str:
    return jinja_env().get_template("invoice_template.html").render(r=record)
