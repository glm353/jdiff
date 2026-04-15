"""Tests for unified row flattening and HTML filter toolbar."""
from __future__ import annotations

from jdiff.diff import FieldChange, SchemaDiff, TypeDiff
from jdiff.load import Field
from jdiff.render import _unified_rows, render_html


def _sample_td() -> TypeDiff:
    td = TypeDiff(name="Foo")
    td.fields_added.append(Field(name="zeta", type_sig="String", description="new"))
    td.fields_removed.append(Field(name="alpha", type_sig="Int", description="gone"))
    td.fields_changed.append(
        FieldChange(path="Foo.mike", kind="description", before="old", after="new")
    )
    td.fields_changed.append(
        FieldChange(path="Foo.mike", kind="type", before="Int", after="String")
    )
    td.enum_added.append("NEW_VAL")
    td.enum_removed.append("OLD_VAL")
    return td


def test_unified_rows_sorted_and_classified():
    rows = _unified_rows(_sample_td())
    paths = [(r["path"], r["kind"]) for r in rows]
    assert paths == sorted(paths, key=lambda p: (p[0].lower(), p[1]))

    by_kind = {r["kind"]: r for r in rows}
    assert by_kind["field added"]["row_class"] == "added"
    assert by_kind["field removed"]["row_class"] == "removed"
    assert by_kind["description"]["row_class"] == "changed"
    assert by_kind["type"]["row_class"] == "changed"
    assert by_kind["enum added"]["row_class"] == "added"
    assert by_kind["enum removed"]["row_class"] == "removed"


def test_html_has_filter_toolbar_and_data_kind():
    diff = SchemaDiff(query_type="Query")
    td = _sample_td()
    td.name = "Query"
    diff.types_changed.append(td)
    html = render_html(diff, "old", "new")
    assert 'class="filters"' in html
    assert 'class="kind-filter"' in html
    assert 'data-kind="description"' in html
    assert 'data-kind="field added"' in html
    assert 'id="hide-desc-preset"' in html
