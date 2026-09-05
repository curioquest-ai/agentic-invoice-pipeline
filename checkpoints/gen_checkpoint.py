"""Checkpoint dataset generator -- the no-browser fallback path.

Same records, same chaos, same Jinja template as the live bot path, rendered
via WeasyPrint instead of Chromium. Exists so that (a) the facilitator can
pre-bake dataset-100.zip, and (b) anyone whose Playwright install fights the
venue wifi is unblocked in under 2 minutes:

    python gen_checkpoint.py --n 100 --seed 42

With the same seed, this produces the SAME ground truth as bot.py -- only the
rendering engine differs. Requires: pip install weasyprint; PNGs need
poppler's pdftoppm on PATH (apt install poppler-utils / brew install poppler).

Also writes reference_outputs.jsonl: what a PERFECT verbatim parser would
emit for each document (== the printed values, minus generator metadata).
Diff your parser against it when your score looks wrong, and use it to
smoke-test 04-eval/eval.py -- a perfect parser must score 100%.
"""
from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "02-generator"))

# Shared PNG contract with 02-generator/bot.py. A4 at 150 DPI -> 1241x1754.
PNG_DPI = 150

from chaos import corrupt, tier_sequence          # noqa: E402
from faker_in import make_record                  # noqa: E402
from render_common import render_invoice_html     # noqa: E402


def to_reference_output(rec: dict) -> dict:
    """Ground-truth record -> the schema.Invoice a perfect parser would emit."""
    return {
        "doc_id": rec["doc_id"],
        "vendor": rec["vendor"].strip(),
        "gstin": rec["gstin"],
        "invoice_no": rec["invoice_no"].strip(),
        "date": rec["date"],
        "items": rec["items"],
        "cgst": rec["cgst"], "sgst": rec["sgst"], "total": rec["total"],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(HERE / "dataset"))
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()

    from weasyprint import HTML  # imported late: heavy

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    tiers = tier_sequence(args.n, rng)
    have_pdftoppm = shutil.which("pdftoppm") is not None
    if not args.no_png and not have_pdftoppm:
        print("warning: pdftoppm not found -- skipping PNGs (Track A needs them)")

    gt = (out / "ground_truth.jsonl").open("w", encoding="utf-8")
    ref = (out / "reference_outputs.jsonl").open("w", encoding="utf-8")
    prev_invoice_no = None
    for i, tier in enumerate(tiers, start=1):
        rec = corrupt(make_record(rng, i), tier, rng, prev_invoice_no)
        rec["doc_id"] = f"inv_{i:04d}"
        gt.write(json.dumps(rec, ensure_ascii=False) + "\n")           # truth first
        ref.write(json.dumps(to_reference_output(rec), ensure_ascii=False) + "\n")
        pdf = out / f"{rec['doc_id']}.pdf"
        HTML(string=render_invoice_html(rec)).write_pdf(str(pdf))      # document second
        if not args.no_png and have_pdftoppm:
            # 150 DPI == A4 at 1241x1754. 02-generator/bot.py renders to the SAME
            # geometry (A4 viewport at device_scale_factor 150/96) so that Track A
            # grades checkpoint users and bot users on identical images. Change one
            # of these and you must change the other -- see checkpoints/README.md.
            subprocess.run(["pdftoppm", "-png", "-r", str(PNG_DPI), "-singlefile",
                            str(pdf), str(out / rec["doc_id"])], check=True)
        prev_invoice_no = rec["invoice_no"]
        if i % 20 == 0:
            print(f"  {i}/{args.n}")
    gt.close(); ref.close()
    print(f"wrote {args.n} docs + ground_truth.jsonl + reference_outputs.jsonl -> {out}")


if __name__ == "__main__":
    main()
