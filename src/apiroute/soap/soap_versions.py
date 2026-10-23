from typing import NamedTuple


class SoapVersion(NamedTuple):
    envelope: str  # the envelope namespace
    content_type: str


SOAP_VERSIONS = {
    "1.1": SoapVersion("http://schemas.xmlsoap.org/soap/envelope/", "text/xml; charset=utf-8"),
    "1.2": SoapVersion(
        "http://www.w3.org/2003/05/soap-envelope", "application/soap+xml; charset=utf-8"
    ),
}
