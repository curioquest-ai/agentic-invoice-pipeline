"""Playwright bot: fills the form N times, prints PDFs+PNGs, writes ground truth.

Run:  1) uvicorn app:app --port 8000     (in 01-form/)
      2) python bot.py --n 100 --seed 42 (here)

Outputs:  dataset/inv_0001.pdf, dataset/inv_0001.png, ..., dataset/ground_truth.jsonl

THE RULE OF THE DAY, in code: the ground-truth line is written BEFORE the form
is filled. Truth exists before the document does. We are not labeling
documents; we are manufacturing documents from labels. Teams that reverse
this order end up hand-labeling PDFs at midnight.

GOTCHA (G9 "Picking the automation tool by hype", same wording as the README):
OpenRPA earns its keep when the target is a Windows desktop app with no API;
for browsers, Playwright is the tool. Cross-platform, pip-installable, and it
runs on every laptop in this room.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from chaos import corrupt, tier_sequence
from faker_in import make_record

DATASET = Path(__file__).resolve().parent / "dataset"

# ---- PNG geometry (Track A's input) ----------------------------------------
# Chromium's default viewport is 1280x720 -- landscape, and far smaller than an
# A4 page. A portrait invoice rendered into it becomes small, low-DPI text, and
# the fine print Track A must read (GSTIN, HSN codes) is exactly what suffers.
#
# Worse, it silently split the room: checkpoints/gen_checkpoint.py renders PNGs
# with `pdftoppm -r 150`, i.e. 1241x1754. Anyone who unzipped the checkpoint was
# feeding their vision model 2.4x the pixels of anyone who ran this bot -- while
# the leaderboard claimed they were graded on the same documents.
#
# So: render A4 at the same 150 DPI. 794x1123 CSS px is A4 at 96 px/in; scaling
# by 150/96 = 1.5625 lands on 1241x1754, matching the checkpoint exactly.
A4_CSS_W, A4_CSS_H = 794, 1123          # A4 at 96 CSS px/inch
PNG_SCALE = 150 / 96                    # -> 150 DPI, same as pdftoppm -r 150


def fill_and_print(page, rec: dict, pdf_path: Path, png_path: Path) -> None:
    page.goto("http://localhost:8000/")
    page.fill("#vendor", rec["vendor"])
    page.fill("#city", rec["city"])
    page.fill("#gstin", rec["gstin"] or "")
    page.fill("#invoice_no", rec["invoice_no"])
    page.fill("#date", rec["date"])
    for i, it in enumerate(rec["items"]):
        if i > 0:
            page.click("#add_item")
        page.fill(f"#item_{i}_description", it["description"])
        page.fill(f"#item_{i}_hsn", it["hsn"] or "")
        page.fill(f"#item_{i}_qty", f"{it['qty']:g}")
        page.fill(f"#item_{i}_rate", f"{it['rate']:.2f}")
        page.fill(f"#item_{i}_amount", f"{it['amount']:.2f}")
    page.fill("#cgst", f"{rec['cgst']:.2f}")
    page.fill("#sgst", f"{rec['sgst']:.2f}")
    page.fill("#total", f"{rec['total']:.2f}")
    with page.expect_navigation():
        page.click("#submit_btn")
    page.pdf(path=str(pdf_path), format="A4")            # Track B/C input
    page.screenshot(path=str(png_path), full_page=True)  # Track A (vision model) input


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    DATASET.mkdir(exist_ok=True)
    rng = random.Random(args.seed)
    tiers = tier_sequence(args.n, rng)
    gt_path = DATASET / "ground_truth.jsonl"

    with sync_playwright() as p, gt_path.open("w", encoding="utf-8") as gt:
        browser = p.chromium.launch()   # page.pdf() requires chromium headless
        page = browser.new_page(viewport={"width": A4_CSS_W, "height": A4_CSS_H},
                                device_scale_factor=PNG_SCALE)
        prev_invoice_no = None
        for i, tier in enumerate(tiers, start=1):
            rec = corrupt(make_record(rng, i), tier, rng, prev_invoice_no)
            rec["doc_id"] = f"inv_{i:04d}"
            # ---- truth FIRST, document second ----
            gt.write(json.dumps(rec, ensure_ascii=False) + "\n")
            gt.flush()
            fill_and_print(page, rec, DATASET / f"{rec['doc_id']}.pdf", DATASET / f"{rec['doc_id']}.png")
            prev_invoice_no = rec["invoice_no"]
            if i % 10 == 0:
                print(f"  {i}/{args.n} done (tier mix so far ok)")
        browser.close()
    print(f"wrote {args.n} PDFs+PNGs and {gt_path}")


if __name__ == "__main__":
    sys.exit(main())
