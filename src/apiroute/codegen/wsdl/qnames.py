WSDL = "http://schemas.xmlsoap.org/wsdl/"
SOAP11 = "http://schemas.xmlsoap.org/wsdl/soap/"
SOAP12 = "http://schemas.xmlsoap.org/wsdl/soap12/"
XSD = "http://www.w3.org/2001/XMLSchema"


def qualified(tag: str, namespace: str) -> str:
    """Clark notation, the form ElementTree uses: {namespace}local"""
    return f"{{{namespace}}}{tag}"


def resolve(prefixed: str, namespaces: dict[str, str], default: str = "") -> tuple[str, str]:
    """A prefixed name ("tns:Weather") as (namespace, local), using the document's prefixes."""
    prefix, _, local = prefixed.rpartition(":")
    return (namespaces.get(prefix, default) if prefix else namespaces.get("", default)), local
