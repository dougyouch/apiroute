import xml.etree.ElementTree as ElementTree
from typing import Any

from apiroute.soap.soap_versions import SOAP_VERSIONS
from apiroute.soap.xml_dict import XmlDict


class SoapBody:
    """A body_format that wraps the body dict in a SOAP envelope:

        @route("POST", "", body_format=SoapBody("GetWeather", "http://ws.test/", "1.1"), ...)

    element and namespace name the operation's input element; version is "1.1" or "1.2".
    For 1.2 the action travels in the Content-Type, for 1.1 in a SOAPAction header (which the
    generated route sets)."""

    def __init__(
        self,
        element: str,
        namespace: str,
        version: str = "1.1",
        qualified: bool = True,
        action: str | None = None,
    ):
        self._element = element
        self._version = SOAP_VERSIONS[version]
        self._is_12 = version == "1.2"
        self._xml = XmlDict(namespace, qualified)
        self._action = action

    def __call__(self, client: Any, data: Any) -> tuple[bytes, str]:
        soap = self._version.envelope
        envelope = ElementTree.Element(f"{{{soap}}}Envelope")
        body = ElementTree.SubElement(envelope, f"{{{soap}}}Body")
        body.append(self._xml.element(self._element, data or {}))
        content = ElementTree.tostring(envelope, encoding="utf-8", xml_declaration=True)
        content_type = self._version.content_type
        if self._is_12 and self._action:
            content_type = f'{content_type}; action="{self._action}"'
        return content, content_type
