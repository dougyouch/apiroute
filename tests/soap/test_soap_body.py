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


class Credentials:
    def __init__(self):
        self.asked = []

    def soap_header(self, operation):
        self.asked.append(operation)
        return {"RequesterCredentials": {"eBayAuthToken": "t0k"}}


def test_soap_header_from_the_client():
    client = Credentials()
    content, _ = SoapBody("GetItemRequest", "urn:ebay", operation="GetItem")(client, {"ItemID": 1})
    assert client.asked == ["GetItem"]
    header_end = content.index(b"Header>") + 7
    body_start = content.index(b"Body>")
    assert b"<ns1:RequesterCredentials><ns1:eBayAuthToken>t0k</ns1:eBayAuthToken>" in content
    assert header_end < body_start  # the Header comes before the Body


def test_no_header_without_the_hook():
    content, _ = SoapBody("Ping", "urn:x")(object(), None)
    assert b"Header" not in content
