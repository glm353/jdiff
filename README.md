# jdiff

Diff two Plus Suite GraphQL introspection schemas and emit a human-readable HTML + Markdown report. Output is intended to be pasted or attached into the **Doc-002 Molecular** Confluence pages, replacing the current manual update process.

See [CLAUDE.md](CLAUDE.md) for full design notes.

## Features

- **Live fetch or file input** — pass `npe:aplus` / `prd:suite` to pull the schema directly from the Plus Suite GraphQL API, or pass a path to an existing introspection JSON dump.
- **Response cache** — fetched schemas are saved under `out/<env>_<api>.json` and reused on subsequent runs. Use `--no-cache` to force a refetch.
- **Static HTML + Markdown output** — both formats paste cleanly into Confluence.
- **Internal-content filter** — anything whose description contains `**INTERNAL`, `JDR Internal`, or `JDR-ONLY` is dropped from both sides before diffing.
- **Readable reports** — every section is a table, Before/After columns are labelled with the actual input filenames, and long multi-line descriptions render with inline diff highlighting (red strikethrough for removed lines, green for added).
- **Sticky Table of Contents** — pinned left sidebar with links to Query, Mutation, Types added/removed, and each individually-changed type.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows cmd / PowerShell
# source .venv/Scripts/activate   # Git Bash
pip install -r requirements.txt
```

Python 3.10+.

## Credentials

Live fetch mode reads credentials from a `.env` file in the repo root. `npe` and `prd` have **separate** credentials because each JWT is env-scoped:

```
X_API_KEY=<npe api key>
JWT_TOKEN=<npe JWT, no "Bearer " prefix>
PRD_API_KEY=<prd api key>
PRD_JWT_TOKEN=<prd JWT>
```

`.env` is already in `.gitignore`. Never commit it.

## Usage

```
python -m jdiff <old> <new> --out out/report [--format html,md] [--no-cache]
```

`<old>` and `<new>` can each be either:

- An `env:api` target where `env ∈ {npe, prd}` and `api ∈ {aplus, suite}`, e.g. `npe:aplus`.
- A path to an introspection JSON file.

The report reads `old → new` (what changed going from baseline `old` to target `new`).

### Examples

```bash
# Live fetch both sides — most common
python -m jdiff npe:aplus prd:aplus --out out/aplus
python -m jdiff npe:suite prd:suite --out out/suite

# Force a refetch (ignore cached JSON under out/)
python -m jdiff npe:aplus prd:aplus --out out/aplus --no-cache

# Mix: live npe vs committed prd file
python -m jdiff npe:suite prd_suite.json --out out/suite

# File-path mode (no API calls)
python -m jdiff npe_aplus.json prd_aplus.json --out out/aplus

# HTML only
python -m jdiff npe:aplus prd:aplus --out out/aplus --format html
```

Each run writes `out/<name>.html` and/or `out/<name>.md`. Open the HTML in a browser and paste into Confluence, or attach the Markdown directly.

### Arguments

| Arg | Description |
| --- | --- |
| `old` | Baseline: `env:api` target or introspection JSON path. |
| `new` | Comparison target: `env:api` or path. |
| `--out` | Output path prefix, no extension. Defaults to `out/report`. |
| `--format` | Comma-separated: `html`, `md`. Defaults to `html,md`. |
| `--no-cache` | Force refetch for `env:api` targets instead of reusing the cached JSON. |

## Filtering rule

Anything whose `description` contains `**INTERNAL`, `JDR Internal`, or `JDR-ONLY` (all case-insensitive) is dropped from **both** sides *before* diffing — this applies to types, fields, queries, mutations, arguments, and enum values. Built-in introspection types (`__Schema`, `__Type`, …) are dropped too.

Add more markers in [jdiff/load.py](jdiff/load.py) → `INTERNAL_MARKERS`.

## Layout

```
jdiff/
  load.py        parse JSON, normalise type signatures, apply internal filter
  diff.py        hand-rolled walk producing a structured diff model
  fetch.py       live introspection fetcher (requests + dotenv creds)
  render.py      markdown + HTML renderers (Jinja2) with inline-diff highlighting
  cli.py         argparse entry point; resolves env:api targets and file paths
  templates/
    report.html.j2
tests/
  test_diff.py
  test_fetch.py
```

## Tests

```bash
pytest
```

- `test_diff.py` covers add / remove / change / arg-diff / internal-filter / swap-inverts against tiny synthetic schemas.
- `test_fetch.py` stubs `requests.post` via `monkeypatch` to assert target parsing, URL template, request headers (`x-api-key`, `Authorization: Bearer ...`, `Content-Type`), and error paths (non-200, GraphQL errors). No network calls.

## Troubleshooting

- **`maximum query depth exceeded`** — the server caps introspection at depth 10. The `TypeRef` fragment in [jdiff/fetch.py](jdiff/fetch.py) is trimmed to 4 `ofType` levels for this reason; don't expand it.
- **`introspection fetch failed ... (403): Forbidden`** — the JWT for that env is missing, expired, or scoped to a different env. Check the `sub` / `exp` claims of the token and confirm you're using the matching env's credentials.
- **Query/Mutation sections empty** — the loader falls back to `"Query"`/`"Mutation"` type names when the schema root omits `queryType` / `mutationType`. If those two type names aren't in the dump either, nothing will render in those sections.
- **`**INTERNAL**` content showing up in the report** — add the exact marker string to `INTERNAL_MARKERS` in [jdiff/load.py](jdiff/load.py).
