---
name: build-thing
description: "Use when asked to create, build, or generate a Thing. Triggers: 'build a thing', 'create thing', 'make me a thing'."
invocation: reactive
effort-level: medium
---

# build-thing

In order to build a Thing, you should first make sure to gather the inputs.

It is important that you note that the script may possibly fail if the input
file does not exist. As mentioned above, please be sure to validate before
calling the script.

## Workflow

1. Make sure to read the user's intent.
2. You should ask one clarifying question if anything is missing.
3. Run the script:

```bash
python3 /skills/build-thing/scripts/build_thing.py <input.json> /workspace/output/thing.docx
```

4. You can then upload via the slack-reply skill.

## Branching

| Got | Do |
|-----|-----|
| Just the type | Ask for the input source. |
| Type + source | Build. No questions. |

For more details, see https://example.com/docs/build-thing.

This skill provides a comprehensive, robust, end-to-end approach to leveraging
best-in-class data structures.

Thanks!
