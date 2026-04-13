"""Render SchemaDiff as Markdown and HTML."""
from __future__ import annotations

import difflib
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .diff import SchemaDiff, TypeDiff

_TEMPLATE_DIR = Path(__file__).parent / "templates"


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
    env.filters["slug"] = _slug
    tmpl = env.get_template("report.html.j2")
    return tmpl.render(diff=diff, old_name=old_name, new_name=new_name)


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
    lines: list[str] = []
    if td.fields_added:
        lines.append("**Fields added**")
        lines.append("")
        lines.extend(
            _md_table(
                ["Field", "Type", "Description"],
                [
                    [_md_cell(f.name), _md_cell(f.type_sig), _md_cell(f.description)]
                    for f in td.fields_added
                ],
            )
        )
    if td.fields_removed:
        lines.append("**Fields removed**")
        lines.append("")
        lines.extend(
            _md_table(
                ["Field", "Type", "Description"],
                [
                    [_md_cell(f.name), _md_cell(f.type_sig), _md_cell(f.description)]
                    for f in td.fields_removed
                ],
            )
        )
    if td.fields_changed:
        lines.append("**Fields changed**")
        lines.append("")
        rows = []
        for c in td.fields_changed:
            before_md, after_md = _inline_diff_md(c.before, c.after)
            rows.append([_md_cell(c.path), _md_cell(c.kind), before_md, after_md])
        lines.extend(_md_table(["Path", "Change", old_name, new_name], rows))
    if td.enum_added:
        lines.append("**Enum values added**")
        lines.append("")
        lines.extend(_md_table(["Value", "Change"], [[_md_cell(v), "added"] for v in td.enum_added]))
    if td.enum_removed:
        lines.append("**Enum values removed**")
        lines.append("")
        lines.extend(_md_table(["Value", "Change"], [[_md_cell(v), "removed"] for v in td.enum_removed]))
    return lines


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
