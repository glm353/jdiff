# jdiff — GraphQL Schema Diff Tool

## Purpose

Python tool that diffs two Plus Suite GraphQL introspection schemas and emits a human-readable report (HTML + Markdown). Output is used to update **Doc-002 Molecular** pages in Confluence, replacing the current manual (slow, error-prone) update process.

Typical comparisons: `npe:aplus` ↔ `prd:aplus`, `npe:suite` ↔ `prd:suite` (live fetch), or the equivalent committed JSON files.

## Input

Two forms, both supported as positional arguments to the CLI:

1. **Live target** — `env:api` where `env ∈ {npe, prd}` and `api ∈ {aplus, suite}`. The tool POSTs the introspection query to the resolved endpoint and caches the response as `out/<env>_<api>.json`. Cached files are reused on subsequent runs; pass `--no-cache` to force a refetch.
2. **File path** — any introspection JSON with shape `{data.__schema.types[...]}`. The committed sample files `npe_aplus.json`, `prd_aplus.json`, `npe_suite.json`, `prd_suite.json` all work as-is.

### Endpoint template

```
POST https://uon-api.{env}.allocate.plus/{env}/plus/graphql/{api}
Headers: x-api-key, Authorization: Bearer <JWT>, Content-Type: application/json
```

### Credentials (.env)

`npe` and `prd` have **separate** credentials because each JWT is env-scoped:

```
X_API_KEY=...          # npe api key
JWT_TOKEN=...          # npe JWT (raw, no "Bearer " prefix)
PRD_API_KEY=...        # prd api key
PRD_JWT_TOKEN=...      # prd JWT (Bearer prefix tolerated and stripped)
```

`.env` is gitignored. `python-dotenv` loads it automatically at CLI startup.

### Introspection query depth cap

The Plus Suite GraphQL server enforces a max query depth of **10**. The standard introspection query nests `ofType` seven levels deep — too deep. [jdiff/fetch.py](jdiff/fetch.py) uses a trimmed `TypeRef` fragment with **4 levels** of `ofType`, which yields a total query depth of 8 and handles any realistic type nesting (up to `[[[Foo!]!]!]!`).

## Filtering rule

**Drop anything whose `description` contains any of these case-insensitive markers**, applied to types, fields, queries, mutations, arguments, and enum values. The filter runs on **both** sides *before* diffing so internal churn never surfaces.

Current marker list (in [jdiff/load.py](jdiff/load.py)):

- `**INTERNAL` — matches both `**INTERNAL**` and `**INTERNAL:**`
- `JDR Internal` — matches `**JDR Internal:**`
- `JDR-ONLY` — matches `**PERMISSION**: JDR-ONLY`

Also drop built-in introspection types (`__Schema`, `__Type`, etc.).

## Architecture

```
jdiff/
  __init__.py
  load.py        # parse JSON, normalise type signatures, apply internal filter
  diff.py        # hand-rolled walk → structured diff model
  fetch.py       # live introspection fetcher (requests + dotenv creds)
  render.py      # markdown + HTML renderers (Jinja2) with inline-diff highlighting
  cli.py         # argparse entry point; resolves env:api targets + file paths
  templates/
    report.html.j2
tests/
  test_diff.py
  test_fetch.py  # HTTP stubbed via monkeypatch — no network
requirements.txt # jinja2, requests, python-dotenv
```

Diff model groups changes by:
- Types added / removed
- Per surviving type: fields added / removed / changed
- Special emphasis on `Query` and `Mutation` root types (this is what Doc-002 enumerates)
- Each change carries a path like `Query.getActivities.args.pageSize`, plus before/after

Hand-rolled walk preferred over `deepdiff` — cleaner output, no heavy post-processing.

### Report layout

- Sticky left-column **Table of Contents** (260 px, `position: sticky`) with links to Query, Mutation, Types added/removed, and each individually-changed type.
- All diff sections render as **tables**, not bullet lists. Changed-fields table has columns `Path | Change | <old filename> | <new filename>`; the two comparison columns are labelled with the actual input stems (e.g. `npe_aplus` / `prd_aplus`).
- **Inline diff highlighting** inside Before/After description cells — `difflib.SequenceMatcher` at line level, with removed lines shown with red strikethrough (`<span class="del">` in HTML, `<del>` in Markdown) and added lines shown with a green background (`<span class="ins">` / `<ins>`).

## CLI

```
python -m jdiff <old> <new> --out out/report --format html,md [--no-cache]
```

Examples:

```bash
python -m jdiff npe:aplus prd:aplus --out out/aplus             # live fetch both sides
python -m jdiff npe:suite prd_suite.json --out out/suite        # mix live + file
python -m jdiff npe_aplus.json prd_aplus.json --out out/aplus   # file-path mode
python -m jdiff npe:aplus prd:aplus --out out/aplus --no-cache  # force refetch
```

`<old>` is the baseline, `<new>` is the comparison target. The report reads `old → new`.

## Why static HTML, not Dash

Consumer is Confluence, which wants a **single artifact** to paste/attach — not a live web app. Static HTML + Markdown both render in Confluence and need no server. Dash would only make sense if we later wanted an interactive multi-schema explorer.

## Verification approach

- `pytest` — covers diff model (add / remove / change / internal filter / swap inversion) and fetch layer (target parsing, URL template, header correctness, error paths, GraphQL-error detection). HTTP is stubbed; no network calls.
- Live smoke: `python -m jdiff npe:aplus prd:aplus --out out/aplus`, open [out/aplus.html](out/aplus.html), spot-check tables, TOC, and inline highlighting.
- Same for `npe:suite` ↔ `prd:suite`.
- Swap arg order → adds/removes should invert.
- Confirm nothing containing `**INTERNAL`, `JDR Internal`, or `JDR-ONLY` appears in any output.

## Plan file

Full design plan: `C:\Users\glm353\.claude\plans\abundant-tumbling-hartmanis.md`

## Session log

- **2026-04-13** — initial design session. Decided on static HTML + Markdown output (rejected Dash as overkill for a paste-into-Confluence workflow). Confirmed `**INTERNAL**` as the filter marker after inspecting sample files. Approved hand-rolled diff walk over `deepdiff`. CLAUDE.md created before any code drafting.
- **2026-04-14** — scaffolded the project (`load`, `diff`, `render`, `cli`, Jinja template, pytest suite). Fixed introspection loader to tolerate missing `ofType` on terminal type refs. Converted report output from bullet lists to tables in both HTML and Markdown, labelled Before/After columns with input filenames, and added a Query/Mutation root-type fallback (`"Query"`/`"Mutation"`) for introspection dumps that omit the schema-root metadata. Expanded internal-marker list to catch `**INTERNAL:**`, `JDR Internal`, and `JDR-ONLY`. Added `difflib`-based inline diff highlighting inside description cells. Swapped the gold `.changed` accent for slate blue and added a sticky left-column Table of Contents. Built the live-fetch pipeline: normalized `.env`, added `jdiff/fetch.py` with introspection query + target parsing, wired CLI to auto-detect `env:api` positionals and cache responses under `out/`, and split credentials per environment (`X_API_KEY`/`JWT_TOKEN` for npe, `PRD_API_KEY`/`PRD_JWT_TOKEN` for prd, with `Bearer ` prefix stripped). Trimmed the introspection `TypeRef` fragment to 4 `ofType` levels to stay under the server's query-depth cap of 10.
