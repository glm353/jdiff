"""Unit tests for the diff walk and internal-filter."""
from __future__ import annotations

import json
from pathlib import Path

from jdiff.diff import diff_schemas
from jdiff.load import load_schema


def _schema(types: list[dict], query: str = "Query", mutation: str | None = None) -> dict:
    root = {"queryType": {"name": query}, "types": types}
    if mutation:
        root["mutationType"] = {"name": mutation}
    return {"data": {"__schema": root}}


def _scalar(name: str) -> dict:
    return {"kind": "SCALAR", "name": name}


def _named(name: str) -> dict:
    return {"kind": "OBJECT", "name": name, "ofType": None}


def _field(name: str, type_ref: dict, description: str | None = None, args=None) -> dict:
    return {
        "name": name,
        "description": description,
        "type": type_ref,
        "args": args or [],
    }


def _type_obj(name: str, fields: list[dict], description: str | None = None) -> dict:
    return {
        "kind": "OBJECT",
        "name": name,
        "description": description,
        "fields": fields,
        "inputFields": None,
        "enumValues": None,
    }


def _write(tmp: Path, name: str, schema: dict) -> Path:
    path = tmp / name
    path.write_text(json.dumps(schema), encoding="utf-8")
    return path


def test_add_remove_change(tmp_path: Path):
    old = _schema(
        [
            _type_obj(
                "Query",
                [
                    _field("a", _scalar("String")),
                    _field("b", _scalar("Int")),
                ],
            )
        ]
    )
    new = _schema(
        [
            _type_obj(
                "Query",
                [
                    _field("a", _scalar("String")),
                    _field("c", _scalar("Boolean")),
                    _field("b", _scalar("String")),  # type changed
                ],
            )
        ]
    )

    d = diff_schemas(load_schema(_write(tmp_path, "old.json", old)),
                     load_schema(_write(tmp_path, "new.json", new)))

    qd = d.query_diff
    assert qd is not None
    assert [f.name for f in qd.fields_added] == ["c"]
    assert qd.fields_removed == []
    assert any(c.kind == "type" and c.path == "Query.b" for c in qd.fields_changed)


def test_internal_filter_drops_fields_and_types(tmp_path: Path):
    old = _schema(
        [
            _type_obj(
                "Query",
                [
                    _field("pub", _scalar("String")),
                    _field("secret", _scalar("String"), description="**INTERNAL** do not use"),
                ],
            ),
            _type_obj("Hidden", [_field("x", _scalar("Int"))], description="**internal**"),
        ]
    )
    new = _schema(
        [
            _type_obj(
                "Query",
                [
                    _field("pub", _scalar("String")),
                ],
            )
        ]
    )

    old_s = load_schema(_write(tmp_path, "old.json", old))
    new_s = load_schema(_write(tmp_path, "new.json", new))

    assert "Hidden" not in old_s.types
    assert "secret" not in old_s.types["Query"].fields

    d = diff_schemas(old_s, new_s)
    # Internal stuff must never surface as an add/remove/change
    assert d.types_removed == []
    assert d.query_diff is None or d.query_diff.empty


def test_arg_changes(tmp_path: Path):
    arg = lambda name, t: {"name": name, "description": None, "type": t, "defaultValue": None}
    old = _schema(
        [
            _type_obj(
                "Query",
                [_field("f", _scalar("String"), args=[arg("a", _scalar("Int"))])],
            )
        ]
    )
    new = _schema(
        [
            _type_obj(
                "Query",
                [
                    _field(
                        "f",
                        _scalar("String"),
                        args=[arg("a", _scalar("String")), arg("b", _scalar("Int"))],
                    )
                ],
            )
        ]
    )
    d = diff_schemas(load_schema(_write(tmp_path, "o.json", old)),
                     load_schema(_write(tmp_path, "n.json", new)))
    kinds = {c.kind for c in d.query_diff.fields_changed}
    assert "arg_added" in kinds
    assert "arg_changed" in kinds


def test_swap_inverts(tmp_path: Path):
    old = _schema([_type_obj("Query", [_field("a", _scalar("String"))])])
    new = _schema([_type_obj("Query", [_field("b", _scalar("String"))])])
    op = _write(tmp_path, "o.json", old)
    np_ = _write(tmp_path, "n.json", new)
    d1 = diff_schemas(load_schema(op), load_schema(np_))
    d2 = diff_schemas(load_schema(np_), load_schema(op))
    assert [f.name for f in d1.query_diff.fields_added] == [f.name for f in d2.query_diff.fields_removed]
    assert [f.name for f in d1.query_diff.fields_removed] == [f.name for f in d2.query_diff.fields_added]
