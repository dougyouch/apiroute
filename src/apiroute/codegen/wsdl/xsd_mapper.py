from typing import Any

from apiroute.codegen.api_definition import Model, ModelField
from apiroute.codegen.python_names import MODEL_RESERVED, pascal_case, snake_case, unique
from apiroute.codegen.type_ref import ANY, TypeRef
from apiroute.codegen.wsdl.qnames import XSD, qualified, resolve
from apiroute.codegen.wsdl.wsdl_document import QName, Schema, WsdlDocument

_BUILTINS = {
    **dict.fromkeys(
        [
            "string",
            "normalizedString",
            "token",
            "anyURI",
            "QName",
            "NOTATION",
            "language",
            "Name",
            "NCName",
            "ID",
            "IDREF",
            "IDREFS",
            "ENTITY",
            "ENTITIES",
            "NMTOKEN",
            "NMTOKENS",
            "dateTime",
            "date",
            "time",
            "duration",
            "gYear",
            "gYearMonth",
            "gMonth",
            "gMonthDay",
            "gDay",
            "base64Binary",
            "hexBinary",
        ],
        "str",
    ),
    **dict.fromkeys(
        [
            "int",
            "integer",
            "long",
            "short",
            "byte",
            "nonNegativeInteger",
            "nonPositiveInteger",
            "positiveInteger",
            "negativeInteger",
            "unsignedLong",
            "unsignedInt",
            "unsignedShort",
            "unsignedByte",
        ],
        "int",
    ),
    **dict.fromkeys(["decimal", "float", "double"], "float"),
    "boolean": "bool",
    "anyType": "Any",
    "anySimpleType": "str",
}

# A list field accepts a lone item too: XML can't tell a one-item list from a single value
_LIST = "Annotated[list[{item}], BeforeValidator(as_list)]"


class XsdMapper:
    """Turns XSD elements and types into pydantic models in the xmltodict shape: element
    fields aliased by their local names, attributes by "@name", simple content by "#text"."""

    def __init__(self, document: WsdlDocument, models: dict[str, Model], body_namespace: str):
        """body_namespace is the operations' namespace: elements in it (or in none) are keyed by
        local name; elements from other namespaces by "{namespace}local", as XmlDict reads them."""
        self._document = document
        self._models = models
        self._body_namespace = body_namespace
        self._named: dict[tuple[str, QName], str] = {}
        self._taken: set[str] = set()

    def element_content(self, name: QName) -> TypeRef:
        """The type of a top-level element's content: what a SOAP body holds inside it."""
        element, schema = self._document.elements[name]
        return self._element_type(element, schema, pascal_case(name[1]))

    def element_schema(self, name: QName) -> Schema:
        return self._document.elements[name][1]

    def _element_type(self, element: Any, schema: Schema, hint: str) -> TypeRef:
        if element.get("type"):
            return self._type(
                resolve(element.get("type"), schema.namespaces, schema.target_namespace), hint
            )
        complex_type = element.find(qualified("complexType", XSD))
        if complex_type is not None:
            return self._complex(complex_type, schema, hint, named=None)
        simple_type = element.find(qualified("simpleType", XSD))
        if simple_type is not None:
            return self._simple(simple_type, schema)
        return ANY

    def _type(self, name: QName, hint: str) -> TypeRef:
        namespace, local = name
        if namespace == XSD:
            return TypeRef(_BUILTINS.get(local, "str"))
        if name in self._document.complex_types:
            element, schema = self._document.complex_types[name]
            return self._complex(element, schema, pascal_case(local), named=name)
        if name in self._document.simple_types:
            element, schema = self._document.simple_types[name]
            return self._named_simple(element, schema, name)
        return TypeRef("str")

    def _complex(self, element: Any, schema: Schema, hint: str, named: QName | None) -> TypeRef:
        key = ("complex", named) if named else None
        if key in self._named:
            return TypeRef.model(self._named[key])
        name = unique(pascal_case(hint), self._taken, frozenset())
        if key:
            self._named[key] = name  # before the fields, so recursive types refer to it
        model = Model(name, description=_documentation(element))
        self._models[name] = model
        model.fields = self._fields(element, schema, name)
        return TypeRef.model(name)

    def _fields(self, complex_type: Any, schema: Schema, model_name: str) -> list[ModelField]:
        taken: set[str] = set()
        fields: list[ModelField] = []
        self._collect(complex_type, schema, model_name, fields, taken, optional=False)
        return fields

    def _collect(
        self, node: Any, schema: Schema, model: str, fields: list, taken: set, optional: bool
    ) -> None:
        for child in node:
            tag = child.tag
            if tag in (qualified("sequence", XSD), qualified("all", XSD)):
                self._collect(child, schema, model, fields, taken, optional or _min(child) == 0)
            elif tag == qualified("choice", XSD):
                self._collect(child, schema, model, fields, taken, optional=True)
            elif tag == qualified("group", XSD) and child.get("ref"):
                group = self._document.groups.get(resolve(child.get("ref"), schema.namespaces))
                if group is not None:
                    self._collect(group[0], group[1], model, fields, taken, optional)
            elif tag == qualified("element", XSD):
                fields.append(self._element_field(child, schema, model, taken, optional))
            elif tag == qualified("attribute", XSD):
                attribute = self._attribute_field(child, schema, model, taken)
                if attribute is not None:
                    fields.append(attribute)
            elif tag == qualified("attributeGroup", XSD) and child.get("ref"):
                group = self._document.attribute_groups.get(
                    resolve(child.get("ref"), schema.namespaces)
                )
                if group is not None:
                    self._collect(group[0], group[1], model, fields, taken, optional)
            elif tag in (qualified("complexContent", XSD), qualified("simpleContent", XSD)):
                self._content(child, schema, model, fields, taken)

    def _content(self, content: Any, schema: Schema, model: str, fields: list, taken: set) -> None:
        derivation = next(iter(content), None)
        if derivation is None:
            return
        base = resolve(derivation.get("base", ""), schema.namespaces, schema.target_namespace)
        if content.tag == qualified("simpleContent", XSD):
            text = ModelField(
                unique("value", taken, MODEL_RESERVED), "#text", self._text(base, model), False
            )
            fields.append(text)
        elif base in self._document.complex_types:
            base_element, base_schema = self._document.complex_types[base]
            self._collect(base_element, base_schema, model, fields, taken, optional=False)
        self._collect(derivation, schema, model, fields, taken, optional=False)

    def _text(self, base: QName, model: str) -> TypeRef:
        """The type of simple content: a built-in or simple type; a complex base is text."""
        if base[0] == XSD or base in self._document.simple_types:
            return self._type(base, f"{model}Text")
        return TypeRef("str")

    def _element_field(
        self, element: Any, schema: Schema, model: str, taken: set, optional: bool
    ) -> ModelField:
        if element.get("ref"):
            name = resolve(element.get("ref"), schema.namespaces, schema.target_namespace)
            target, target_schema = self._document.elements.get(name, (element, schema))
            wire = self._wire_name(name[0], name[1])
            item = self._element_type(target, target_schema, f"{model}{pascal_case(name[1])}")
        else:
            local = element.get("name")
            wire = self._wire_name(_element_namespace(element, schema), local)
            item = self._element_type(element, schema, f"{model}{pascal_case(local)}")
        if _max(element) > 1:
            item = TypeRef.of(_LIST.format(item=item.expr), item)
        python = unique(snake_case(wire.rsplit("}", 1)[-1]), taken, MODEL_RESERVED)
        required = not optional and _min(element) > 0 and element.get("nillable") != "true"
        return ModelField(
            python, None if python == wire else wire, item, required, _documentation(element)
        )

    def _wire_name(self, namespace: str, local: str) -> str:
        if namespace in ("", self._body_namespace):
            return local
        return f"{{{namespace}}}{local}"

    def _attribute_field(
        self, attribute: Any, schema: Schema, model: str, taken: set
    ) -> ModelField | None:
        if attribute.get("use") == "prohibited":
            return None
        name = attribute.get("name") or attribute.get("ref", "").rsplit(":", 1)[-1]
        if not name:
            return None
        if attribute.get("type"):
            item = self._type(
                resolve(attribute.get("type"), schema.namespaces, schema.target_namespace),
                f"{model}{pascal_case(name)}",
            )
        else:
            simple = attribute.find(qualified("simpleType", XSD))
            item = self._simple(simple, schema) if simple is not None else TypeRef("str")
        python = unique(snake_case(name), taken, MODEL_RESERVED)
        return ModelField(python, f"@{name}", item, attribute.get("use") == "required")

    def _named_simple(self, element: Any, schema: Schema, name: QName) -> TypeRef:
        key = ("simple", name)
        if key not in self._named:
            mapped = self._simple(element, schema)
            if not mapped.expr.startswith("Literal["):
                return mapped  # plain restrictions stay plain types
            alias = unique(pascal_case(name[1]), self._taken, frozenset())
            self._named[key] = alias
            self._models[alias] = Model(alias, description=_documentation(element), alias_of=mapped)
        return TypeRef.model(self._named[key])

    def _simple(self, element: Any, schema: Schema) -> TypeRef:
        restriction = element.find(qualified("restriction", XSD))
        if restriction is None:
            return TypeRef("str")  # lists and unions of simple types travel as text
        values = [e.get("value") for e in restriction.findall(qualified("enumeration", XSD))]
        if values:
            return TypeRef(f"Literal[{', '.join(repr(v) for v in values)}]")
        base = resolve(restriction.get("base", "xs:string"), schema.namespaces, XSD)
        return self._type(base, "Value") if base[0] == XSD else TypeRef("str")


def _min(element: Any) -> int:
    return int(element.get("minOccurs", "1"))


def _max(element: Any) -> float:
    value = element.get("maxOccurs", "1")
    return float("inf") if value == "unbounded" else int(value)


def _documentation(element: Any) -> str:
    node = element.find(f"{qualified('annotation', XSD)}/{qualified('documentation', XSD)}")
    return " ".join((node.text or "").split()) if node is not None else ""


def _element_namespace(element: Any, schema: Schema) -> str:
    """A local element's namespace: its schema's when qualified (form, else the schema's
    elementFormDefault), none otherwise."""
    form = element.get("form")
    qualified_form = form == "qualified" or (form is None and schema.qualified)
    return schema.target_namespace if qualified_form else ""
