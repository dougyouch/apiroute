import io
from dataclasses import dataclass, field
from typing import Any

from apiroute.codegen.openapi.spec_loader import SpecLoader
from apiroute.codegen.wsdl.qnames import WSDL, XSD, qualified

QName = tuple[str, str]  # (namespace, local name)


@dataclass
class Schema:
    """One xs:schema: its target namespace, element form and the prefixes in scope."""

    element: Any
    target_namespace: str
    qualified: bool
    namespaces: dict[str, str]


@dataclass
class WsdlDocument:
    """A WSDL and everything it imports, indexed by qualified name."""

    target_namespace: str = ""
    namespaces: dict[str, str] = field(default_factory=dict)
    messages: dict[QName, Any] = field(default_factory=dict)
    port_types: dict[QName, Any] = field(default_factory=dict)
    bindings: dict[QName, Any] = field(default_factory=dict)
    services: list[Any] = field(default_factory=list)
    elements: dict[QName, tuple[Any, Schema]] = field(default_factory=dict)
    complex_types: dict[QName, tuple[Any, Schema]] = field(default_factory=dict)
    simple_types: dict[QName, tuple[Any, Schema]] = field(default_factory=dict)
    groups: dict[QName, tuple[Any, Schema]] = field(default_factory=dict)
    attribute_groups: dict[QName, tuple[Any, Schema]] = field(default_factory=dict)
    title: str = ""


class WsdlLoader:
    """Loads a WSDL with defusedxml, following wsdl:import, xs:import and xs:include."""

    def __init__(self, loader: SpecLoader | None = None):
        self._loader = loader or SpecLoader()
        self._seen: set[str] = set()

    def load(self, location: str) -> WsdlDocument:
        document = WsdlDocument()
        self._load_wsdl(location, document, top=True)
        return document

    def _load_wsdl(self, location: str, document: WsdlDocument, top: bool) -> None:
        if location in self._seen:
            return
        self._seen.add(location)
        root, namespaces = self._parse(location)
        target = root.get("targetNamespace", "")
        if top:
            document.target_namespace = target
            document.namespaces = namespaces
            document.title = root.get("name", "")
        for kind, index in (
            ("message", document.messages),
            ("portType", document.port_types),
            ("binding", document.bindings),
        ):
            for element in root.findall(qualified(kind, WSDL)):
                index[(target, element.get("name"))] = (element, namespaces)
        document.services += [(s, namespaces) for s in root.findall(qualified("service", WSDL))]
        for types in root.findall(qualified("types", WSDL)):
            for schema in types.findall(qualified("schema", XSD)):
                self._add_schema(schema, namespaces, location, document)
        for imported in root.findall(qualified("import", WSDL)):
            if imported.get("location"):
                self._load_wsdl(
                    self._loader.join(location, imported.get("location")), document, False
                )

    def _add_schema(
        self, schema: Any, namespaces: dict, location: str, document: WsdlDocument
    ) -> None:
        info = Schema(
            schema,
            schema.get("targetNamespace", ""),
            schema.get("elementFormDefault") == "qualified",
            namespaces,
        )
        indexes = {
            "element": document.elements,
            "complexType": document.complex_types,
            "simpleType": document.simple_types,
            "group": document.groups,
            "attributeGroup": document.attribute_groups,
        }
        for kind, index in indexes.items():
            for element in schema.findall(qualified(kind, XSD)):
                index[(info.target_namespace, element.get("name"))] = (element, info)
        for kind in ("import", "include"):
            for imported in schema.findall(qualified(kind, XSD)):
                if imported.get("schemaLocation"):
                    self._load_schema(
                        self._loader.join(location, imported.get("schemaLocation")),
                        document,
                        info.target_namespace if kind == "include" else None,
                    )

    def _load_schema(self, location: str, document: WsdlDocument, include_into: str | None) -> None:
        if location in self._seen:
            return
        self._seen.add(location)
        root, namespaces = self._parse(location)
        if include_into is not None and not root.get("targetNamespace"):
            root.set("targetNamespace", include_into)  # a chameleon include
        self._add_schema(root, namespaces, location, document)

    def _parse(self, location: str) -> tuple[Any, dict[str, str]]:
        text = self._loader.read_text(location)
        return _parse(text), _prefixes(text)


def _parse(text: str) -> Any:
    from defusedxml.ElementTree import fromstring  # the codegen extra

    return fromstring(text.encode())


def _prefixes(text: str) -> dict[str, str]:
    """Every xmlns declaration in the document. ElementTree drops prefixes, but WSDL and XSD
    name types with them (type="tns:Weather"); one prefix meaning two things is rare enough
    that the first declaration wins."""
    from defusedxml.ElementTree import iterparse

    prefixes: dict[str, str] = {}
    for _, (prefix, uri) in iterparse(io.BytesIO(text.encode()), events=("start-ns",)):
        prefixes.setdefault(prefix, uri)
    return prefixes
