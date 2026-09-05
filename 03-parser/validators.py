"""Deterministic, code-side validation of extracted invoices.

This file is the second half of the day's core pattern:
  extraction (LLM, verbatim)  ->  validation (code, judgmental)

Every check here is boring, fast, and testable -- exactly why it must NOT be
delegated to the model. An LLM asked to 'extract and verify' will quietly
repair broken tax math into consistency, destroying the very signal
(data-entry errors) this pipeline exists to surface.

Usage:
    from validators import validate
    flags = validate(invoice)   # list[str], empty == clean
"""
from __future__ import annotations

import re
from datetime import datetime

from schema import Invoice

GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

# Real-world Indian date formats seen in the wild (and in our chaos engine).
DATE_FORMATS = [
    "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
    "%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%Y-%m-%d",
]


def gstin_checksum_ok(gstin: str) -> bool:
    """Mod-36 checksum over the first 14 chars; 15th char is the check digit.

    Factor alternates 1,2,1,2... ; each product contributes quotient+remainder
    in base 36. This is the official GSTN algorithm.
    """
    if len(gstin) != 15:
        return False
    total = 0
    for i, ch in enumerate(gstin[:14]):
        if ch not in GSTIN_CHARS:
            return False
        val = GSTIN_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += val // 36 + val % 36
    return GSTIN_CHARS[(36 - total % 36) % 36] == gstin[14]


def date_parseable(s: str) -> bool:
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


def validate(inv: Invoice, tol: float = 0.05) -> list[str]:
    """Return a list of validation flags. Empty list == passes all checks.

    tol absorbs paise-level rounding; anything beyond it is a real mismatch.
    """
    flags: list[str] = []

    # -- GSTIN ---------------------------------------------------------------
    if inv.gstin is None or not inv.gstin.strip():
        flags.append("GSTIN_MISSING")
    else:
        g = inv.gstin.strip()
        if g != g.upper():
            flags.append("GSTIN_LOWERCASE")   # normalizable, but flag it
        if not GSTIN_RE.match(g.upper()):
            flags.append("GSTIN_MALFORMED")
        elif not gstin_checksum_ok(g.upper()):
            flags.append("GSTIN_CHECKSUM_FAIL")

    # -- Line-item math ------------------------------------------------------
    for i, it in enumerate(inv.items):
        if abs(it.qty * it.rate - it.amount) > tol:
            flags.append(f"ITEM_{i}_MATH_MISMATCH")

    # -- Tax math ------------------------------------------------------------
    subtotal = sum(it.amount for it in inv.items)
    if abs(inv.cgst - inv.sgst) > tol:
        flags.append("CGST_SGST_UNEQUAL")     # intra-state GST splits equally
    if abs((subtotal + inv.cgst + inv.sgst) - inv.total) > tol:
        flags.append("TOTAL_MISMATCH")

    # -- Date ----------------------------------------------------------------
    if not date_parseable(inv.date):
        flags.append("DATE_UNPARSEABLE")

    return flags


if __name__ == "__main__":
    # Self-test: generate a valid GSTIN and verify round-trip.
    body = "29ABCDE1234F1Z"
    total = 0
    for i, ch in enumerate(body):
        v = GSTIN_CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += v // 36 + v % 36
    g = body + GSTIN_CHARS[(36 - total % 36) % 36]
    assert gstin_checksum_ok(g), g
    assert not gstin_checksum_ok(g[:-1] + ("0" if g[-1] != "0" else "1"))
    print("validators self-test OK:", g)
