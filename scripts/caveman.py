#!/usr/bin/env python3
"""
caveman.py — deterministic prose compressor for agent-targeted text (skills,
prompts, instructions). Strips mechanical-safe verbosity. Flags judgment-level
candidates for human/agent review without removing them.

Usage:
    caveman.py FILE                # to stdout
    caveman.py FILE -w             # in-place, .bak backup
    caveman.py -                   # read stdin -> stdout
    caveman.py FILE --report       # only print the savings report

Skips: YAML frontmatter, fenced code blocks (```), inline code (`...`),
markdown tables (lines with leading `|`).

Stdlib only. Python 3.8+.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# ----- Substitutions (regex, replacement). Order matters. ---------------------

SUBS: list[tuple[re.Pattern, str]] = [
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

    # Imperative softeners → drop (agent-targeted; instruction is the verb)
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

    # Intensifiers — weak word boost; drop
    (re.compile(r"\b(?:very|quite|really|simply|just|truly|actually|basically|essentially|literally) ", re.I), ""),

    # Restated-context phrases (agent already has the context loaded)
    (re.compile(r"\bAs (?:mentioned|noted|stated|discussed) (?:above|earlier|previously)[,:]?\s*", re.I), ""),
    (re.compile(r"\bAs (?:I|we) (?:mentioned|noted|stated|said) (?:above|earlier|before)[,:]?\s*", re.I), ""),

    # Throat-clearing
    (re.compile(r"^(\s*)Note that\s+", re.M), r"\1"),
    (re.compile(r"^(\s*)It should be noted that\s+", re.M), r"\1"),
    (re.compile(r"^(\s*)It's worth noting that\s+", re.M), r"\1"),
    (re.compile(r"\bThis means that\b", re.I), "So"),

    # Trailing politeness
    (re.compile(r"\n+(?:Thanks(?:!|\.)?|Thank you(?:!|\.)?|Cheers(?:!|\.)?|Hope this helps(?:!|\.)?)\s*$", re.I), ""),

    # Whitespace cleanup (after substitutions)
    (re.compile(r"  +"), " "),                # collapse internal double spaces (NOT leading)
    (re.compile(r" +(\n)"), r"\1"),           # trailing spaces on a line
    (re.compile(r"\n{3,}"), "\n\n"),          # max one blank line
]

# Words to FLAG for review (do not strip — the agent decides if they're fluff in context).
FLAG_WORDS = {
    "comprehensive", "robust", "seamless", "best-in-class", "world-class",
    "cutting-edge", "leverage", "leveraging", "leveraged",
    "synergy", "holistic", "end-to-end", "best practices",
    "fast-paced", "dynamic", "innovative", "scalable",
    "streamline", "streamlined", "streamlining",
    "optimize", "optimized", "optimizing",  # flag — sometimes valid, often fluff
    "ensure", "ensuring",                   # often "make sure" wrapper
}

# ----- Frontmatter / code / table protection ---------------------------------

CODE_FENCE = re.compile(r"^(\s*)(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]+`")
TABLE_LINE = re.compile(r"^\s*\|")

def split_protected(text: str) -> list[tuple[str, str]]:
    """Split into [(kind, chunk), ...] where kind in {'frontmatter','code','table','prose'}."""
    chunks: list[tuple[str, str]] = []
    lines = text.split("\n")
    i = 0

    # Frontmatter at start of file
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


def cave_prose(text: str) -> str:
    out = text
    for pat, repl in SUBS:
        out = pat.sub(repl, out)
    return out


def find_flags(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    lower = text.lower()
    for w in FLAG_WORDS:
        # Word-boundary match. Multi-word flags use phrase match.
        if " " in w or "-" in w:
            n = lower.count(w.lower())
        else:
            n = len(re.findall(rf"\b{re.escape(w)}\b", lower))
        if n:
            counts[w] = n
    return counts


def words(text: str) -> int:
    # Strip code+table+frontmatter from word count to mirror token cost more honestly.
    payload = []
    for kind, chunk in split_protected(text):
        if kind == "prose":
            payload.append(chunk)
    return sum(len(re.findall(r"\S+", c)) for c in payload)


def cave(text: str) -> str:
    chunks = split_protected(text)
    out: list[str] = []
    for kind, chunk in chunks:
        out.append(cave_prose(chunk) if kind == "prose" else chunk)
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description="Deterministic caveman compressor.")
    p.add_argument("path", help="File to compress, or '-' for stdin.")
    p.add_argument("-w", "--write", action="store_true",
                   help="Write in place. Backup at <path>.bak.")
    p.add_argument("--report", action="store_true",
                   help="Print only the savings report (no compressed output).")
    args = p.parse_args()

    if args.path == "-":
        if args.write:
            print("caveman: -w/--write incompatible with stdin", file=sys.stderr)
            return 2
        original = sys.stdin.read()
        path = None
    else:
        path = Path(args.path)
        if not path.is_file():
            print(f"caveman: {path}: not a file", file=sys.stderr)
            return 2
        original = path.read_text()

    compressed = cave(original)
    in_words = words(original)
    out_words = words(compressed)
    flags = find_flags(compressed)

    if args.write and path:
        path.with_suffix(path.suffix + ".bak").write_text(original)
        path.write_text(compressed)

    cut = (in_words - out_words) / in_words * 100 if in_words else 0
    report = [
        f"caveman: {in_words} → {out_words} prose words ({cut:.0f}% cut)",
    ]
    if flags:
        report.append("flagged for review:")
        for w in sorted(flags, key=flags.get, reverse=True):
            report.append(f"  {flags[w]:3d}  {w}")
    print("\n".join(report), file=sys.stderr)

    if args.report:
        return 0
    if not args.write:
        sys.stdout.write(compressed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
