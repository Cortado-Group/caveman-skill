#!/usr/bin/env python3
"""
measure.py — eval harness for caveman.py.

Runs caveman across a corpus of representative skill files, in all three modes,
and reports:
  - Per-file: word count in/out, % cut, structure preservation pass/fail
  - Aggregate: median + mean + min + max compression per mode
  - Aggregate: structure preservation pass rate per mode

Run:
    python3 evals/measure.py
    python3 evals/measure.py --corpus path/to/other/corpus
    python3 evals/measure.py --json   # machine-readable output

Exits non-zero if any file fails structural preservation in any mode —
useful as a CI gate.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import caveman  # noqa: E402

MODES = ("lite", "default", "ultra")
DEFAULT_CORPUS = ROOT / "evals" / "corpus"


def measure_one(text: str) -> dict[str, dict[str, Any]]:
    """Run all modes against `text`. Return per-mode metrics."""
    results: dict[str, dict[str, Any]] = {}
    in_words = caveman.words(text)
    for mode in MODES:
        compressed = caveman.cave(text, mode=mode)
        out_words = caveman.words(compressed)
        cut_pct = (in_words - out_words) / in_words * 100 if in_words else 0
        struct_problems = caveman.validate_structure(compressed)
        preserve_problems = caveman.validate_preservation(text, compressed)
        results[mode] = {
            "in_words": in_words,
            "out_words": out_words,
            "cut_pct": round(cut_pct, 1),
            "structure_ok": not struct_problems,
            "preservation_ok": not preserve_problems,
            "structure_problems": struct_problems,
            "preservation_problems": preserve_problems,
        }
    return results


def aggregate(per_file: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    agg: dict[str, Any] = {}
    for mode in MODES:
        cuts = [m[mode]["cut_pct"] for m in per_file.values()]
        struct_pass = sum(1 for m in per_file.values() if m[mode]["structure_ok"])
        preserve_pass = sum(1 for m in per_file.values() if m[mode]["preservation_ok"])
        n = len(per_file) or 1
        agg[mode] = {
            "median_cut_pct": round(statistics.median(cuts), 1) if cuts else 0,
            "mean_cut_pct": round(statistics.mean(cuts), 1) if cuts else 0,
            "min_cut_pct": min(cuts, default=0),
            "max_cut_pct": max(cuts, default=0),
            "structure_pass_rate": f"{struct_pass}/{n}",
            "preservation_pass_rate": f"{preserve_pass}/{n}",
        }
    return agg


def render_text(per_file, agg) -> str:
    lines = ["=" * 70, "caveman eval — per file", "=" * 70]
    for fname, modes in sorted(per_file.items()):
        lines.append(f"\n{fname}  (input: {modes['lite']['in_words']} words)")
        for mode in MODES:
            r = modes[mode]
            sok = "✓" if r["structure_ok"] else "✗"
            pok = "✓" if r["preservation_ok"] else "✗"
            lines.append(
                f"  {mode:8s}  {r['out_words']:4d} words  "
                f"({r['cut_pct']:5.1f}% cut)  struct {sok}  preserve {pok}"
            )
            for p in r["structure_problems"]:
                lines.append(f"    structure: {p}")
            for p in r["preservation_problems"]:
                lines.append(f"    preservation: {p}")
    lines.append("\n" + "=" * 70)
    lines.append("Aggregate")
    lines.append("=" * 70)
    lines.append(
        f"{'mode':8s}  {'median':>7s}  {'mean':>7s}  {'min':>7s}  {'max':>7s}  "
        f"{'struct':>10s}  {'preserve':>10s}"
    )
    for mode in MODES:
        a = agg[mode]
        lines.append(
            f"{mode:8s}  {a['median_cut_pct']:>6.1f}%  {a['mean_cut_pct']:>6.1f}%  "
            f"{a['min_cut_pct']:>6.1f}%  {a['max_cut_pct']:>6.1f}%  "
            f"{a['structure_pass_rate']:>10s}  {a['preservation_pass_rate']:>10s}"
        )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Eval caveman against a corpus.")
    p.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS,
                   help=f"Directory of .md files to evaluate (default: {DEFAULT_CORPUS})")
    p.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    args = p.parse_args()

    if not args.corpus.is_dir():
        print(f"measure: corpus not found: {args.corpus}", file=sys.stderr)
        return 2

    files = sorted(args.corpus.glob("*.md"))
    if not files:
        print(f"measure: no .md files in {args.corpus}", file=sys.stderr)
        return 2

    per_file: dict[str, dict[str, dict[str, Any]]] = {}
    for f in files:
        per_file[f.name] = measure_one(f.read_text())

    agg = aggregate(per_file)

    if args.json:
        print(json.dumps({"per_file": per_file, "aggregate": agg}, indent=2))
    else:
        print(render_text(per_file, agg))

    # CI gate: any structure or preservation failure → exit 1
    failed = any(
        not (m[mode]["structure_ok"] and m[mode]["preservation_ok"])
        for m in per_file.values()
        for mode in MODES
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
