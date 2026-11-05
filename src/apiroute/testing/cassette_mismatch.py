class CassetteMismatch(AssertionError):
    """A request during replay that no unplayed recorded interaction matches: the code now
    makes a request it didn't when the cassette was recorded. Record it again (mode="record",
    or delete the file) if the change is intended."""
