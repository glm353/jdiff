"""Command-line entry point.

Usage:
    python -m jdiff <old> <new> --out out/report

Each positional may be either a path to an introspection JSON file or a
target of the form `env:api` (e.g. `npe:aplus`), in which case the schema
is fetched live from the Plus Suite GraphQL API using credentials from .env.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .diff import diff_schemas
from .fetch import fetch_schema, parse_target
from .load import load_schema
from .render import render_html, render_markdown

_CREDS_BY_ENV = {
    "npe": ("X_API_KEY", "JWT_TOKEN"),
    "prd": ("PRD_API_KEY", "PRD_JWT_TOKEN"),
}


def _load_creds(env: str) -> tuple[str, str]:
    key_var, token_var = _CREDS_BY_ENV[env]
    api_key = os.environ.get(key_var)
    jwt_token = os.environ.get(token_var)
    if not api_key or not jwt_token:
        raise SystemExit(
            f"missing credentials for {env}: set {key_var} and {token_var} in .env"
        )
    # Tolerate a stored "Bearer " prefix — fetch_schema adds it itself.
    if jwt_token.lower().startswith("bearer "):
        jwt_token = jwt_token[7:]
    return api_key, jwt_token


def _resolve_input(value: str, cache_dir: Path, no_cache: bool) -> Path:
    """Return a filesystem path for `value`.

    If `value` is of the form `env:api`, fetch the schema (or reuse a cached
    copy under `cache_dir`). Otherwise treat `value` as a file path.
    """
    target = parse_target(value)
    if target is None:
        return Path(value)

    env, api = target
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{env}_{api}.json"

    if cache_path.exists() and not no_cache:
        print(f"using cached {cache_path}")
        return cache_path

    api_key, jwt_token = _load_creds(env)
    print(f"fetching {env}:{api} → {cache_path}")
    payload = fetch_schema(env, api, api_key=api_key, jwt_token=jwt_token)
    cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return cache_path


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    p = argparse.ArgumentParser(
        prog="jdiff",
        description="Diff two GraphQL introspection schemas.",
    )
    p.add_argument(
        "old",
        help="Baseline introspection JSON path, or target like 'npe:aplus'.",
    )
    p.add_argument(
        "new",
        help="New introspection JSON path, or target like 'prd:aplus'.",
    )
    p.add_argument("--out", default="out/report", help="Output path prefix (no extension).")
    p.add_argument(
        "--format",
        default="html,md",
        help="Comma-separated list of output formats: html, md.",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Force refetching env:api targets even if a cached JSON exists.",
    )
    args = p.parse_args(argv)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = out.parent

    old_path = _resolve_input(args.old, cache_dir, args.no_cache)
    new_path = _resolve_input(args.new, cache_dir, args.no_cache)

    old_schema = load_schema(old_path)
    new_schema = load_schema(new_path)
    d = diff_schemas(old_schema, new_schema)

    old_name = old_path.stem
    new_name = new_path.stem

    formats = {f.strip().lower() for f in args.format.split(",") if f.strip()}
    if "html" in formats:
        html_path = out.with_suffix(".html")
        html_path.write_text(render_html(d, old_name, new_name), encoding="utf-8")
        print(f"wrote {html_path}")
    if "md" in formats:
        md_path = out.with_suffix(".md")
        md_path.write_text(render_markdown(d, old_name, new_name), encoding="utf-8")
        print(f"wrote {md_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
