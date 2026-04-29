# caveman-skill

A lean Claude Code skill that compresses agent-targeted text — skills, prompts, instructions — by stripping mechanical-safe verbosity. Procedural prose only; not for human-facing copy.

## Credit where it's due

Inspired by [**JuliusBrussee/caveman**](https://github.com/JuliusBrussee/caveman) — the original "talk like caveman" Claude/Codex/Cursor/Windsurf token-saving toolkit. If you want a full multi-agent installation framework with hooks, evals, memory compression (`cavemem`), and intensity modes (lite / full / ultra / 文言文), use that one.

This repo is a **smaller cousin** focused on one thing: compressing skill files (`SKILL.md` + `references/*.md`) for Claude Code skill libraries. We pulled out the techniques that mattered for our use case and left the rest.

## How this differs from the original

| | JuliusBrussee/caveman | this repo |
|---|---|---|
| Scope | Multi-agent (Claude / Codex / Cursor / Cline / Windsurf / Gemini) | Claude Code skills only |
| Components | `cavekit`, `caveman`, `cavemem`, hooks, evals, plugins | One Python script + one SKILL.md |
| Modes | lite / full / ultra / 文言文 | One mode |
| Memory compression | Yes (`cavemem`) | No |
| Auto-activation | Hooks + plugin install | Manual or skill-triggered |
| Install | `bash install.sh` or plugin manager | `git clone`, drop folder into skills dir |
| Files | Dozens | 5 |
| Deps | Python + JS + PowerShell + Shell | Python stdlib only |

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

# Write in place, leave .bak backup
python3 scripts/caveman.py path/to/SKILL.md -w

# Just the savings report
python3 scripts/caveman.py path/to/SKILL.md --report

# stdin
cat SKILL.md | python3 scripts/caveman.py -
```

The script reports word counts in/out, percent cut, and a list of *flagged* words it didn't strip — corporate-fluff candidates (`comprehensive`, `robust`, `seamless`, `leverage`, `synergy`, `optimize`, etc.) for the agent to review in context.

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

## Contributing

PRs welcome. Three guidelines:

1. New regex substitutions must be *mechanically safe* — adding noise is worse than leaving verbosity.
2. Don't add dependencies. Stdlib only.
3. If in doubt, **flag** the word for review instead of stripping it.

## License

MIT. See [LICENSE](LICENSE).

## Acknowledgments

- [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) — the original idea, methodology, and proof that this approach works at scale (46% average compression on prose-heavy markdown). Go give it a star.
