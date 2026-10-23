import ssl

from apiroute.transports.httpx_client_factory import HttpxClientFactory


def test_builds_one_ssl_context_and_shares_it():
    factory = HttpxClientFactory(http2=False)
    context = factory._options["verify"]
    assert isinstance(context, ssl.SSLContext)
    factory.new_client()
    assert factory._options["verify"] is context


def test_leaves_verify_false_and_given_contexts_alone():
    context = ssl.create_default_context()
    assert HttpxClientFactory(verify=False)._options["verify"] is False
    assert HttpxClientFactory(verify=context)._options["verify"] is context


def test_passes_options_to_each_client(mock):
    client = HttpxClientFactory(transport=mock, follow_redirects=True).new_client()
    assert client.follow_redirects is True
