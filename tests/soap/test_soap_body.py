from apiroute.soap import SoapBody


def test_soap_11_envelope():
    content, content_type = SoapBody("Ping", "http://ws.test/")(None, {"Text": "hi"})
    assert content_type == "text/xml; charset=utf-8"
    assert content.startswith(b"<?xml version='1.0' encoding='utf-8'?>")
    assert b"http://schemas.xmlsoap.org/soap/envelope/" in content
    assert b"<ns1:Ping><ns1:Text>hi</ns1:Text></ns1:Ping>" in content


def test_soap_12_carries_the_action_in_the_content_type():
    _, content_type = SoapBody("Ping", "http://ws.test/", "1.2", action="urn:ping")(None, None)
    assert content_type == 'application/soap+xml; charset=utf-8; action="urn:ping"'
