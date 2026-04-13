# jdiff

Diff two Plus Suite GraphQL introspection schemas and emit a human-readable HTML + Markdown report. Output is intended to be pasted or attached into the **Doc-002 Molecular** Confluence pages, replacing the current manual update process.

See [CLAUDE.md](CLAUDE.md) for full design notes.

## Install

```bash
pip install -r requirements.txt
```

Python 3.10+.

## Usage

```bash
python -m jdiff <old.json> <new.json> --out out/report --format html,md
```

Example:

```bash
python -m jdiff npe_aplus.json prd_aplus.json --out out/aplus --format html,md
```

This writes `out/aplus.html` and `out/aplus.md`. Open the HTML in a browser and paste into Confluence, or attach the Markdown directly.

### Arguments

| Arg | Description |
| --- | --- |
| `old` | Baseline introspection JSON (`{data.__schema.types[...]}`). |
| `new` | New introspection JSON. |
| `--out` | Output path prefix, no extension. Defaults to `out/report`. |
| `--format` | Comma-separated: `html`, `md`. Defaults to `html,md`. |

## Input format

Standard GraphQL introspection query output. Generate one per environment against the Plus Suite GraphQL endpoint, e.g.:

```
POST https://uon-api.npe.allocate.plus/npe/plus/graphql/suite
Headers: x-api-key, Authorization: Bearer <JWT>
```

Sample files in repo root: `npe_aplus.json`, `prd_aplus.json`, `npe_suite.json`, `prd_suite.json`.

## Filtering rule

Anything whose `description` contains `**INTERNAL**` (case-insensitive) is dropped from **both** sides *before* diffing — this applies to types, fields, queries, mutations, arguments, and enum values. Built-in introspection types (`__Schema`, `__Type`, …) are dropped too.

## Layout

```
jdiff/
  load.py        parse JSON, normalise type signatures, apply internal filter
  diff.py        hand-rolled walk producing a structured diff model
  render.py      markdown + HTML renderers (Jinja2)
  cli.py         argparse entry point
  templates/
    report.html.j2
tests/
  test_diff.py
```

## Tests

```bash
pytest
```

Unit tests cover add / remove / change / arg-diff / internal-filter / swap-inverts cases against tiny synthetic schemas.

## Verification

- Run against `npe_aplus.json` vs `prd_aplus.json`, open HTML in browser, spot-check.
- Same for `npe_suite.json` vs `prd_suite.json`.
- Swap arg order → adds/removes should invert.
- Confirm nothing containing `**INTERNAL**` appears in any output.

## Roadmap

- `--fetch npe,prd` to pull live schemas using `API_KEY` / `JWT` env vars.
