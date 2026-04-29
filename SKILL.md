---
name: caveman
description: "Compress a skill (or any prompt/instruction doc) by stripping prose to telegraphic style — drop articles, hedges, filler, restated context, polite framing. Use when asked to caveman a skill, compress a skill, shrink a skill, reduce skill tokens, trim verbose skills, cave a skill, make tighter, make terser. Cuts token cost ~40–60% on procedural skills with no behavior loss. NOT for judgment, voice, brand, or interview skills — strips nuance."
invocation: reactive
effort-level: low
---

# caveman

Strip skill body + references to bare procedural instructions. Inspired by [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman).

## Two-pass workflow

### Pass 1 — deterministic (always run first)

```bash
python3 scripts/caveman.py path/to/SKILL.md --report     # see savings
python3 scripts/caveman.py path/to/SKILL.md -w           # write in place, .bak backup
```

Script does mechanically-safe substitutions (in order to → to, kill imperative softeners, drop intensifiers) and preserves YAML frontmatter, fenced code, inline `code`, markdown tables verbatim. Flags fluff candidates (`comprehensive`, `robust`, `leverage`, etc.) for the next pass.

### Pass 2 — judgment (the agent)

What the script can't do safely:
- Prose paragraphs → bullets / tables
- Repeated rationale → state once, reference
- Conditional logic → tables, not prose
- Drop sentences explaining WHY when WHAT is enough
- Decide each flagged-fluff word in context

## Cut

- Articles where unambiguous
- Restated context ("As mentioned above…")
- Adjectival fluff (after script flags — context matters)
- Repeated rationale
- Sentences explaining WHY when WHAT is enough
- Conjunctions where bullets/tables work

## Keep

- **Description (frontmatter)** — verbose. Trigger matching. Trim only true duplicates.
- Conditional logic / branches (tables, not prose)
- File paths, command lines, tool/field names
- Numeric thresholds, schema, "never" rules
- Cross-skill references (`see X skill`)
- YAML, code blocks, tables (script preserves automatically)

## Apply to

✅ Procedural: `build-*`, ops, integrations, API wrappers
🚫 Judgment / voice / behavioral: `human-writing`, `dossier`, `cg-brand`, `source-to-interview`, `slack-reply`. Strips nuance.

## Process

1. Read SKILL.md + `references/*.md`
2. Baseline: `wc -w SKILL.md references/*.md`
3. Pass 1: `python3 scripts/caveman.py <file> -w` on each
4. Pass 2: judgment pass on output, especially flagged words
5. Re-count. Target: −40% body, −50% references
6. Diff for missing branches/never-rules — restore if cut
7. Deploy. Verify trigger recall still works.

## Patterns

| Verbose | Cave |
|---|---|
| "If the user has not provided X, you should ask them" | "Missing X? Ask." |
| "Make sure to follow the conventions in `slack-reply` skill" | "Upload: `slack-reply` skill." |
| "The script accepts a JSON file as input" | "Input: JSON. Schema: docstring." |
| Multi-paragraph "When to use" | Bullet list of triggers |
| "It is critical that you do X. This prevents Y." | "Do X." (rationale once at top, not per-rule) |

## Quality bar

After caveman, an agent reading the skill cold should still know:
- when to invoke
- exact inputs needed
- exact outputs produced
- branching rules
- non-negotiable "never" rules

Any unclear post-cave → restore.
