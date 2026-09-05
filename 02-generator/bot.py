"""Playwright bot: fills the form N times, prints PDFs+PNGs, writes ground truth.

Run:  1) uvicorn app:app --port 8000     (in 01-form/)
      2) python bot.py --n 100 --seed 42 (here)

DEMO MODE, for the projector at 12:15:

      python bot.py --headed --n 3

Opens a real browser and fills the form slowly enough to watch, printing each
ground-truth line to the terminal BEFORE the corresponding document is made.
Terminal on one half of the screen, browser on the other: the answer exists,
then the document is manufactured from it. That is the rule of the day, visible.

Demo mode writes to demo_output/, never to dataset/, so nobody can corrupt a
100-document run by demoing over the top of it.

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
DEMO_DIR = Path(__file__).resolve().parent / "demo_output"   # --headed never touches dataset/
DEMO_MAX_N = 5          # a slow-mo run of 100 is eight minutes of nobody learning anything

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


def fill_and_print(page, rec: dict, pdf_path: Path, png_path: Path, headed: bool = False) -> None:
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
    if headed:
        # full_page screenshots use the viewport height as a floor, so restore
        # the real A4 height before capturing or the PNG comes out short.
        page.set_viewport_size({"width": A4_CSS_W, "height": A4_CSS_H})
        page.wait_for_timeout(900)                       # let the room read it
    page.pdf(path=str(pdf_path), format="A4")            # Track B/C input
    page.screenshot(path=str(png_path), full_page=True)  # Track A (vision model) input
    if headed:
        page.set_viewport_size({"width": A4_CSS_W, "height": 700})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--headed", action="store_true",
                    help="open a real browser and fill the form slowly enough to watch. "
                         "Writes to demo_output/, never to dataset/")
    ap.add_argument("--slow-mo", type=int, default=120,
                    help="ms between browser actions in --headed mode (default 120)")
    args = ap.parse_args()

    headed, slow_mo = args.headed, args.slow_mo
    out_dir = DEMO_DIR if headed else DATASET
    n = args.n
    if headed and n > DEMO_MAX_N:
        print(f"--headed is for the projector, not for a batch: capping {n} -> {DEMO_MAX_N}.")
        print(f"Run the real {n} headless when the demo is done.\n")
        n = DEMO_MAX_N

    out_dir.mkdir(exist_ok=True)
    rng = random.Random(args.seed)
    tiers = tier_sequence(n, rng)
    gt_path = out_dir / "ground_truth.jsonl"

    with sync_playwright() as p, gt_path.open("w", encoding="utf-8") as gt:
        # NOTE: page.pdf() used to be headless-only. It is not any more -- verified
        # on Playwright 1.62 -- which is why --headed can produce the real PDFs
        # and PNGs rather than a separate for-show-only path.
        browser = p.chromium.launch(headless=not headed, slow_mo=slow_mo if headed else 0)
        # Headed: a 1123px-tall window does not fit a 768p projector, so fill at a
        # shorter height and grow to full A4 just before capture. Output geometry
        # is therefore identical either way -- see fill_and_print().
        page = browser.new_page(
            viewport={"width": A4_CSS_W, "height": 700 if headed else A4_CSS_H},
            device_scale_factor=PNG_SCALE)
        prev_invoice_no = None
        for i, tier in enumerate(tiers, start=1):
            rec = corrupt(make_record(rng, i), tier, rng, prev_invoice_no)
            rec["doc_id"] = f"inv_{i:04d}"
            # ---- truth FIRST, document second ----
            gt.write(json.dumps(rec, ensure_ascii=False) + "\n")
            gt.flush()
            if headed:
                # The whole point of the demo: say the answer out loud BEFORE the
                # document that contains it exists.
                print(f"\n  TRUTH WRITTEN -> {rec['doc_id']}  [{rec['tier']}]"
                      + (f"  corruptions={rec['corruptions']}" if rec["corruptions"] else ""))
                print(f"    vendor={rec['vendor']!r}  gstin={rec['gstin']!r}")
                print(f"    cgst={rec['cgst']}  sgst={rec['sgst']}  total={rec['total']}")
                print("    v  now watch the document get made from it")
            fill_and_print(page, rec, out_dir / f"{rec['doc_id']}.pdf",
                           out_dir / f"{rec['doc_id']}.png", headed=headed)
            prev_invoice_no = rec["invoice_no"]
            if not headed and i % 10 == 0:
                print(f"  {i}/{n} done (tier mix so far ok)")
        browser.close()
    print(f"\nwrote {n} PDFs+PNGs and {gt_path}")
    if headed:
        print("Demo output is in demo_output/ -- your real dataset/ is untouched.")
        print("Now run the real thing:  python bot.py --n 100 --seed 42")


if __name__ == "__main__":
    sys.exit(main())
