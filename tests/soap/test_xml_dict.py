import xml.etree.ElementTree as ElementTree

from apiroute.soap.xml_dict import XmlDict

NS = "http://ws.test/"


def xml(element):
    return ElementTree.tostring(element, encoding="unicode")


def test_dict_to_element_with_attributes_text_lists_and_other_namespaces():
    element = XmlDict(NS).element(
        "Order",
        {
            "@id": 7,
            "Item": [{"Name": "a"}, {"Name": "b"}],
            "Note": {"#text": "hi", "@lang": "en"},
            "{http://other.test/}Tag": True,
            "Skipped": None,
        },
    )
    assert xml(element) == (
        '<ns0:Order xmlns:ns0="http://ws.test/" xmlns:ns1="http://other.test/" id="7">'
        "<ns0:Item><ns0:Name>a</ns0:Name></ns0:Item><ns0:Item><ns0:Name>b</ns0:Name></ns0:Item>"
        '<ns0:Note lang="en">hi</ns0:Note><ns1:Tag>true</ns1:Tag></ns0:Order>'
    )


def test_unqualified_children_have_no_namespace():
    element = XmlDict(NS, qualified=False).element("Order", {"Name": "a"})
    assert xml(element) == '<ns0:Order xmlns:ns0="http://ws.test/"><Name>a</Name></ns0:Order>'


def test_element_to_dict():
    element = ElementTree.fromstring(
        '<o:Order xmlns:o="http://ws.test/" xmlns:x="http://other.test/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" id="7">'
        "<o:Item>a</o:Item><o:Item>b</o:Item><o:Note lang='en'>hi</o:Note><x:Tag>t</x:Tag>"
        "<o:Empty/><o:Nil xsi:nil='true'/></o:Order>"
    )
    assert XmlDict(NS).value(element) == {
        "@id": "7",
        "Item": ["a", "b"],
        "Note": {"@lang": "en", "#text": "hi"},
        "{http://other.test/}Tag": "t",
        "Empty": "",
        "Nil": None,
    }
