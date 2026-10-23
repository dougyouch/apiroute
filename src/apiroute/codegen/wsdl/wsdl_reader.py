from typing import Any

from apiroute.codegen.api_definition import (
    ApiDefinition,
    Group,
    Operation,
    RequestBody,
    SoapOperation,
)
from apiroute.codegen.python_names import snake_case, unique
from apiroute.codegen.wsdl.qnames import SOAP11, SOAP12, WSDL, qualified, resolve
from apiroute.codegen.wsdl.wsdl_document import QName, WsdlDocument, WsdlLoader
from apiroute.codegen.wsdl.xsd_mapper import XsdMapper


class WsdlReader:
    """Reads a WSDL 1.1 document into an ApiDefinition: the first SOAP port of its first
    service (SOAP 1.1 preferred when a service offers both), one POST route per operation.
    Only document/literal bindings are supported."""

    def __init__(self, location: str, client_name: str, loader: WsdlLoader | None = None):
        self._location = location
        self._client_name = client_name
        self._loader = loader or WsdlLoader()

    def read(self) -> ApiDefinition:
        document = self._loader.load(self._location)
        address, binding, version = self._port(document)
        definition = ApiDefinition(
            client_name=self._client_name,
            base_url=address,
            title=document.title or self._client_name,
            source=self._location.rsplit("/", 1)[-1],
            root=Group("", self._client_name),
        )
        binding_element, namespaces = document.bindings[binding]
        port_type = resolve(binding_element.get("type"), namespaces, document.target_namespace)
        mapper = XsdMapper(document, definition.models, self._body_namespace(document, port_type))
        _check_style(binding_element, version)
        taken: set[str] = set()
        for operation in binding_element.findall(qualified("operation", WSDL)):
            definition.root.operations.append(
                self._operation(document, mapper, operation, port_type, version, taken)
            )
        return definition

    def _body_namespace(self, document: WsdlDocument, port_type: QName) -> str:
        port_element, _ = document.port_types[port_type]
        first = port_element.find(qualified("operation", WSDL))
        if first is None:
            return document.target_namespace
        return self._elements(document, port_type, first.get("name"))[0][0]

    def _port(self, document: WsdlDocument) -> tuple[str, QName, str]:
        """(address, binding name, SOAP version) of the port to generate."""
        ports = []
        for service, namespaces in document.services:
            for port in service.findall(qualified("port", WSDL)):
                for version, namespace in (("1.1", SOAP11), ("1.2", SOAP12)):
                    address = port.find(qualified("address", namespace))
                    if address is not None:
                        binding = resolve(
                            port.get("binding"), namespaces, document.target_namespace
                        )
                        ports.append((version, address.get("location"), binding))
        if not ports:
            raise ValueError("the WSDL has no SOAP port (wsdl:service/wsdl:port/soap:address)")
        version, address, binding = sorted(ports, key=lambda p: p[0])[0]
        return address, binding, version

    def _operation(
        self,
        document: WsdlDocument,
        mapper: XsdMapper,
        operation: Any,
        port_type: QName,
        version: str,
        taken: set[str],
    ) -> Operation:
        name = operation.get("name")
        soap_namespace = SOAP12 if version == "1.2" else SOAP11
        soap_operation = operation.find(qualified("operation", soap_namespace))
        action = soap_operation.get("soapAction", "") if soap_operation is not None else ""
        input_element, output_element = self._elements(document, port_type, name)
        schema = mapper.element_schema(input_element)
        body_type = mapper.element_content(input_element)
        response = mapper.element_content(output_element) if output_element else None
        result = Operation(
            name=unique(snake_case(name), taken),
            method="POST",
            path="",
            summary=self._documentation(document, port_type, name),
            body=RequestBody(type=body_type, required=False, plain="dict[str, Any]"),
            response=response,
            response_plain=_plain(response) if output_element else "None",
            headers={"SOAPAction": f'"{action}"'} if version == "1.1" else {},
            operation_id=name,
            soap=SoapOperation(
                element=input_element[1],
                namespace=input_element[0],
                version=version,
                qualified=schema.qualified,
                action=action,
                response_namespace=output_element[0] if output_element else input_element[0],
            ),
        )
        if result.response is not None and result.response.expr == "Any":
            result.response = None
        return result

    def _documentation(self, document: WsdlDocument, port_type: QName, name: str) -> str:
        """Operations are documented on the port type, not the binding."""
        port_element, _ = document.port_types[port_type]
        for operation in port_element.findall(qualified("operation", WSDL)):
            if operation.get("name") == name:
                return _documentation(operation)
        return ""

    def _elements(
        self, document: WsdlDocument, port_type: QName, name: str
    ) -> tuple[QName, QName | None]:
        """The input and output message elements of a port type operation."""
        port_element, namespaces = document.port_types[port_type]
        for operation in port_element.findall(qualified("operation", WSDL)):
            if operation.get("name") != name:
                continue
            found = []
            for kind in ("input", "output"):
                message = operation.find(qualified(kind, WSDL))
                found.append(
                    None if message is None else self._part_element(document, message, namespaces)
                )
            if found[0] is None:
                raise ValueError(f"operation {name} has no input element")
            return found[0], found[1]
        raise ValueError(f"operation {name} isn't in its port type")

    def _part_element(self, document: WsdlDocument, message: Any, namespaces: dict) -> QName:
        message_name = resolve(message.get("message"), namespaces, document.target_namespace)
        message_element, message_namespaces = document.messages[message_name]
        part = message_element.find(qualified("part", WSDL))
        if part is None or not part.get("element"):
            raise ValueError(
                f"message {message_name[1]} has no element part; only document/literal is supported"
            )
        return resolve(part.get("element"), message_namespaces, document.target_namespace)


def _plain(response: Any) -> str:
    """The dict layer's return type: a dict for complex content, else plain text values."""
    return "dict[str, Any]" if response is not None and response.models else "Any"


def _check_style(binding: Any, version: str) -> None:
    soap = binding.find(qualified("binding", SOAP12 if version == "1.2" else SOAP11))
    if soap is not None and soap.get("style", "document") != "document":
        raise ValueError(
            f"{soap.get('style')}-style bindings aren't supported, only document/literal"
        )


def _documentation(element: Any) -> str:
    node = element.find(qualified("documentation", WSDL))
    return " ".join((node.text or "").split()) if node is not None else ""
