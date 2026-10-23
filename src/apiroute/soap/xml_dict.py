import xml.etree.ElementTree as ElementTree
from typing import Any

# Elements and attributes are built with the standard library; documents are parsed with
# defusedxml (see SoapDecoder), since responses come from the network.


class XmlDict:
    """Converts between XML elements and dicts in the xmltodict shape: child elements are
    keys, "@name" attributes, "#text" text, lists repeat an element, and "{ns}local" keys
    name an element outside the body's namespace.

    namespace is the one unprefixed keys belong to; qualified says whether child elements are
    in it (an XSD's elementFormDefault) or in no namespace."""

    def __init__(self, namespace: str, qualified: bool = True):
        self._namespace = namespace
        self._qualified = qualified

    def element(self, tag: str, value: Any, top: bool = True) -> ElementTree.Element:
        element = ElementTree.Element(self._tag(tag, top))
        self._fill(element, value)
        return element

    def value(self, element: ElementTree.Element) -> Any:
        """An element's content: a dict when it has attributes or children, else its text.
        xsi: attributes are instructions, not data: xsi:nil="true" reads as None."""
        if _is_nil(element):
            return None
        result: dict[str, Any] = {
            f"@{_local(k)}": v for k, v in element.attrib.items() if not k.startswith(_XSI_TAG)
        }
        for child in element:
            key = self._key(child.tag)
            value = self.value(child)
            if key in result:
                existing = result[key]
                result[key] = (
                    [*existing, value] if isinstance(existing, list) else [existing, value]
                )
            else:
                result[key] = value
        text = (element.text or "").strip()
        if not result:
            return text
        if text:
            result["#text"] = text
        return result

    def _fill(self, element: ElementTree.Element, value: Any) -> None:
        if not isinstance(value, dict):
            element.text = _text(value)
            return
        for key, item in value.items():
            if item is None:
                continue
            if key.startswith("@"):
                element.set(key[1:], _text(item))
            elif key == "#text":
                element.text = _text(item)
            else:
                for one in item if isinstance(item, list) else [item]:
                    child = ElementTree.SubElement(element, self._tag(key, top=False))
                    self._fill(child, one)

    def _tag(self, key: str, top: bool) -> str:
        if key.startswith("{"):
            return key
        if top or self._qualified:
            return f"{{{self._namespace}}}{key}" if self._namespace else key
        return key

    def _key(self, tag: str) -> str:
        if tag.startswith("{"):
            namespace, local = tag[1:].split("}", 1)
            return local if namespace == self._namespace else tag
        return tag


def _local(name: str) -> str:
    return name.split("}", 1)[1] if name.startswith("{") else name


_XSI_TAG = "{http://www.w3.org/2001/XMLSchema-instance}"


def _is_nil(element: ElementTree.Element) -> bool:
    return element.get(f"{_XSI_TAG}nil") in ("true", "1")


def _text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)
