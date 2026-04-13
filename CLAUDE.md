# jdiff — GraphQL Schema Diff Tool

## Purpose

Python tool that diffs two Plus Suite GraphQL introspection schemas and emits a human-readable report (HTML + Markdown). Output is used to update **Doc-002 Molecular** pages in Confluence, replacing the current manual (slow, error-prone) update process.

Typical comparisons: `npe_aplus.json` ↔ `prd_aplus.json`, `npe_suite.json` ↔ `prd_suite.json`.

## Input

Standard GraphQL introspection JSON dumps with shape `{data.__schema.types[...]}`. Generated via the introspection query documented in `ASP-Accessing GraphQL APIs-130426-045627.pdf` (see "Introspection" section).

Endpoint pattern (for future live-fetch mode):
```
POST https://uon-api.npe.allocate.plus/npe/plus/graphql/suite
Headers: x-api-key, Authorization: Bearer <JWT>, Content-Type: application/json
```

Sample schema files in repo root: `npe_aplus.json`, `prd_aplus.json`, `npe_suite.json`, `prd_suite.json`.

## Filtering rule

**Drop anything whose `description` contains `**INTERNAL**` (case-insensitive).** Applies to types, fields, queries, mutations, and arguments. Filter is applied to **both** sides *before* diffing so internal churn never appears in the report.

Also drop built-in introspection types (`__Schema`, `__Type`, etc.).

Note: the literal phrase "INTERNAL USE ONLY" does **not** appear in the sample files — `**INTERNAL**` (markdown bold) is the actual marker used in the Plus Suite schema descriptions.

## Architecture

```
jdiff/
  __init__.py
  load.py        # parse JSON, normalise type signatures, apply internal filter
  diff.py        # hand-rolled walk → structured diff model
  render.py      # markdown + HTML renderers (Jinja2)
  cli.py         # argparse entry point
  templates/
    report.html.j2
tests/
  test_diff.py
requirements.txt # jinja2 (+ requests later for live fetch)
```

Diff model groups changes by:
- Types added / removed
- Per surviving type: fields added / removed / changed
- Special emphasis on `Query` and `Mutation` root types (this is what Doc-002 enumerates)
- Each change carries a path like `Query.getActivities.args.pageSize`, plus before/after

Hand-rolled walk preferred over `deepdiff` — cleaner output, no heavy post-processing.

## CLI (planned)

```
python -m jdiff <old.json> <new.json> --out out/report --format html,md
```

Future: `--fetch npe,prd` to pull live schemas using API_KEY / JWT env vars.

## Why static HTML, not Dash

Consumer is Confluence, which wants a **single artifact** to paste/attach — not a live web app. Static HTML + Markdown both render in Confluence and need no server. Dash would only make sense if we later wanted an interactive multi-schema explorer.

## Verification approach

- Run against `npe_aplus.json` vs `prd_aplus.json`, open HTML in browser, spot-check.
- Same for `npe_suite.json` vs `prd_suite.json`.
- Swap arg order → adds/removes should invert.
- Confirm nothing containing `**INTERNAL**` appears in any output.
- Unit tests with tiny synthetic schemas covering add / remove / change / internal-filter cases.

## Plan file

Full design plan: `C:\Users\glm353\.claude\plans\vectorized-sprouting-kahn.md`

## Session log

- **2026-04-13** — initial design session. Decided on static HTML + Markdown output (rejected Dash as overkill for a paste-into-Confluence workflow). Confirmed `**INTERNAL**` as the filter marker after inspecting sample files. Approved hand-rolled diff walk over `deepdiff`. CLAUDE.md created before any code drafting.
