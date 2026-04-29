---
name: api-wrapper
description: Wrapper for example.com API. Use when asked to query the example API for users, accounts, or projects.
---

# api-wrapper

CLI: `scripts/example_api.py`. Needs `credentials/example_token.txt` in cwd.

You should make sure to source the credentials file before running any command.

## Read operations

In order to look up a user, run:

```bash
python3 scripts/example_api.py find-user "name@example.com"
```

You can list all projects with:

```bash
python3 scripts/example_api.py projects
```

## Write operations

It is important that you note that write operations are rate-limited.

```bash
python3 scripts/example_api.py create-project "Project Name" --owner alice
```

Make sure to retry on 429 with exponential backoff. The script handles this
automatically, but you should be aware of it.

## Quirks

- The `search` endpoint returns 500 errors for some inputs. Make sure to
  fetch all and filter locally.
- Pagination is via `next` URL. The CLI handles this for you.
- Please be sure to validate input before calling the script.

For full API reference see https://example.com/api/docs.

Thanks!
