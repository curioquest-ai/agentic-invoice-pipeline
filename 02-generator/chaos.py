"""Chaos engine: turn clean records into realistically messy ones -- and LOG IT.

GOTCHA (G7 "Chaos that is uniform random noise", same wording as the README):
real-world error distributions cluster -- dates, digit transpositions, missing
IDs -- they're not uniform random noise. A chaos engine that models realistic
failure modes is worth 10x one that sprinkles random typos.

Design rules:
  1. Chaos happens BEFORE printing. Whatever we corrupt is what gets printed,
     so ground truth (== printed values) stays honest for a verbatim parser.
  2. Every corruption is appended to record["corruptions"], and the tier is
     stored in record["tier"]. The eval slices by these in the 15:00 block.
  3. Tiers and mix (n=100): clean 60 / ok 20 / bad 12 / broken 8.

Tier semantics:
  clean  -- nothing touched
  ok     -- cosmetic noise a good parser should sail through (formats, case, spacing)
  bad    -- data-entry damage: values are wrong but internally the doc may still be consistent-ish
  broken -- business-rule violations our validators MUST catch (math, duplicates)
"""
from __future__ import annotations

import copy
import random

TIER_MIX = [("clean", 60), ("ok", 20), ("bad", 12), ("broken", 8)]  # per 100

_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%y", "%d %b %Y", "%d-%b-%Y", "%d/%m/%y"]

_HINDI_ITEMS = {"HDMI Cable 2m": "एचडीएमआई केबल 2मी", "A4 Copier Paper 500s": "ए4 कॉपियर पेपर 500",
                "Packing Tape 48mm": "पैकिंग टेप 48मिमी"}


def _log(rec: dict, tag: str) -> None:
    rec.setdefault("corruptions", []).append(tag)


def _reformat_date(rec: dict, rng: random.Random) -> None:
    from datetime import datetime
    d = datetime.strptime(rec["date"], "%Y-%m-%d")
    rec["date"] = d.strftime(rng.choice(_DATE_FORMATS))
    _log(rec, "date_reformatted")


def _swap_digits(num: float) -> float:
    """Transpose the first UNEQUAL adjacent digit pair: 12450 -> 21450.
    Skipping equal pairs matters: swapping '1' and '1' is a logged corruption
    that changes nothing -- your validator recall metric then reports a miss
    that never existed. A chaos engine must guarantee its chaos is real."""
    s = f"{num:.2f}"
    digits = [i for i, c in enumerate(s) if c.isdigit()]
    for a, b in zip(digits, digits[1:]):
        if s[a] != s[b]:
            ls = list(s)
            ls[a], ls[b] = ls[b], ls[a]
            return float("".join(ls))
    return float(s[:-1] + ("7" if s[-1] != "7" else "3"))  # all digits equal: nudge last paisa digit


def corrupt(record: dict, tier: str, rng: random.Random, prev_invoice_no: str | None) -> dict:
    rec = copy.deepcopy(record)
    rec["tier"] = tier
    rec["corruptions"] = []

    if tier == "clean":
        return rec

    if tier == "ok":
        _reformat_date(rec, rng)
        ops = rng.sample(["lc_gstin", "spacing", "trailing_space"], k=rng.randint(1, 2))
        if "lc_gstin" in ops:
            rec["gstin"] = rec["gstin"].lower(); _log(rec, "gstin_lowercased")
        if "spacing" in ops:
            rec["vendor"] = rec["vendor"].replace(" ", "  ", 1); _log(rec, "vendor_double_space")
        if "trailing_space" in ops:
            rec["invoice_no"] = rec["invoice_no"] + " "; _log(rec, "invoice_no_trailing_space")
        return rec

    if tier == "bad":
        _reformat_date(rec, rng)
        op = rng.choice(["drop_gstin", "digit_swap_total", "truncate_vendor"])
        if op == "drop_gstin":
            rec["gstin"] = None; _log(rec, "gstin_missing")
        elif op == "digit_swap_total":
            # A data-entry transposition in the grand total. Note: this ALSO
            # breaks the math -- which is realistic; transposed totals don't
            # stay consistent. Validators will flag TOTAL_MISMATCH.
            rec["total"] = _swap_digits(rec["total"]); _log(rec, "total_digit_swap")
        else:
            rec["vendor"] = rec["vendor"][: max(6, len(rec["vendor"]) // 2)]; _log(rec, "vendor_truncated")
        return rec

    if tier == "broken":
        op = rng.choice(["tax_math", "dup_invoice", "hindi_item"])
        if op == "tax_math":
            rec["cgst"] = round(rec["cgst"] * rng.choice([0.5, 2.0]), 2); _log(rec, "cgst_wrong_math")
        elif op == "dup_invoice" and prev_invoice_no:
            rec["invoice_no"] = prev_invoice_no; _log(rec, "duplicate_invoice_no")
        else:
            for it in rec["items"]:
                if it["description"] in _HINDI_ITEMS:
                    it["description"] = _HINDI_ITEMS[it["description"]]; _log(rec, "item_desc_hindi"); break
            else:
                rec["cgst"] = round(rec["cgst"] * 2.0, 2); _log(rec, "cgst_wrong_math")
        return rec

    raise ValueError(f"unknown tier {tier}")


def tier_sequence(n: int, rng: random.Random) -> list[str]:
    seq = []
    for tier, per100 in TIER_MIX:
        seq += [tier] * round(n * per100 / 100)
    seq = seq[:n] + ["clean"] * (n - len(seq))
    rng.shuffle(seq)
    return seq
