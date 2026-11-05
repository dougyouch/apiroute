import dataclasses
from typing import Any

from apiroute.codegen.api_definition import Model, ModelField
from apiroute.codegen.openapi.ref_resolver import RefResolver
from apiroute.codegen.plain_text import plain_text
from apiroute.codegen.python_literals import py_str
from apiroute.codegen.python_names import MODEL_RESERVED, pascal_case, snake_case, unique
from apiroute.codegen.type_ref import ANY, TypeRef

_PRIMITIVES = {"string": "str", "integer": "int", "number": "float", "boolean": "bool"}


class SchemaMapper:
    """Turns JSON Schemas into Python types, adding a Model for every named schema and every
    inline object. A $ref is registered under its name before its body is mapped, so
    recursive schemas refer to themselves by name. With discriminators=True, a oneOf or anyOf
    with a discriminator becomes a tagged union."""

    def __init__(
        self, resolver: RefResolver, models: dict[str, Model], discriminators: bool = False
    ):
        self._resolver = resolver
        self._models = models
        self._discriminators = discriminators
        self._by_ref: dict[tuple[str, str], str] = {}
        self._taken: set[str] = set()

    def map(self, schema: Any, hint: str, base: str | None = None) -> TypeRef:
        """The type for schema; hint names any model created for an inline object."""
        if not isinstance(schema, dict) or not schema:
            return ANY
        if "$ref" in schema:
            return self._nullable_ref(schema, base)
        mapped = self._unnullable(schema, hint, base)
        return mapped.optional() if _is_nullable(schema) else mapped

    def plain(self, schema: Any, base: str | None = None) -> str:
        """The shape the dict layer annotates: a dict, a list, a primitive or Any."""
        schema, base = self._follow(schema, base)
        if not isinstance(schema, dict):
            return "Any"
        if "allOf" in schema and schema["allOf"]:
            return self.plain(schema["allOf"][0], base)
        kind = _type(schema)
        if kind == "object" or "properties" in schema or "additionalProperties" in schema:
            return "dict[str, Any]"
        if kind == "array":
            return "list[Any]"
        return _PRIMITIVES.get(kind, "Any")

    def register_named(self, name: str, ref: str, base: str | None = None) -> str:
        """Maps a named schema even if nothing references it (components.schemas)."""
        return self._ref(ref, base).expr

    def _unnullable(self, schema: dict, hint: str, base: str | None) -> TypeRef:
        if "const" in schema:
            return TypeRef(f"Literal[{schema['const']!r}]")
        if "enum" in schema:
            return _literal(schema["enum"])
        if "allOf" in schema:
            return self._all_of(schema, hint, base)
        for key in ("oneOf", "anyOf"):
            if key in schema:
                return self._union(schema[key], hint, base, schema.get("discriminator"))
        kinds = [k for k in _types(schema) if k != "null"]
        if len(kinds) > 1:
            options = [self._unnullable({**schema, "type": k}, hint, base) for k in kinds]
            return TypeRef.of(" | ".join(o.expr for o in options), *options)
        kind = kinds[0] if kinds else ("object" if "properties" in schema else None)
        if kind == "array":
            item = self.map(schema.get("items", {}), f"{hint}Item", base)
            return TypeRef.of(f"list[{item.expr}]", item)
        if kind == "object":
            return self._object(schema, hint, base)
        if kind == "string" and schema.get("format") == "binary":
            return ANY  # a file: bytes, an open file, or a (name, content, type) tuple
        return TypeRef(_PRIMITIVES.get(kind, "Any"))

    def _nullable_ref(self, schema: dict, base: str | None) -> TypeRef:
        """A $ref's model, or None when the schema it names is nullable (as GitHub's
        nullable-* components are), since the value may then be null wherever it's used."""
        mapped = self._ref(schema["$ref"], base)
        target = self._follow(schema, base)[0]
        return mapped.optional() if isinstance(target, dict) and _is_nullable(target) else mapped

    def _ref(self, ref: str, base: str | None) -> TypeRef:
        target, location, ref_name = self._resolver.resolve(ref, base)
        key = (location, ref.partition("#")[2])
        if key not in self._by_ref:
            name = unique(pascal_case(ref_name), self._taken, frozenset())
            self._by_ref[key] = name
            self._models[name] = self._named(name, target, location)
        return TypeRef.model(self._by_ref[key])

    def _named(self, name: str, schema: Any, base: str) -> Model:
        description = plain_text(schema.get("description", "")) if isinstance(schema, dict) else ""
        if isinstance(schema, dict) and _is_object_model(schema):
            if "allOf" in schema:
                own = {k: v for k, v in schema.items() if k != "allOf"}
                schema = self._merge([*schema["allOf"], own], base)
            fields = self._fields(schema, name, base)
            return Model(name, fields=fields, description=description)
        if self._discriminators and isinstance(schema, dict) and _is_tagged_union(schema):
            key = "oneOf" if "oneOf" in schema else "anyOf"
            union = self._union(schema[key], name, base, schema["discriminator"], named=True)
            alias = union.optional() if _is_nullable(schema) else union
        else:
            alias = self.map(schema, f"{name}Value", base)
        return Model(name, description=description, alias_of=alias)

    def _object(self, schema: dict, hint: str, base: str | None) -> TypeRef:
        if schema.get("properties"):
            name = unique(pascal_case(hint), self._taken, frozenset())
            fields = self._fields(schema, name, base)
            self._models[name] = Model(
                name, fields=fields, description=plain_text(schema.get("description", ""))
            )
            return TypeRef.model(name)
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict) and extra:
            value = self.map(extra, f"{hint}Value", base)
            return TypeRef.of(f"dict[str, {value.expr}]", value)
        return TypeRef("dict[str, Any]")

    def _all_of(self, schema: dict, hint: str, base: str | None) -> TypeRef:
        parts = schema["allOf"]
        extra = {k: v for k, v in schema.items() if k not in ("allOf", "description", "nullable")}
        if len(parts) == 1 and not extra:
            return self.map(parts[0], hint, base)
        merged = self._merge([*parts, extra], base)
        merged["description"] = schema.get("description", merged.get("description", ""))
        return self._object(merged, hint, base) if merged.get("properties") else ANY

    def _merge(self, parts: list[Any], base: str | None) -> dict:
        """allOf parts as one object schema: their properties and required lists combined."""
        merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
        for part in parts:
            part, part_base = self._follow(part, base)
            if not isinstance(part, dict):
                continue
            if "allOf" in part:
                part = self._merge(part["allOf"], part_base)
            merged["properties"].update(part.get("properties", {}))
            merged["required"] += [
                r for r in part.get("required", []) if r not in merged["required"]
            ]
            merged.setdefault("description", part.get("description", ""))
        return merged

    def _union(
        self,
        options: list[Any],
        hint: str,
        base: str | None,
        discriminator: Any = None,
        named: bool = False,
    ) -> TypeRef:
        """The options as a union. With a discriminator whose options are all models having
        its property, a tagged union pydantic picks the member of by that property: an alias
        model, or (for a named schema, named=True) the Annotated expression itself."""
        variants: list[tuple[Any, TypeRef]] = []
        nullable = False
        for index, option in enumerate(options, 1):
            if isinstance(option, dict) and _types(option) == ["null"]:
                nullable = True
                continue
            item = self.map(option, f"{hint}Option{index}", base)
            if item.expr not in {m.expr for _, m in variants}:
                variants.append((option, item))
        if not variants:
            return TypeRef("None")
        mapped = [item for _, item in variants]
        union = TypeRef.of(" | ".join(m.expr for m in mapped), *mapped)
        tagged = self._tagged(union, variants, discriminator, base)
        if tagged is not None and not named:
            name = unique(pascal_case(hint), self._taken, frozenset())
            self._models[name] = Model(name, alias_of=tagged)
            tagged = TypeRef.model(name)
        union = tagged or union
        return union.optional() if nullable else union

    def _tagged(
        self,
        union: TypeRef,
        variants: list[tuple[Any, TypeRef]],
        discriminator: Any,
        base: str | None,
    ) -> TypeRef | None:
        """The union tagged by an OpenAPI discriminator, each member's property typed as the
        Literal of the values naming it (its mapping entries, else its schema's name); None
        when the union can't be one: a member that isn't a model, or lacks the property."""
        if not self._discriminators or len(variants) < 2 or not isinstance(discriminator, dict):
            return None
        wire_name = discriminator.get("propertyName")
        if not isinstance(wire_name, str):
            return None
        named_by = self._mapping(discriminator.get("mapping"), base)
        tags = []
        for option, item in variants:
            model = self._models.get(item.expr)
            if model is None or model.alias_of is not None:
                return None
            field = next((f for f in model.fields if (f.alias or f.name) == wire_name), None)
            values = named_by.get(model.name) or self._implicit_tag(option, base)
            if field is None or not values:
                return None
            tags.append((model, field, values))
        if len({field.name for _, field, _ in tags}) != 1:
            return None
        for model, field, values in tags:
            _tag(model, field, values)
        expr = f"Annotated[{union.expr}, Field(discriminator={py_str(tags[0][1].name)})]"
        return TypeRef(expr, union.models)

    def _mapping(self, mapping: Any, base: str | None) -> dict[str, list[str]]:
        """A discriminator's mapping as model name -> the values naming it. Values may be
        refs or bare schema names."""
        named_by: dict[str, list[str]] = {}
        if not isinstance(mapping, dict):
            return named_by
        for value, target in mapping.items():
            if not isinstance(target, str):
                continue
            ref = target if "/" in target or "#" in target else f"#/components/schemas/{target}"
            named_by.setdefault(self._ref(ref, base).expr, []).append(str(value))
        return named_by

    def _implicit_tag(self, option: Any, base: str | None) -> list[str]:
        """The value naming a member with no mapping entry: its schema's name."""
        if not isinstance(option, dict) or "$ref" not in option:
            return []
        return [self._resolver.resolve(option["$ref"], base)[2]]

    def _fields(self, schema: dict, model_name: str, base: str | None) -> list[ModelField]:
        required = set(schema.get("required", []))
        taken: set[str] = set()
        fields = []
        for wire_name, property_schema in schema.get("properties", {}).items():
            name = unique(snake_case(wire_name), taken, MODEL_RESERVED)
            field_type = self.map(property_schema, f"{model_name}{pascal_case(wire_name)}", base)
            description = ""
            if isinstance(property_schema, dict):
                description = self._follow(property_schema, base)[0].get("description", "")
            fields.append(
                ModelField(
                    name=name,
                    alias=None if name == wire_name else wire_name,
                    type=field_type,
                    required=wire_name in required,
                    description=plain_text(description) if isinstance(description, str) else "",
                )
            )
        return fields

    def _follow(self, schema: Any, base: str | None) -> tuple[Any, str | None]:
        seen = set()
        while isinstance(schema, dict) and "$ref" in schema and schema["$ref"] not in seen:
            seen.add(schema["$ref"])
            schema, base, _ = self._resolver.resolve(schema["$ref"], base)
        return schema, base


def _types(schema: dict) -> list[str]:
    kind = schema.get("type")
    if isinstance(kind, list):
        return kind
    return [kind] if kind else []


def _type(schema: dict) -> str | None:
    kinds = [k for k in _types(schema) if k != "null"]
    return kinds[0] if kinds else None


def _is_nullable(schema: dict) -> bool:
    return schema.get("nullable") is True or "null" in _types(schema)


def _is_tagged_union(schema: dict) -> bool:
    return isinstance(schema.get("discriminator"), dict) and any(
        isinstance(schema.get(key), list) for key in ("oneOf", "anyOf")
    )


def _tag(model: Model, field: ModelField, values: list[str]) -> None:
    """Types a union member's discriminator field as the Literal of the values naming it,
    added to those of other unions it's in; it must then be present."""
    merged = tuple(dict.fromkeys([*field.discriminator, *values]))
    literal = TypeRef(f"Literal[{', '.join(repr(v) for v in merged)}]")
    tagged = dataclasses.replace(field, type=literal, required=True, discriminator=merged)
    model.fields = [tagged if f is field else f for f in model.fields]


def _is_object_model(schema: dict) -> bool:
    if "allOf" in schema and len(schema["allOf"]) > 1:
        return True
    return bool(schema.get("properties")) and not any(k in schema for k in ("oneOf", "anyOf"))


def _literal(values: list[Any]) -> TypeRef:
    present = [v for v in values if v is not None]
    if not present:
        return TypeRef("None")
    literal = TypeRef(f"Literal[{', '.join(repr(v) for v in present)}]")
    return literal.optional() if len(present) < len(values) else literal
