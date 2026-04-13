"""Hand-rolled diff walk over two loaded Schemas."""
from __future__ import annotations

from dataclasses import dataclass, field

from .load import Field, Schema, Type


@dataclass
class FieldChange:
    path: str
    kind: str  # "type", "description", "arg_added", "arg_removed", "arg_changed"
    before: str | None = None
    after: str | None = None


@dataclass
class TypeDiff:
    name: str
    fields_added: list[Field] = field(default_factory=list)
    fields_removed: list[Field] = field(default_factory=list)
    fields_changed: list[FieldChange] = field(default_factory=list)
    enum_added: list[str] = field(default_factory=list)
    enum_removed: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (
            self.fields_added
            or self.fields_removed
            or self.fields_changed
            or self.enum_added
            or self.enum_removed
        )


@dataclass
class SchemaDiff:
    types_added: list[Type] = field(default_factory=list)
    types_removed: list[Type] = field(default_factory=list)
    types_changed: list[TypeDiff] = field(default_factory=list)
    query_type: str | None = None
    mutation_type: str | None = None

    @property
    def query_diff(self) -> TypeDiff | None:
        return next((t for t in self.types_changed if t.name == self.query_type), None)

    @property
    def mutation_diff(self) -> TypeDiff | None:
        return next((t for t in self.types_changed if t.name == self.mutation_type), None)


def _diff_field(type_name: str, old: Field, new: Field) -> list[FieldChange]:
    changes: list[FieldChange] = []
    base = f"{type_name}.{old.name}"

    if old.type_sig != new.type_sig:
        changes.append(FieldChange(base, "type", old.type_sig, new.type_sig))

    if (old.description or "") != (new.description or ""):
        changes.append(
            FieldChange(base, "description", old.description, new.description)
        )

    old_args, new_args = old.args, new.args
    for name in sorted(new_args.keys() - old_args.keys()):
        a = new_args[name]
        changes.append(
            FieldChange(f"{base}.args.{name}", "arg_added", None, a.type_sig)
        )
    for name in sorted(old_args.keys() - new_args.keys()):
        a = old_args[name]
        changes.append(
            FieldChange(f"{base}.args.{name}", "arg_removed", a.type_sig, None)
        )
    for name in sorted(old_args.keys() & new_args.keys()):
        oa, na = old_args[name], new_args[name]
        if oa.type_sig != na.type_sig:
            changes.append(
                FieldChange(
                    f"{base}.args.{name}", "arg_changed", oa.type_sig, na.type_sig
                )
            )
    return changes


def _diff_type(old: Type, new: Type) -> TypeDiff:
    td = TypeDiff(name=old.name)

    for fname in sorted(new.fields.keys() - old.fields.keys()):
        td.fields_added.append(new.fields[fname])
    for fname in sorted(old.fields.keys() - new.fields.keys()):
        td.fields_removed.append(old.fields[fname])
    for fname in sorted(old.fields.keys() & new.fields.keys()):
        td.fields_changed.extend(_diff_field(old.name, old.fields[fname], new.fields[fname]))

    old_enums, new_enums = set(old.enum_values), set(new.enum_values)
    td.enum_added = sorted(new_enums - old_enums)
    td.enum_removed = sorted(old_enums - new_enums)

    return td


def diff_schemas(old: Schema, new: Schema) -> SchemaDiff:
    result = SchemaDiff(
        query_type=new.query_type or old.query_type,
        mutation_type=new.mutation_type or old.mutation_type,
    )

    for name in sorted(new.types.keys() - old.types.keys()):
        result.types_added.append(new.types[name])
    for name in sorted(old.types.keys() - new.types.keys()):
        result.types_removed.append(old.types[name])
    for name in sorted(old.types.keys() & new.types.keys()):
        td = _diff_type(old.types[name], new.types[name])
        if not td.empty:
            result.types_changed.append(td)

    return result
