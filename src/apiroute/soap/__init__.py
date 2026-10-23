"""SOAP 1.1/1.2 support for generated WSDL clients: envelopes in, envelopes out.

Bodies are dicts in the common xmltodict shape: a child element is a key, "@name" an
attribute, "#text" an element's text, a list repeated elements, and "{namespace}local" an
element from another namespace. Needs the soap extra (defusedxml): pip install apiroute[soap].
"""

from apiroute.soap.soap_body import SoapBody
from apiroute.soap.soap_decoder import SoapDecoder
from apiroute.soap.soap_fault import SoapFault
from apiroute.soap.xml_list import as_list

__all__ = ["SoapBody", "SoapDecoder", "SoapFault", "as_list"]
