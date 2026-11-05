from collections.abc import Callable
from typing import Any

from apiroute.streaming.line_decoder import LineDecoder
from apiroute.streaming.ndjson_decoder import NdjsonDecoder
from apiroute.streaming.sse_decoder import SseDecoder

# The stream= modes that decode the body as it arrives, each a factory taking the route's
# item converter
STREAM_DECODERS: dict[str, Callable[[Any], Any]] = {
    "lines": lambda converter: LineDecoder(),
    "ndjson": NdjsonDecoder,
    "sse": lambda converter: SseDecoder(),
}

# The modes whose iterator reconnects after the connection fails mid-body
RECONNECTING_STREAMS = frozenset({"sse"})
