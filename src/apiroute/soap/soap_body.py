import xml.etree.ElementTree as ElementTree
from typing import Any

from apiroute.soap.soap_versions import SOAP_VERSIONS
from apiroute.soap.xml_dict import XmlDict


class SoapBody:
    """A body_format that wraps the body dict in a SOAP envelope:

        @route("POST", "", body_format=SoapBody("GetWeather", "http://ws.test/", "1.1"), ...)

    element and namespace name the operation's input element; version is "1.1" or "1.2".
    For 1.2 the action travels in the Content-Type, for 1.1 in a SOAPAction header (which the
    generated route sets).

    When the client has a soap_header(operation) method, the dict it returns (in the same
    shape as bodies) is sent in the envelope's Header: that is where services such as eBay's
    Trading API expect credentials."""

    encodes_empty = True  # an operation without arguments still sends an envelope

    def __init__(
        self,
        element: str,
        namespace: str,
        version: str = "1.1",
        qualified: bool = True,
        action: str | None = None,
        operation: str | None = None,
    ):
        self._element = element
        self._version = SOAP_VERSIONS[version]
        self._is_12 = version == "1.2"
        self._xml = XmlDict(namespace, qualified)
        self._action = action
        self._operation = operation or element

    def __call__(self, client: Any, data: Any) -> tuple[bytes, str]:
        soap = self._version.envelope
        envelope = ElementTree.Element(f"{{{soap}}}Envelope")
        self._add_header(envelope, client)
        body = ElementTree.SubElement(envelope, f"{{{soap}}}Body")
        body.append(self._xml.element(self._element, data or {}))
        content = ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True)
        content_type = self._version.content_type
        if self._is_12 and self._action:
            content_type = f'{content_type}; action="{self._action}"'
        return content, content_type

    def _add_header(self, envelope: ElementTree.Element, client: Any) -> None:
        soap_header = getattr(client, "soap_header", None)
        content = soap_header(self._operation) if callable(soap_header) else None
        if not content:
            return
        header = ElementTree.SubElement(envelope, f"{{{self._version.envelope}}}Header")
        for name, value in content.items():
            header.append(self._xml.element(name, value))
