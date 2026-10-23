from typing import Any

import httpx

from apiroute.soap.soap_fault import SoapFault
from apiroute.soap.soap_versions import SOAP_VERSIONS
from apiroute.soap.xml_dict import XmlDict


class SoapDecoder:
    """A route decoder that reads a SOAP envelope: the content of the Body's first element as
    a dict, or SoapFault for a Fault. Responses are parsed with defusedxml, which refuses
    entity expansion and external entities."""

    def __init__(self, namespace: str, version: str = "1.1"):
        self._envelope = SOAP_VERSIONS[version].envelope
        self._is_12 = version == "1.2"
        self._xml = XmlDict(namespace)

    def __call__(self, response: httpx.Response) -> Any:
        try:
            root = _parse(response.content)
        except Exception as error:
            raise SoapFault("Client", f"not a SOAP envelope: {error}", None, response) from error
        body = root.find(f"{{{self._envelope}}}Body")
        if body is None:
            raise SoapFault("Client", "the envelope has no Body", None, response)
        fault = body.find(f"{{{self._envelope}}}Fault")
        if fault is not None:
            raise self._fault(fault, response)
        if not response.is_success:
            raise SoapFault("Server", f"HTTP {response.status_code}", None, response)
        content = next(iter(body), None)
        return None if content is None else self._xml.value(content)

    def _fault(self, fault: Any, response: httpx.Response) -> SoapFault:
        if self._is_12:
            soap = self._envelope
            code = fault.findtext(f"{{{soap}}}Code/{{{soap}}}Value", "")
            reason = fault.findtext(f"{{{soap}}}Reason/{{{soap}}}Text", "")
            detail = fault.find(f"{{{soap}}}Detail")
        else:
            code = fault.findtext("faultcode", "")
            reason = fault.findtext("faultstring", "")
            detail = fault.find("detail")
        detail_value = None if detail is None else self._xml.value(detail)
        return SoapFault(code.strip(), reason.strip(), detail_value, response)


def _parse(content: bytes) -> Any:
    # defusedxml comes with the soap extra; generated SOAP clients need it at run time
    try:
        from defusedxml.ElementTree import fromstring
    except ImportError as error:
        raise RuntimeError("SOAP clients need defusedxml: pip install apiroute[soap]") from error
    return fromstring(content)
