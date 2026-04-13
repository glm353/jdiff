"""Load, normalise, and filter GraphQL introspection JSON schemas."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

INTERNAL_MARKERS = (
    "**INTERNAL",        # matches **INTERNAL** and **INTERNAL:**
    "JDR Internal",
    "JDR-ONLY",          # matches **PERMISSION**: JDR-ONLY
)
BUILTIN_PREFIX = "__"


@dataclass
class Arg:
    name: str
    type_sig: str
    description: str | None = None
    default_value: str | None = None


@dataclass
class Field:
    name: str
    type_sig: str
    description: str | None = None
    args: dict[str, Arg] = field(default_factory=dict)


@dataclass
class Type:
    name: str
    kind: str
    description: str | None = None
    fields: dict[str, Field] = field(default_factory=dict)
    enum_values: list[str] = field(default_factory=list)


@dataclass
class Schema:
    types: dict[str, Type]
    query_type: str | None
    mutation_type: str | None


def _is_internal(description: str | None) -> bool:
    if not description:
        return False
    lowered = description.lower()
    return any(marker.lower() in lowered for marker in INTERNAL_MARKERS)


def type_signature(type_ref: dict) -> str:
    """Recursively render a GraphQL type ref into a signature like `[Foo!]!`."""
    if type_ref is None:
        return "?"
    kind = type_ref.get("kind")
    if kind == "NON_NULL":
        return type_signature(type_ref.get("ofType")) + "!"
    if kind == "LIST":
        return "[" + type_signature(type_ref.get("ofType")) + "]"
    return type_ref.get("name") or "?"


def _load_arg(raw: dict) -> Arg:
    return Arg(
        name=raw["name"],
        type_sig=type_signature(raw["type"]),
        description=raw.get("description"),
        default_value=raw.get("defaultValue"),
    )


def _load_field(raw: dict) -> Field:
    args = {}
    for a in raw.get("args") or []:
        if _is_internal(a.get("description")):
            continue
        args[a["name"]] = _load_arg(a)
    return Field(
        name=raw["name"],
        type_sig=type_signature(raw["type"]),
        description=raw.get("description"),
        args=args,
    )


def _load_type(raw: dict) -> Type:
    fields = {}
    for f in raw.get("fields") or []:
        if _is_internal(f.get("description")):
            continue
        fields[f["name"]] = _load_field(f)
    # input object fields live under inputFields
    for f in raw.get("inputFields") or []:
        if _is_internal(f.get("description")):
            continue
        fields[f["name"]] = Field(
            name=f["name"],
            type_sig=type_signature(f["type"]),
            description=f.get("description"),
        )
    enum_values = [
        e["name"]
        for e in (raw.get("enumValues") or [])
        if not _is_internal(e.get("description"))
    ]
    return Type(
        name=raw["name"],
        kind=raw["kind"],
        description=raw.get("description"),
        fields=fields,
        enum_values=enum_values,
    )


def load_schema(path: str | Path) -> Schema:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    schema_root = data["data"]["__schema"]

    types: dict[str, Type] = {}
    for raw in schema_root["types"]:
        name = raw.get("name") or ""
        if name.startswith(BUILTIN_PREFIX):
            continue
        if _is_internal(raw.get("description")):
            continue
        types[name] = _load_type(raw)

    query_type = (schema_root.get("queryType") or {}).get("name")
    mutation_type = (schema_root.get("mutationType") or {}).get("name")
    if not query_type and "Query" in types:
        query_type = "Query"
    if not mutation_type and "Mutation" in types:
        mutation_type = "Mutation"

    return Schema(types=types, query_type=query_type, mutation_type=mutation_type)
