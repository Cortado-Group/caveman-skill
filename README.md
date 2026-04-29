# caveman-skill

A lean Claude Code skill that compresses agent-targeted text — skills, prompts, instructions — by stripping mechanical-safe verbosity. Procedural prose only; not for human-facing copy.

## Prior art

Several "caveman speak" projects already exist. We borrowed the idea — the differentiator here is one specific use case (compressing skill files) and one specific implementation choice (deterministic script + judgment pass + flag-don't-strip on fluff candidates).

| Project | Approach | Notes |
|---|---|---|
| [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | Multi-agent toolkit (`cavekit` + `caveman` + `cavemem`) with Python compressor, hooks, evals, intensity modes (lite / full / ultra / 文言文). Targets Claude / Codex / Cursor / Cline / Windsurf / Gemini. | The most complete project. Use this if you want the full framework. ~46% reported compression. |
| [om-patel5/Caveman-Claude](https://github.com/om-patel5/Caveman-Claude) | "Token optimization layer" — Solidity-bridged framework with prompts. | 109 stars. Mostly prompt-based. |
| [amanattar/caveman-claude-skill](https://github.com/amanattar/caveman-claude-skill) | Single-file Claude skill. Six intensity modes. Pure prompt, no scripts. | Cleanest skill-shaped distribution; closest in spirit to ours, but no deterministic pass. |

## How this differs

| | This repo | The above |
|---|---|---|
| Scope | Compressing skill files (`SKILL.md` + `references/*.md`) | General agent output / memory / multi-agent |
| Determinism | Deterministic regex pass + judgment pass split | Mostly prompt-only (JuliusBrussee has a Python compressor too) |
| Frontmatter / code / table preservation | Explicit, regex-protected | Varies |
| Fluff handling | **Flag, don't strip** — surfaces candidates for the agent to decide in context | Strip aggressively |
| Modes | One | Several (lite / full / ultra / wenyan) |
| Files | 5 | Dozens to hundreds |
| Deps | Python stdlib | Varies (Solidity / JS / PS / Shell mix in some) |
| Install | `git clone` into skills dir | sh installers, plugin managers, mode flags |

## What it does

Two layers of compression:

1. **Deterministic pass** (`scripts/caveman.py`) — mechanical regex substitutions that are *always* safe:
   - "in order to" → "to"
   - "Make sure to X" / "You should X" / "It is important that you X" → "X"
   - "Please " / "kindly" → drop
   - "very/quite/really/just/basically" → drop
   - "could potentially" → "could"
   - "As mentioned above" / "It should be noted that" → drop
   - Trailing politeness ("Thanks!", "Hope this helps") → drop
   - Whitespace normalization

2. **Behavioral pass** (the SKILL.md itself) — the agent applies judgment-required compression that regex can't do safely: prose-to-bullet conversion, restating-context detection, conditional-flow simplification.

Both passes preserve YAML frontmatter, fenced code blocks, inline backticks, and markdown tables verbatim.

## Install (as a Claude Code skill)

```bash
git clone https://github.com/Cortado-Group/caveman-skill.git ~/.claude/skills/caveman
```

Or drop the folder into wherever your project's skills live.

## Use the script directly

```bash
# Stdout
python3 scripts/caveman.py path/to/SKILL.md

# Write in place; backup at path/to/SKILL.md.bak
python3 scripts/caveman.py path/to/SKILL.md -w

# Just the savings report
python3 scripts/caveman.py path/to/SKILL.md --report

# Validate structure only (no compression)
python3 scripts/caveman.py path/to/SKILL.md --validate-only

# stdin
cat SKILL.md | python3 scripts/caveman.py -
```

### Intensity modes

```bash
python3 scripts/caveman.py FILE --lite       # safest subset only
python3 scripts/caveman.py FILE               # default (recommended)
python3 scripts/caveman.py FILE --ultra      # most aggressive
```

| Mode | What it does |
|---|---|
| `--lite` | Only verbose phrasings ("in order to" → "to") and doubled hedges. No prose-changing substitutions. |
| default | Lite + imperative softeners ("Make sure to") + intensifiers ("very/quite/just") + restated context ("As mentioned above") + throat-clearing + trailing politeness. |
| `--ultra` | Default + auto-strip flagged fluff words (`comprehensive`, `robust`, `leverage`, etc.) + run substitutions on markdown table cell text. |

### Backup convention

Backups use `<name>.<ext>.bak` — e.g. `SKILL.md` → `SKILL.md.bak`. The `.bak` suffix tells every markdown crawler (skill discovery, doc generators, IDEs) to ignore the file. Avoid `.original.md` patterns — those get re-parsed by anything that scans `*.md`.

### Validation

Every compression run validates the output before writing. If the result has unbalanced code fences, unclosed YAML frontmatter, or orphaned table separators, the script refuses to write and exits non-zero. Use `--validate-only` to check input without compressing.

### Flagged words

Outside `--ultra`, the script reports corporate-fluff candidates (`comprehensive`, `robust`, `seamless`, `leverage`, `synergy`, `optimize`, etc.) without stripping them. The agent decides in context.

## What NOT to compress

This skill is for **agent-targeted text**. Don't run it on:

- Human-facing prose (Slack replies, blog drafts, JD content, marketing copy)
- Judgment / voice skills (anything teaching style, tone, or critical thinking)
- Code, config files, or data files
- Anything where readability for a human reviewer matters

Caveman strips nuance. Use it where nuance is overhead.

## Example

A skill file like:

```markdown
## Workflow

In order to build the report, you should first make sure to gather all
the data. It is important that you note that the database might possibly
be locked. As mentioned above, please be sure to retry if this happens.
```

Becomes:

```markdown
## Workflow

To build the report, first gather all the data. The database might be
locked. Retry if this happens.
```

Word count: 38 → 21 (45% cut). YAML/code/tables would have been preserved verbatim.

## Tests

32 unit tests in `tests/test_caveman.py`. Stdlib `unittest` (no pytest dep).

```bash
python3 -m unittest discover tests -v
```

What's covered:
- **Preservation invariants** — frontmatter, URLs, file paths, code blocks, headings, table structure survive in all modes
- **Idempotency** — `cave(cave(x)) == cave(x)` in every mode
- **Parameterized substitutions** — verify each rule fires (lite vs default-only)
- **Mode monotonicity** — lite ≥ default ≥ ultra in word count
- **Structural validation** — detects unbalanced fences, unclosed frontmatter, orphan table separators
- **Preservation validation** — detects URL loss, heading-count change, bullet-count change between input and output
- **Edge cases** — empty input, only frontmatter, only code, only tables
- **CLI integration** — `subprocess` invocations cover stdin, stdout, `-w`, `--report`, `--validate-only`, all three modes, and exit codes

## Evals

Different from unit tests — `evals/measure.py` runs the compressor across a corpus of representative skill files in `evals/corpus/` and reports per-file + aggregate compression and preservation stats.

```bash
python3 evals/measure.py            # human-readable
python3 evals/measure.py --json     # machine-readable
python3 evals/measure.py --corpus path/to/your/skills/
```

Exits non-zero if any file fails structural or preservation checks in any mode — useful as a CI gate.

Bring your own corpus: point `--corpus` at any directory of `.md` skill files. Drop your real (non-secret) skills in there to benchmark on actual content.

## Contributing

PRs welcome. Four guidelines:

1. New regex substitutions must be *mechanically safe* — adding noise is worse than leaving verbosity.
2. Don't add dependencies. Stdlib only.
3. If in doubt, **flag** the word for review instead of stripping it.
4. New rules need a corresponding test case in `tests/test_caveman.py`. The eval suite + unit tests must pass.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

The idea — and the proof that "talk like caveman" actually saves tokens at scale — comes from prior work. Star them:

- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) — the most complete implementation. Multi-agent, hooks, evals, memory compression, intensity modes. ~46% compression on prose-heavy markdown.
- [om-patel5/Caveman-Claude](https://github.com/om-patel5/Caveman-Claude) — token-optimization layer with 109 stars, broader Claude ecosystem framing.
- [amanattar/caveman-claude-skill](https://github.com/amanattar/caveman-claude-skill) — clean single-file skill with multiple intensity modes; closest in shape to this repo.

If you want the full ecosystem, go there. This repo exists for the narrow case of compressing skill files in a Claude Code skills directory with a deterministic-first, flag-don't-strip approach.
