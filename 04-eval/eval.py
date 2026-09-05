"""Eval harness: grade parser outputs against manufactured ground truth.

Run:  python eval.py --outputs ../03-parser/outputs_track_b.jsonl \
                     --truth   ../02-generator/dataset/ground_truth.jsonl \
                     [--cost-per-doc 0.5]

Emits: eval_report.md (per-field x per-tier matrix) + a one-line leaderboard
row to paste into the shared sheet.

Two scores per field, on purpose:
  exact      -- string/number identical after trimming outer whitespace
                (outer whitespace never survives PDF rendering; grading on it
                would penalize parsers for information that isn't there)
  normalized -- after canonicalization: strip Rs./commas/case/inner-space
                collapse, parse numbers with 1-paisa tolerance, dates -> ISO

GOTCHA (G5 "Exact-match eval fails correct answers", same wording as the
README): exact-match eval fails correct answers on formatting. Normalize BOTH
sides before comparing, and keep raw + normalized scores -- the gap between
them is your post-processing spec.

GOTCHA (M4): headline accuracy is a lie. '94% accurate' can mean 100%
on clean docs and 40% on the broken 8% -- and the broken 8% is the entire
reason the pipeline exists. This report therefore slices every field by tier.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Fields are DERIVED from the data, not hardcoded -- this is what lets one
# harness grade every idea-library document type (invoice, e-way bill, cheque,
# marksheet...). Graded scalar fields = keys present in ground truth AND in at
# least one parser output, minus generator metadata. Numeric-vs-text handling
# is type-driven from the truth value; a field is treated as a date when its
# name contains "date" (a naming convention every idea-library spec follows).
METADATA_KEYS = {"doc_id", "tier", "corruptions", "city", "track"}
TIERS = ["clean", "ok", "bad", "broken"]


def detect_row_key(truth: dict, override: str | None = None) -> str | None:
    """Name of the repeated-row list: 'items' on our invoice, 'subjects' on a
    marksheet, 'slab_lines' on an electricity bill.

    DERIVED, not hardcoded -- the most common key whose value is a list of
    dicts. This used to be the literal string "items", which meant any document
    whose rows were called anything else lost ALL line-level grading, silently,
    and still produced a plausible-looking report. Pass --row-key to override.
    """
    if override:
        return override
    counts = Counter()
    for gt in truth.values():
        for k, v in gt.items():
            if k in METADATA_KEYS:
                continue
            if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
                counts[k] += 1
    return counts.most_common(1)[0][0] if counts else None


def derive_fields(outputs: dict, truth: dict, row_key: str | None) -> tuple[list[str], list[str]]:
    t_scalar, t_item = set(), set()
    for gt in truth.values():
        t_scalar |= {k for k, v in gt.items() if k not in METADATA_KEYS and not isinstance(v, list)}
        for it in (gt.get(row_key) or []) if row_key else []:
            t_item |= set(it.keys())
    o_scalar, o_item = set(), set()
    for out in outputs.values():
        f = out.get("fields") or {}
        o_scalar |= {k for k, v in f.items() if not isinstance(v, list)}
        for it in (f.get(row_key) or []) if row_key else []:
            o_item |= set(it.keys())
    scalar = sorted(t_scalar & o_scalar) if o_scalar else sorted(t_scalar)
    item = sorted(t_item & o_item) if o_item else sorted(t_item)
    return scalar, item
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
                "%d %b %Y", "%d-%b-%Y", "%d %B %Y"]


# ---------------------------------------------------------------- normalization
def norm_text(s: str | None) -> str | None:
    if s is None:
        return None
    return re.sub(r"\s+", " ", s).strip().upper() or None


def norm_number(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    s = re.sub(r"[₹,\s]|RS\.?", "", str(v).upper())
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def norm_date(s: str | None) -> str | None:
    if s is None:
        return None
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return norm_text(s)   # unparseable stays as-is; verbatim match still possible


def exact_eq(a, b) -> bool:
    if isinstance(a, (int, float)) or isinstance(b, (int, float)):
        na, nb = norm_number(a), norm_number(b)
        return na is not None and na == nb
    a2 = a.strip() if isinstance(a, str) else a
    b2 = b.strip() if isinstance(b, str) else b
    return a2 == b2


def norm_eq(field: str, a, b, truth_value) -> bool:
    if isinstance(truth_value, (dict, list)):
        # A grouped field -- e.g. a payslip's earnings{basic, hra, ...}. There is
        # nothing to normalise, so compare structurally rather than raising:
        # norm_text() on a dict used to throw TypeError and take the whole run
        # down. Flatten these in your schema if you want them graded one by one.
        return a == b
    if isinstance(truth_value, (int, float)):
        na, nb = norm_number(a), norm_number(b)
        return na is not None and nb is not None and abs(na - nb) <= 0.01
    if "date" in field.lower():
        return norm_date(a) == norm_date(b)
    return norm_text(a) == norm_text(b)


# ------------------------------------------------------------------- evaluation
def load_jsonl(p: str | Path) -> dict[str, dict]:
    rows = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows[r["doc_id"]] = r
    return rows


def evaluate(outputs: dict[str, dict], truth: dict[str, dict],
             row_key: str | None = None) -> dict:
    # score[field][tier] = [exact_hits, norm_hits, n]
    scalar_fields, item_fields = derive_fields(outputs, truth, row_key)
    score = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
    latencies, parse_failures = [], 0
    # Parsed-only tallies. A failed doc takes zero credit on every field, which
    # is fair -- but it means a STABILITY regression and an ACCURACY regression
    # look identical in the headline. Counting the parsed docs separately lets
    # the report say which kind of problem you have. (See the exact-vs-norm pair
    # above: same trick, different axis.)
    parsed_hits = parsed_n = 0

    for doc_id, gt in truth.items():
        tier = gt.get("tier", "clean")
        out = outputs.get(doc_id)
        fields = (out or {}).get("fields")
        if out and "latency_s" in out:
            latencies.append(out["latency_s"])
        if fields is None:
            parse_failures += 1
            for f in scalar_fields + [f"item.{x}" for x in item_fields]:
                score[f][tier][2] += 1          # counted, zero credit
            continue

        for f in scalar_fields:
            cell = score[f][tier]
            cell[2] += 1
            parsed_n += 1
            if exact_eq(fields.get(f), gt.get(f)):
                cell[0] += 1
            if norm_eq(f, fields.get(f), gt.get(f), gt.get(f)):
                cell[1] += 1
                parsed_hits += 1

        gt_items = (gt.get(row_key) or []) if row_key else []
        out_items = (fields.get(row_key) or []) if row_key else []
        for i, git in enumerate(gt_items):        # positional comparison
            oit = out_items[i] if i < len(out_items) else {}
            for f in item_fields:
                cell = score[f"item.{f}"][tier]
                cell[2] += 1
                parsed_n += 1
                if exact_eq(oit.get(f), git.get(f)):
                    cell[0] += 1
                if norm_eq(f, oit.get(f), git.get(f), git.get(f)):
                    cell[1] += 1
                    parsed_hits += 1

    return {"score": score, "latencies": latencies, "parse_failures": parse_failures,
            "scalar_fields": scalar_fields, "item_fields": item_fields,
            "parsed_hits": parsed_hits, "parsed_n": parsed_n,
            "n_docs": len(truth), "row_key": row_key}


# ---------------------------------------------------------- validation-flag audit
def is_uncatchable(tag: str, extra: set[str]) -> bool:
    """Corruptions a PER-DOCUMENT validator structurally cannot see.

    Any 'duplicate_*' tag qualifies by definition -- duplicate_invoice_no on our
    invoice, duplicate_po_no on a purchase order -- because you need the whole
    batch to spot a duplicate. This used to be the single hardcoded string
    "duplicate_invoice_no", which meant every other document's duplicate tag
    counted against recall forever, for a reason nobody could find.
    """
    return "duplicate" in tag or tag in extra


def flag_audit(outputs: dict, truth: dict, catchable: set[str],
               uncatchable: set[str] | None = None) -> tuple[int, int, int]:
    """Did validation_flags fire on the docs the chaos engine actually broke?
    Returns (broken_docs, broken_docs_flagged, clean_docs_falsely_flagged).
    Cross-doc corruptions are excluded -- see is_uncatchable above.
    """
    uncatchable = uncatchable or set()
    broken = flagged = false_pos = 0
    for doc_id, gt in truth.items():
        out = outputs.get(doc_id) or {}
        flags = out.get("validation_flags", [])
        corr = [c for c in gt.get("corruptions", []) if not is_uncatchable(c, uncatchable)]
        if any(c in catchable for c in corr):
            broken += 1
            if flags:
                flagged += 1
        elif gt.get("tier") == "clean" and out.get("fields") and flags:
            false_pos += 1
    return broken, flagged, false_pos


# ----------------------------------------------------------------------- report
def pct(hit: int, n: int) -> str:
    return f"{100*hit/n:.0f}%" if n else "--"


def write_report(res: dict, audit, track: str, cost_per_doc: float | None, out_md: Path) -> str:
    score = res["score"]
    lines = [f"# Eval report -- track: {track}", ""]
    lines.append("| Field | " + " | ".join(f"{t} (exact/norm)" for t in TIERS) + " | ALL (exact/norm) |")
    lines.append("|---" * (len(TIERS) + 2) + "|")
    overall_norm_hits = overall_n = 0
    for f in res["scalar_fields"] + [f"item.{x}" for x in res["item_fields"]]:
        row = [f]
        te = tn = tc = 0
        for t in TIERS:
            e, n_, c = score[f][t]
            te, tn, tc = te + e, tn + n_, tc + c
            row.append(f"{pct(e, c)}/{pct(n_, c)}")
        row.append(f"{pct(te, tc)}/{pct(tn, tc)}")
        overall_norm_hits += tn
        overall_n += tc
        lines.append("| " + " | ".join(row) + " |")

    lat = res["latencies"]
    p50 = statistics.median(lat) if lat else 0
    headline = 100 * overall_norm_hits / overall_n if overall_n else 0
    broken, caught, false_pos = audit
    n_fail = res["parse_failures"]
    n_ok = res["n_docs"] - n_fail

    # Accuracy over parsed docs only. If this sits far above the headline, the
    # problem is stability, not extraction quality -- and the fix is a different
    # fix. Zero-credit-on-failure hides that distinction in a single number.
    parsed_headline = (100 * res["parsed_hits"] / res["parsed_n"]) if res["parsed_n"] else 0

    # Recall alone is trivially gamed: a validator that flags everything scores
    # 100%. Precision is the number that says whether the flags mean anything.
    denom = caught + false_pos
    precision = (100 * caught / denom) if denom else 0.0

    lines += [
        "",
        f"- Headline normalized accuracy (all fields, all tiers): **{headline:.1f}%** -- "
        "now read the broken column above -- see M4, 'headline accuracy is a lie'.",
        f"- Accuracy on successfully-parsed docs only: **{parsed_headline:.1f}%** "
        f"({n_ok}/{res['n_docs']} docs) -- if this is much higher than the headline, "
        "your problem is stability, not extraction quality.",
        f"- Parse failures (doc produced no output): {n_fail}",
        f"- Validator recall on chaos-broken docs: {caught}/{broken} caught"
        f"  | false flags on clean docs: {false_pos}",
        f"- Validator **precision: {precision:.0f}%** ({caught} true / {denom} total flagged docs)"
        " -- recall is worthless without this: a validator that flags everything scores 100% recall.",
        f"- p50 latency: {p50:.2f}s"
        + (f" | cost/doc: Rs.{cost_per_doc:.2f} | at 1M docs/month: Rs.{cost_per_doc*1_000_000:,.0f}"
           if cost_per_doc is not None else ""),
        "",
        "Leaderboard row (paste into the shared sheet):",
        "```",
        f"{track} | norm_acc={headline:.1f}% | parse_fail={n_fail} "
        f"| flag_prec={precision:.0f}% "
        f"| p50={p50:.2f}s | cost/doc={'Rs.%.2f' % cost_per_doc if cost_per_doc is not None else 'Rs.0'}",
        "```",
    ]
    text = "\n".join(lines)
    out_md.write_text(text, encoding="utf-8")
    return text


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--cost-per-doc", type=float, default=None, help="INR, from your track's pricing")
    ap.add_argument("--report", default="eval_report.md")
    ap.add_argument("--catchable", default="total_digit_swap,cgst_wrong_math,gstin_missing",
                    help="comma-separated corruption tags your validators are expected to catch. "
                         "The default is the GST-invoice set -- IF YOU PICKED ANOTHER DOCUMENT "
                         "YOU MUST PASS YOUR OWN, from your spec card, or recall is meaningless")
    ap.add_argument("--uncatchable", default="",
                    help="comma-separated tags a per-document validator structurally cannot see. "
                         "Any 'duplicate_*' tag is treated this way automatically")
    ap.add_argument("--row-key", default=None,
                    help="name of the repeated-row list (items / subjects / slab_lines). "
                         "Derived from your data if omitted")
    ap.add_argument("--ignore-fields", default="",
                    help="comma-separated generator-metadata keys to exclude from grading, "
                         "on top of the defaults")
    args = ap.parse_args()

    METADATA_KEYS.update(f.strip() for f in args.ignore_fields.split(",") if f.strip())

    outputs = load_jsonl(args.outputs)
    truth = load_jsonl(args.truth)
    track = next(iter(outputs.values()), {}).get("track", Path(args.outputs).stem)

    row_key = detect_row_key(truth, args.row_key)
    catchable = {t.strip() for t in args.catchable.split(",") if t.strip()}
    uncatchable = {t.strip() for t in args.uncatchable.split(",") if t.strip()}

    # A non-invoice team that forgets --catchable used to get "recall 0/0,
    # precision 0%" and no clue why. Say so, loudly, and name what IS there.
    present = {c for gt in truth.values() for c in gt.get("corruptions", []) or []}
    gradable = {c for c in present if not is_uncatchable(c, uncatchable)}
    if gradable and not (gradable & catchable):
        print("\n" + "!" * 72)
        print("!! --catchable matches NOTHING in this dataset. Validator recall and")
        print("!! precision below are meaningless. Tags actually present here:")
        print("!!   " + ", ".join(sorted(gradable)))
        print("!! Re-run with:  --catchable \"" + ",".join(sorted(gradable)) + "\"")
        print("!" * 72 + "\n")

    res = evaluate(outputs, truth, row_key)
    audit = flag_audit(outputs, truth, catchable, uncatchable)
    print(write_report(res, audit, track, args.cost_per_doc, Path(args.report)))
    if row_key:
        print(f"(graded repeated rows under key '{row_key}'"
              + (" -- override with --row-key)" if not args.row_key else ")"))
    else:
        print("(no repeated-row list detected -- scalar fields only)")


if __name__ == "__main__":
    main()
