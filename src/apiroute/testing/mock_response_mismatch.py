class MockResponseMismatch(AssertionError):
    """A mocked or replayed response doesn't fit the model the API's spec declares for its
    operation: the mock has drifted from the API (or the spec from the mock)."""
