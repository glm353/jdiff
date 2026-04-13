"""Command-line entry point: python -m jdiff old.json new.json --out out/report."""
from __future__ import annotations

import argparse
from pathlib import Path

from .diff import diff_schemas
from .load import load_schema
from .render import render_html, render_markdown


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jdiff", description="Diff two GraphQL introspection schemas.")
    p.add_argument("old", help="Path to the old/baseline introspection JSON.")
    p.add_argument("new", help="Path to the new introspection JSON.")
    p.add_argument("--out", default="out/report", help="Output path prefix (no extension).")
    p.add_argument(
        "--format",
        default="html,md",
        help="Comma-separated list of output formats: html, md.",
    )
    args = p.parse_args(argv)

    old_schema = load_schema(args.old)
    new_schema = load_schema(args.new)
    d = diff_schemas(old_schema, new_schema)

    old_name = Path(args.old).stem
    new_name = Path(args.new).stem
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

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
