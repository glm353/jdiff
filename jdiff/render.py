"""Render SchemaDiff as Markdown and HTML."""
from __future__ import annotations

import difflib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .diff import SchemaDiff, TypeDiff

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# All change kinds that can appear in the unified table's Change column.
# Used to build the HTML filter toolbar. Order is rendering/display order.
CHANGE_KINDS: list[str] = [
    "field added",
    "field removed",
    "type",
    "description",
    "arg_added",
    "arg_removed",
    "arg_changed",
    "enum added",
    "enum removed",
]


def _field_body(type_sig: str, description: str | None) -> str:
    desc = description or ""
    if desc:
        return f"{type_sig}\n\n{desc}"
    return type_sig


def _unified_rows(td: TypeDiff) -> list[dict]:
    """Flatten a TypeDiff into a single sorted list of row dicts.

    Each row has keys: path, kind, before, after, row_class.
    Sort is alphabetical by path, then kind, so changes for the same
    field cluster together.
    """
    rows: list[dict] = []
    for f in td.fields_added:
        rows.append({
            "path": f.name,
            "kind": "field added",
            "before": "",
            "after": _field_body(f.type_sig, f.description),
            "row_class": "added",
        })
    for f in td.fields_removed:
        rows.append({
            "path": f.name,
            "kind": "field removed",
            "before": _field_body(f.type_sig, f.description),
            "after": "",
            "row_class": "removed",
        })
    for c in td.fields_changed:
        rows.append({
            "path": c.path,
            "kind": c.kind,
            "before": c.before or "",
            "after": c.after or "",
            "row_class": "changed",
        })
    for v in td.enum_added:
        rows.append({
            "path": v,
            "kind": "enum added",
            "before": "",
            "after": v,
            "row_class": "added",
        })
    for v in td.enum_removed:
        rows.append({
            "path": v,
            "kind": "enum removed",
            "before": v,
            "after": "",
            "row_class": "removed",
        })
    rows.sort(key=lambda r: (r["path"].lower(), r["kind"]))
    return rows


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "htm"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _inline_diff_html(before: object, after: object) -> tuple[Markup, Markup]:
    """Line-level inline diff. Returns (before_html, after_html) with
    <span class="del"> around removed lines and <span class="ins"> around
    added lines. Equal lines are shown on both sides."""
    b = "" if before is None else str(before)
    a = "" if after is None else str(after)
    b_lines = b.splitlines() or [""]
    a_lines = a.splitlines() or [""]
    sm = difflib.SequenceMatcher(a=b_lines, b=a_lines, autojunk=False)

    before_out: list[str] = []
    after_out: list[str] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for line in b_lines[i1:i2]:
                before_out.append(str(escape(line)))
            for line in a_lines[j1:j2]:
                after_out.append(str(escape(line)))
        elif op == "delete":
            for line in b_lines[i1:i2]:
                before_out.append(f'<span class="del">{escape(line) or "&nbsp;"}</span>')
        elif op == "insert":
            for line in a_lines[j1:j2]:
                after_out.append(f'<span class="ins">{escape(line) or "&nbsp;"}</span>')
        elif op == "replace":
            for line in b_lines[i1:i2]:
                before_out.append(f'<span class="del">{escape(line) or "&nbsp;"}</span>')
            for line in a_lines[j1:j2]:
                after_out.append(f'<span class="ins">{escape(line) or "&nbsp;"}</span>')

    return Markup("\n".join(before_out)), Markup("\n".join(after_out))


def _slug(value: str) -> str:
    return "type-" + "".join(ch if ch.isalnum() else "-" for ch in str(value)).strip("-").lower()


def render_html(diff: SchemaDiff, old_name: str, new_name: str) -> str:
    env = _env()
    env.globals["inline_diff"] = _inline_diff_html
    env.globals["unified_rows"] = _unified_rows
    env.filters["slug"] = _slug
    tmpl = env.get_template("report.html.j2")
    return tmpl.render(
        diff=diff,
        old_name=old_name,
        new_name=new_name,
        change_kinds=CHANGE_KINDS,
    )


def _md_cell(value: object) -> str:
    """Escape a value for a GFM table cell."""
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\\", "\\\\").replace("|", "\\|")
    s = s.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return s


def _inline_diff_md(before: object, after: object) -> tuple[str, str]:
    """Same as _inline_diff_html but produces GFM-safe cells using
    <del>...</del> for removed lines and <ins>...</ins> for added lines,
    separated by <br>. Confluence renders both tags."""
    b = "" if before is None else str(before)
    a = "" if after is None else str(after)
    b_lines = b.splitlines() or [""]
    a_lines = a.splitlines() or [""]
    sm = difflib.SequenceMatcher(a=b_lines, b=a_lines, autojunk=False)

    def _esc(line: str) -> str:
        return line.replace("|", "\\|")

    before_out: list[str] = []
    after_out: list[str] = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for line in b_lines[i1:i2]:
                before_out.append(_esc(line))
            for line in a_lines[j1:j2]:
                after_out.append(_esc(line))
        elif op in ("delete", "replace"):
            for line in b_lines[i1:i2]:
                before_out.append(f"<del>{_esc(line) or '&nbsp;'}</del>")
            if op == "replace":
                for line in a_lines[j1:j2]:
                    after_out.append(f"<ins>{_esc(line) or '&nbsp;'}</ins>")
        elif op == "insert":
            for line in a_lines[j1:j2]:
                after_out.append(f"<ins>{_esc(line) or '&nbsp;'}</ins>")
    return "<br>".join(before_out), "<br>".join(after_out)


def _md_table(headers: list[str], rows: list[list[str]]) -> list[str]:
    if not rows:
        return []
    out = []
    out.append("| " + " | ".join(headers) + " |")
    out.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    return out


def _type_block_md(td: TypeDiff, old_name: str, new_name: str) -> list[str]:
    rows = _unified_rows(td)
    if not rows:
        return []
    table_rows = []
    for r in rows:
        before_md, after_md = _inline_diff_md(r["before"], r["after"])
        table_rows.append([_md_cell(r["path"]), _md_cell(r["kind"]), before_md, after_md])
    return _md_table(["Path", "Change", old_name, new_name], table_rows)


def render_markdown(diff: SchemaDiff, old_name: str, new_name: str) -> str:
    lines: list[str] = []
    lines.append(f"# GraphQL Schema Diff: `{old_name}` → `{new_name}`")
    lines.append("")

    lines.append(f"## Query ({diff.query_type or '—'})")
    lines.append("")
    if diff.query_diff and not diff.query_diff.empty:
        lines.extend(_type_block_md(diff.query_diff, old_name, new_name))
    else:
        lines.append("_No changes._")
        lines.append("")

    lines.append(f"## Mutation ({diff.mutation_type or '—'})")
    lines.append("")
    if diff.mutation_diff and not diff.mutation_diff.empty:
        lines.extend(_type_block_md(diff.mutation_diff, old_name, new_name))
    else:
        lines.append("_No changes._")
        lines.append("")

    lines.append("## Types added")
    lines.append("")
    if diff.types_added:
        lines.extend(
            _md_table(
                ["Name", "Kind"],
                [[_md_cell(t.name), _md_cell(t.kind)] for t in diff.types_added],
            )
        )
    else:
        lines.append("_None._")
        lines.append("")

    lines.append("## Types removed")
    lines.append("")
    if diff.types_removed:
        lines.extend(
            _md_table(
                ["Name", "Kind"],
                [[_md_cell(t.name), _md_cell(t.kind)] for t in diff.types_removed],
            )
        )
    else:
        lines.append("_None._")
        lines.append("")

    other = [
        t
        for t in diff.types_changed
        if t.name not in {diff.query_type, diff.mutation_type}
    ]
    lines.append("## Other type changes")
    lines.append("")
    if other:
        for td in other:
            lines.append(f"### {td.name}")
            lines.append("")
            lines.extend(_type_block_md(td, old_name, new_name))
    else:
        lines.append("_None._")
        lines.append("")

    return "\n".join(lines) + "\n"
