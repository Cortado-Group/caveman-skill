---
name: workflow-skill
description: A multi-step workflow skill for testing how caveman handles longer prose with explicit step-by-step content.
---

# workflow-skill

This is a workflow skill that walks the agent through a multi-step process.
In order to be effective, you should follow the steps in order.

## Step 1: Intake

You should first make sure to gather the following information from the user:

- What is the goal?
- Who is the recipient?
- When is the deadline?

It is important that you note that you should ask one question at a time.
Don't list options. Don't overwhelm.

## Step 2: Research

You can use the following tools to research:

- `box-search` for finding existing files
- `knowledge-base` for searching books and digests
- `web_fetch` for external content

Make sure to cite sources. As mentioned above, you should be precise.

## Step 3: Draft

In order to draft, run:

```bash
python3 /skills/workflow-skill/scripts/draft.py <input.json> /workspace/output/draft.md
```

Please be sure to use the absolute path. The MCP gateway will reject relative paths.

## Step 4: Review

You should review the draft for:

- Tone — professional warmth, not too casual or too corporate
- Length — appropriate for the audience
- Clarity — each section has a clear takeaway

## Step 5: Deliver

You can deliver via Slack reply. Make sure to use the absolute path:

```
/workspace/output/draft.md
```

Thanks for following this workflow!
