#!/usr/bin/env bash
# agentic-invoice-pipeline setup · workshop by Priyank Mehta (SaarthiOS)
# Run me at HOME, on real wifi — Chromium is ~150MB, the optional Ollama
# vision model is ~6GB. Venue wifi is where model pulls go to die.
set -e

# --- pick an interpreter we actually test against -----------------------------
# Bare `python3` is whatever is first on PATH. On a 2026 laptop that is often
# 3.14, which has no wheels for parts of requirements.txt -- and the failure
# lands in the middle of the 11:30 block. Probe, then fail loudly.
PY=""
for cand in python3.12 python3.11 python3.13 python3; do
  command -v "$cand" >/dev/null 2>&1 || continue
  ver=$("$cand" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null) || continue
  case "$ver" in 3.11|3.12|3.13) PY="$cand"; break;; esac
done
if [ -z "$PY" ]; then
  echo "✗ Need Python 3.11, 3.12 or 3.13. Found: $(python3 --version 2>&1)"
  echo "  macOS:  brew install python@3.12"
  echo "  Linux:  sudo apt install python3.12-venv"
  exit 1
fi
echo "── using $PY ($($PY --version)) ──"

$PY -m venv .venv && source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
python -m playwright install chromium
[ -f .env ] || cp .env.example .env
echo "── core setup done · .env created from template (Track A needs NO keys) ──"
echo "Track A (free/local): ollama pull qwen2.5vl:7b        # ~6GB / ~30min, needs 16GB RAM free"
echo "  8GB laptop?         ollama pull llama3.2:3b         # ~2GB, then run with --text-fallback"
echo "Track B (paid API):   put ANTHROPIC_API_KEY in .env"
echo "Track C (framework):  put LLAMA_CLOUD_API_KEY in .env (free tier: cloud.llamaindex.ai)"
