"""Shared plumbing for all parser tracks: doc discovery, output writing,
one-retry JSON repair, timing. Track files stay focused on the stack itself."""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Callable, Iterator

from pydantic import ValidationError

from schema import Invoice
from validators import validate


def _load_dotenv() -> None:
    """Auto-load repo-root .env (BYOK) -- zero-dependency, runs on import.
    Real env vars win over .env values; copy .env.example -> .env and fill
    only the keys your track needs (Track A needs none)."""
    env = Path(__file__).resolve().parents[1] / ".env"
    if not env.exists():
        return
    import os
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_dotenv()


def iter_docs(dataset_dir: str | Path, ext: str) -> Iterator[Path]:
    """Yield inv_XXXX.{ext} in order. ext='pdf' for Tracks B/C, 'png' for A."""
    for p in sorted(Path(dataset_dir).glob(f"inv_*.{ext}")):
        yield p


def b64(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode()


def coerce_json(text: str) -> dict:
    """Last-resort salvage when a model ignores structured-output mode.

    GOTCHA (same wording as slide, README): JSON in a text response != structured
    output -- use tool-calling / JSON-schema mode or you'll spend 20 minutes
    regex-ing markdown fences. This function is the 20 minutes, pre-spent, and
    if your track relies on it something upstream is misconfigured.
    """
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON object found in: {text[:200]!r}")
    return json.loads(text[start : end + 1])


def run_track(
    name: str,
    dataset_dir: str | Path,
    ext: str,
    parse_one: Callable[[Path], dict],
    out_path: str | Path,
    limit: int | None = None,
) -> None:
    """Run parse_one over the dataset; emit outputs.jsonl with per-doc
    {doc_id, fields, validation_flags, latency_s, error}. One retry per doc.
    """
    out_path = Path(out_path)
    n_ok = n_err = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i, doc in enumerate(iter_docs(dataset_dir, ext)):
            if limit is not None and i >= limit:
                break
            row: dict = {"doc_id": doc.stem, "track": name}
            t0 = time.time()
            try:
                raw = _with_retry(parse_one, doc)
                inv = Invoice.model_validate(raw)
                row["fields"] = inv.model_dump()
                row["validation_flags"] = validate(inv)
                n_ok += 1
            except (ValidationError, Exception) as e:  # noqa: BLE001 -- log & continue: one bad doc must not kill a 100-doc run
                row["error"] = f"{type(e).__name__}: {e}"[:300]
                n_err += 1
            row["latency_s"] = round(time.time() - t0, 2)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{name}] {doc.stem}  {'OK' if 'fields' in row else 'ERR'}  {row['latency_s']}s")
    print(f"[{name}] done: {n_ok} ok, {n_err} errors -> {out_path}")


def _with_retry(fn: Callable[[Path], dict], doc: Path) -> dict:
    try:
        return fn(doc)
    except Exception:
        time.sleep(1.0)
        return fn(doc)   # exactly one retry; if it fails twice, surface it
