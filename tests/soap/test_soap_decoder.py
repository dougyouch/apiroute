import httpx
import pytest

from apiroute.soap import SoapDecoder, SoapFault

ENV11 = "http://schemas.xmlsoap.org/soap/envelope/"
ENV12 = "http://www.w3.org/2003/05/soap-envelope"


def response(body: str, status=200, envelope=ENV11):
    content = f'<s:Envelope xmlns:s="{envelope}"><s:Body>{body}</s:Body></s:Envelope>'
    return httpx.Response(status, content=content.encode())


def test_returns_the_first_body_elements_content():
    decoded = SoapDecoder("http://ws.test/")(
        response(
            '<r:PingResponse xmlns:r="http://ws.test/"><r:Result>pong</r:Result></r:PingResponse>'
        )
    )
    assert decoded == {"Result": "pong"}


def test_soap_11_fault():
    fault = (
        "<s:Fault><faultcode>s:Client</faultcode><faultstring>Bad city</faultstring>"
        "<detail><Code>42</Code></detail></s:Fault>"
    )
    with pytest.raises(SoapFault, match="Bad city") as raised:
        SoapDecoder("http://ws.test/")(response(fault, 500))
    assert raised.value.code == "s:Client" and raised.value.detail == {"Code": "42"}


def test_soap_12_fault():
    fault = (
        "<s:Fault><s:Code><s:Value>s:Sender</s:Value></s:Code>"
        "<s:Reason><s:Text>Nope</s:Text></s:Reason></s:Fault>"
    )
    with pytest.raises(SoapFault) as raised:
        SoapDecoder("http://ws.test/", "1.2")(response(fault, 500, ENV12))
    assert (raised.value.code, raised.value.reason) == ("s:Sender", "Nope")


def test_error_status_without_a_fault_and_non_xml_bodies():
    with pytest.raises(SoapFault, match="HTTP 500"):
        SoapDecoder("http://ws.test/")(response("<x/>", 500))
    with pytest.raises(SoapFault, match="not a SOAP envelope"):
        SoapDecoder("http://ws.test/")(httpx.Response(200, content=b"<html>"))


def test_entity_expansion_is_refused():
    bomb = (
        b'<?xml version="1.0"?><!DOCTYPE lol [<!ENTITY lol "lol">'
        b'<!ENTITY lol2 "&lol;&lol;">]><s:Envelope xmlns:s="'
        + ENV11.encode()
        + b'"><s:Body>&lol2;</s:Body></s:Envelope>'
    )
    with pytest.raises(SoapFault, match="not a SOAP envelope"):
        SoapDecoder("http://ws.test/")(httpx.Response(200, content=bomb))
