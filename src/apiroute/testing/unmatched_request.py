from apiroute.testing.mock_call import MockCall


class UnmatchedRequest(AssertionError):
    """A MockTransport got a request that no route, queued response or handler answers."""

    def __init__(self, call: MockCall):
        self.call = call
        super().__init__(f"no mock response for {call.describe()}; queue one or add a route")
