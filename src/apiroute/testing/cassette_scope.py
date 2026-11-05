from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from apiroute.testing.async_recording_transport import AsyncRecordingTransport
from apiroute.testing.cassette import Cassette
from apiroute.testing.mock_transport import MockTransport
from apiroute.testing.recording_transport import RecordingTransport
from apiroute.testing.sleep_recording import recorded_sleeps
from apiroute.testing.transport_installation import installed
from apiroute.transports.async_one_shot_transport import AsyncOneShotTransport
from apiroute.transports.one_shot_transport import OneShotTransport

MODES = ("once", "record", "replay")


@contextmanager
def cassette(
    path: str | Path,
    *,
    mode: str = "once",
    match_body: bool = False,
    redact: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    check: Any = None,
    assert_all_played: bool = False,
    transport: Any = None,
    async_transport: Any = None,
) -> Iterator[Cassette]:
    """Records every client's real responses to a file the first time, and replays them
    afterwards, so a test runs against what the API really said without reaching it again:

        def test_get_user():
            with cassette("tests/cassettes/get_user.json"):
                assert GitHub().get_user("octocat")["login"] == "octocat"

    mode="once" replays the file when it exists and records it when it doesn't; "record"
    always records (sending real requests, through transport/async_transport when given),
    replacing the file when the block ends without an error; "replay" requires the file.

    Requests are matched to recordings by method and URL (and body, with match_body=True),
    each recording played once, in order; a request nothing matches raises CassetteMismatch.
    Credentials are kept out of the file: Authorization, Cookie and any request header whose
    name looks secret (token, key, secret ...) are saved as "[REDACTED]", as are Set-Cookie
    and secret-looking query values (matched in the same masked form). For secrets elsewhere,
    such as in bodies, redact is called with each interaction's JSON to return a scrubbed one.
    check (a ResponseSchemas) validates replayed responses against the spec's models.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    tape = Cassette(path, match_body=match_body, redact=redact)
    if mode == "replay" or (mode == "once" and tape.exists):
        yield from _replaying(tape, check, assert_all_played)
    else:
        yield from _recording(tape, transport, async_transport)


def _replaying(tape: Cassette, check: Any, assert_all_played: bool) -> Iterator[Cassette]:
    tape.load()
    mock = MockTransport(tape.play, check=check)
    with installed(mock, mock.aio), recorded_sleeps(mock.sleeps):
        yield tape
    if assert_all_played and tape.unplayed:
        raise AssertionError(f"{tape.path}: {len(tape.unplayed)} recordings were never replayed")


def _recording(tape: Cassette, transport: Any, async_transport: Any) -> Iterator[Cassette]:
    sync = RecordingTransport(transport or OneShotTransport(), tape.record)
    asynchronous = AsyncRecordingTransport(async_transport or AsyncOneShotTransport(), tape.record)
    with installed(sync, asynchronous):
        yield tape
    tape.save()
