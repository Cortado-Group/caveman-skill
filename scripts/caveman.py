#!/usr/bin/env python3
"""
caveman.py — deterministic prose compressor for agent-targeted text (skills,
prompts, instructions).

Modes (cumulative):
    --lite         only the safest substitutions (verbose phrasings, doubled hedges)
    (default)      + imperative softeners, intensifiers, restated-context phrases,
                     trailing politeness, throat-clearing
    --ultra        + auto-strip flagged fluff words ("comprehensive", "robust",
                     "leverage", etc.) AND compress markdown table cell text

Usage:
    caveman.py FILE                          # to stdout
    caveman.py FILE -w                       # in-place; backup at <name>.<ext>.bak
    caveman.py FILE --report                 # only print savings + flags
    caveman.py FILE --ultra -w               # most aggressive
    caveman.py FILE --validate-only          # check structure (no output, no write)
    caveman.py -                             # read stdin -> stdout

Preserves verbatim: YAML frontmatter, fenced code blocks (``` / ~~~), inline
`code`, and markdown tables (cell text only compressed in --ultra).

Stdlib only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

# ----- Substitution sets. Order matters. -------------------------------------

SUBS_LITE: list[tuple[re.Pattern, str]] = [
    # Verbose phrasings → terse
    (re.compile(r"\bin order to\b", re.I), "to"),
    (re.compile(r"\bdue to the fact that\b", re.I), "because"),
    (re.compile(r"\bin the event that\b", re.I), "if"),
    (re.compile(r"\bat this point in time\b", re.I), "now"),
    (re.compile(r"\bin spite of the fact that\b", re.I), "although"),
    (re.compile(r"\bfor the purpose of\b", re.I), "for"),
    (re.compile(r"\bwith regard to\b", re.I), "about"),
    (re.compile(r"\bwith respect to\b", re.I), "about"),
    (re.compile(r"\bin the case of\b", re.I), "for"),
    (re.compile(r"\bin terms of\b", re.I), "for"),
    (re.compile(r"\ba large number of\b", re.I), "many"),
    (re.compile(r"\ba small number of\b", re.I), "few"),
    (re.compile(r"\bthe majority of\b", re.I), "most"),
    (re.compile(r"\bprior to\b", re.I), "before"),
    (re.compile(r"\bsubsequent to\b", re.I), "after"),
    # Doubled hedges → singletons
    (re.compile(r"\bcould potentially\b", re.I), "could"),
    (re.compile(r"\bmay possibly\b", re.I), "may"),
    (re.compile(r"\bmight possibly\b", re.I), "might"),
]

SUBS_DEFAULT_EXTRA: list[tuple[re.Pattern, str]] = [
    # Imperative softeners (agent already knows the verb is the instruction)
    (re.compile(r"^(\s*)Please\s+([A-Z])", re.M), r"\1\2"),
    (re.compile(r"\bplease (?=[a-z])", re.I), ""),
    (re.compile(r"\bkindly\s+", re.I), ""),
    (re.compile(r"\bMake sure to\s+", re.I), ""),
    (re.compile(r"\bMake sure that you\s+", re.I), ""),
    (re.compile(r"\bBe sure to\s+", re.I), ""),
    (re.compile(r"\bIt is important that you\s+", re.I), ""),
    (re.compile(r"\bIt is important to\s+", re.I), ""),
    (re.compile(r"\bYou should\s+", re.I), ""),
    (re.compile(r"\bYou must\s+", re.I), ""),
    (re.compile(r"\bYou need to\s+", re.I), ""),
    (re.compile(r"\bYou will need to\s+", re.I), ""),
    (re.compile(r"\bYou can\s+", re.I), ""),
    (re.compile(r"\bRemember to\s+", re.I), ""),
    (re.compile(r"\bDon't forget to\s+", re.I), ""),
    # Intensifiers
    (re.compile(r"\b(?:very|quite|really|simply|just|truly|actually|basically|essentially|literally) ", re.I), ""),
    # Restated-context
    (re.compile(r"\bAs (?:mentioned|noted|stated|discussed) (?:above|earlier|previously)[,:]?\s*", re.I), ""),
    (re.compile(r"\bAs (?:I|we) (?:mentioned|noted|stated|said) (?:above|earlier|before)[,:]?\s*", re.I), ""),
    # Throat-clearing
    (re.compile(r"^(\s*)Note that\s+", re.M), r"\1"),
    (re.compile(r"^(\s*)It should be noted that\s+", re.M), r"\1"),
    (re.compile(r"^(\s*)It's worth noting that\s+", re.M), r"\1"),
    (re.compile(r"\bThis means that\b", re.I), "So"),
    # Trailing politeness
    (re.compile(r"\n+(?:Thanks(?:!|\.)?|Thank you(?:!|\.)?|Cheers(?:!|\.)?|Hope this helps(?:!|\.)?)\s*$", re.I), ""),
]

# Whitespace tidy — ALWAYS run last
WHITESPACE_TIDY: list[tuple[re.Pattern, str]] = [
    (re.compile(r"  +"), " "),
    (re.compile(r" +(\n)"), r"\1"),
    (re.compile(r"\n{3,}"), "\n\n"),
]

# Words to flag (default mode) or auto-strip (--ultra)
FLAG_WORDS = {
    "comprehensive", "robust", "seamless", "best-in-class", "world-class",
    "cutting-edge", "leverage", "leveraging", "leveraged",
    "synergy", "holistic", "end-to-end", "best practices",
    "fast-paced", "dynamic", "innovative", "scalable",
    "streamline", "streamlined", "streamlining",
    "optimize", "optimized", "optimizing",
    "ensure", "ensuring",
}


def build_subs(mode: str) -> list[tuple[re.Pattern, str]]:
    subs = list(SUBS_LITE)
    if mode in ("default", "ultra"):
        subs += SUBS_DEFAULT_EXTRA
    if mode == "ultra":
        # Auto-strip flagged words. Single-word matches use \b; multi-word use phrase.
        for w in FLAG_WORDS:
            if " " in w or "-" in w:
                subs.append((re.compile(re.escape(w), re.I), ""))
            else:
                subs.append((re.compile(rf"\b{re.escape(w)}\b ?", re.I), ""))
    subs += WHITESPACE_TIDY
    return subs


# ----- Frontmatter / code / table protection ---------------------------------

CODE_FENCE = re.compile(r"^(\s*)(```|~~~)")
TABLE_LINE = re.compile(r"^\s*\|.*\|\s*$")
TABLE_SEPARATOR = re.compile(r"^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")


def split_protected(text: str) -> list[tuple[str, str]]:
    """Return [(kind, chunk), ...] where kind in {frontmatter, code, table, prose}."""
    chunks: list[tuple[str, str]] = []
    lines = text.split("\n")
    i = 0
    if lines and lines[0].strip() == "---":
        end = next((j for j in range(1, len(lines)) if lines[j].strip() == "---"), None)
        if end is not None:
            chunks.append(("frontmatter", "\n".join(lines[: end + 1])))
            i = end + 1

    cur_kind = "prose"
    cur: list[str] = []

    def flush():
        if cur:
            chunks.append((cur_kind, "\n".join(cur)))
            cur.clear()

    while i < len(lines):
        line = lines[i]
        m = CODE_FENCE.match(line)
        if m:
            flush()
            fence = m.group(2)
            block = [line]
            i += 1
            while i < len(lines):
                block.append(lines[i])
                if lines[i].lstrip().startswith(fence):
                    i += 1
                    break
                i += 1
            chunks.append(("code", "\n".join(block)))
            cur_kind = "prose"
            continue

        if TABLE_LINE.match(line):
            if cur_kind != "table":
                flush()
                cur_kind = "table"
            cur.append(line)
            i += 1
            continue

        if cur_kind != "prose":
            flush()
            cur_kind = "prose"
        cur.append(line)
        i += 1

    flush()
    return chunks


INLINE_CODE_RE = re.compile(r"`[^`\n]+`")


def cave_prose(text: str, subs: list[tuple[re.Pattern, str]]) -> str:
    """Apply substitutions to prose, protecting inline `backtick` spans."""
    # Stash inline code spans behind unique placeholders, restore at end.
    spans: list[str] = []

    def stash(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"\x00CAVE_INLINE_{len(spans) - 1}\x00"

    out = INLINE_CODE_RE.sub(stash, text)
    for pat, repl in subs:
        out = pat.sub(repl, out)
    # Restore. Walk from highest index down so regex doesn't accidentally
    # match a longer placeholder by prefix.
    for i in range(len(spans) - 1, -1, -1):
        out = out.replace(f"\x00CAVE_INLINE_{i}\x00", spans[i])
    return out


def cave_table_cells(text: str, subs: list[tuple[re.Pattern, str]]) -> str:
    """In --ultra mode, run prose substitutions on each markdown table cell."""
    out_lines: list[str] = []
    for line in text.split("\n"):
        if TABLE_SEPARATOR.match(line):
            out_lines.append(line)
            continue
        if not TABLE_LINE.match(line):
            out_lines.append(line)
            continue
        # Split on pipes, compress middle cells
        parts = line.split("|")
        new_parts = []
        for k, p in enumerate(parts):
            if k == 0 or k == len(parts) - 1:
                new_parts.append(p)  # leading/trailing artifacts
                continue
            cell = p
            for pat, repl in subs:
                cell = pat.sub(repl, cell)
            new_parts.append(cell)
        out_lines.append("|".join(new_parts))
    return "\n".join(out_lines)


# ----- Validation -------------------------------------------------------------

# Patterns used in extract-and-compare validation (borrowed shape from
# JuliusBrussee/caveman's validate.py; reimplemented for our scope).
URL_RE = re.compile(r"https?://[^\s)]+")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
PATH_RE = re.compile(r"(?:\./|\.\./|/|[A-Za-z]:\\)[\w\-/\\\.]+|[\w\-\.]+[/\\][\w\-/\\\.]+")


def _extract_code(text: str) -> list[str]:
    blocks: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        m = CODE_FENCE.match(lines[i])
        if not m:
            i += 1
            continue
        fence = m.group(2)
        block = [lines[i]]
        i += 1
        while i < len(lines):
            block.append(lines[i])
            if lines[i].lstrip().startswith(fence):
                i += 1
                break
            i += 1
        blocks.append("\n".join(block))
    return blocks


def validate_structure(text: str) -> list[str]:
    """Return a list of structural problems found in `text`. Empty = OK.

    Checks intrinsic structural sanity (frontmatter closes, fences balance,
    table separators have headers). For preservation checks comparing input
    vs output, see `validate_preservation`.
    """
    problems: list[str] = []
    lines = text.split("\n")

    if lines and lines[0].strip() == "---":
        if not any(lines[j].strip() == "---" for j in range(1, len(lines))):
            problems.append("YAML frontmatter opened with `---` but never closed")

    fences = sum(1 for ln in lines if CODE_FENCE.match(ln))
    if fences % 2 != 0:
        problems.append(f"unbalanced code fence count: {fences} (must be even)")

    for i, ln in enumerate(lines):
        if TABLE_SEPARATOR.match(ln):
            if i == 0 or not TABLE_LINE.match(lines[i - 1]):
                problems.append(f"line {i+1}: table separator with no header row above")

    return problems


def validate_preservation(original: str, compressed: str) -> list[str]:
    """Compare original vs compressed for structural preservation.

    Empty list = preserved. Each problem is a human-readable string suitable
    for printing.
    """
    problems: list[str] = []

    orig_urls = set(URL_RE.findall(original))
    comp_urls = set(URL_RE.findall(compressed))
    missing_urls = orig_urls - comp_urls
    if missing_urls:
        problems.append(f"URLs lost: {sorted(missing_urls)}")

    orig_paths = set(PATH_RE.findall(original))
    comp_paths = set(PATH_RE.findall(compressed))
    missing_paths = orig_paths - comp_paths
    if missing_paths:
        problems.append(f"file paths lost: {sorted(missing_paths)}")

    orig_headings = HEADING_RE.findall(original)
    comp_headings = HEADING_RE.findall(compressed)
    if len(orig_headings) != len(comp_headings):
        problems.append(
            f"heading count changed: {len(orig_headings)} → {len(comp_headings)}"
        )

    orig_code = _extract_code(original)
    comp_code = _extract_code(compressed)
    if orig_code != comp_code:
        problems.append(
            f"code block content changed: {len(orig_code)} blocks in original, "
            f"{len(comp_code)} in compressed (or content differs)"
        )

    orig_bullets = len(BULLET_RE.findall(original))
    comp_bullets = len(BULLET_RE.findall(compressed))
    if orig_bullets != comp_bullets:
        problems.append(
            f"bullet count changed: {orig_bullets} → {comp_bullets} "
            "(check that no bulleted item collapsed to empty)"
        )

    return problems


# Back-compat alias used by main()
validate = validate_structure


# ----- Counting ---------------------------------------------------------------

def words(text: str) -> int:
    """Count words in prose chunks only (mirrors token-cost of human-readable text)."""
    return sum(
        len(re.findall(r"\S+", chunk))
        for kind, chunk in split_protected(text)
        if kind == "prose"
    )


def find_flags(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    lower = text.lower()
    for w in FLAG_WORDS:
        if " " in w or "-" in w:
            n = lower.count(w.lower())
        else:
            n = len(re.findall(rf"\b{re.escape(w)}\b", lower))
        if n:
            counts[w] = n
    return counts


# ----- Main pipeline ----------------------------------------------------------

def cave(text: str, mode: str = "default") -> str:
    subs = build_subs(mode)
    chunks = split_protected(text)
    out: list[str] = []
    for kind, chunk in chunks:
        if kind == "prose":
            out.append(cave_prose(chunk, subs))
        elif kind == "table" and mode == "ultra":
            out.append(cave_table_cells(chunk, subs))
        else:
            out.append(chunk)
    return "\n".join(out)


def backup_path(path: Path) -> Path:
    """`SKILL.md` -> `SKILL.md.bak`. The `.bak` suffix tells every markdown
    crawler (skill discovery, doc generators, IDEs) to ignore the file."""
    return path.with_name(f"{path.name}.bak")


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic caveman compressor.")
    p.add_argument("path", help="File to compress, or '-' for stdin.")
    p.add_argument("-w", "--write", action="store_true",
                   help="Write in place. Backup at <name>.<ext>.bak (markdown crawlers ignore .bak).")
    p.add_argument("--report", action="store_true",
                   help="Print only the savings report (no compressed output).")
    p.add_argument("--validate-only", action="store_true",
                   help="Validate structure (no compression, no output, no write).")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--lite", action="store_const", dest="mode", const="lite",
                   help="Safest subset only (verbose phrasings, doubled hedges).")
    g.add_argument("--ultra", action="store_const", dest="mode", const="ultra",
                   help="Most aggressive: auto-strip flagged fluff + compress table cells.")
    p.set_defaults(mode="default")
    args = p.parse_args()

    if args.path == "-":
        if args.write:
            print("caveman: -w/--write incompatible with stdin", file=sys.stderr)
            return 2
        original = sys.stdin.read()
        path: Path | None = None
    else:
        path = Path(args.path)
        if not path.is_file():
            print(f"caveman: {path}: not a file", file=sys.stderr)
            return 2
        original = path.read_text()

    if args.validate_only:
        problems = validate(original)
        if problems:
            for prob in problems:
                print(f"caveman: validation: {prob}", file=sys.stderr)
            return 1
        print("caveman: OK", file=sys.stderr)
        return 0

    compressed = cave(original, mode=args.mode)
    in_words = words(original)
    out_words = words(compressed)
    flags = find_flags(compressed)
    problems = validate(compressed)

    if problems:
        for prob in problems:
            print(f"caveman: validation FAILED post-compression: {prob}", file=sys.stderr)
        print("caveman: refusing to write — re-run with --validate-only on input first",
              file=sys.stderr)
        return 1

    if args.write and path is not None:
        backup_path(path).write_text(original)
        path.write_text(compressed)

    cut = (in_words - out_words) / in_words * 100 if in_words else 0
    report_lines = [f"caveman[{args.mode}]: {in_words} → {out_words} prose words ({cut:.0f}% cut)"]
    if flags:
        report_lines.append("flagged for review:" if args.mode != "ultra" else "remaining flagged words (post-strip):")
        for w in sorted(flags, key=flags.get, reverse=True):
            report_lines.append(f"  {flags[w]:3d}  {w}")
    print("\n".join(report_lines), file=sys.stderr)

    if args.report:
        return 0
    if not args.write:
        sys.stdout.write(compressed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
