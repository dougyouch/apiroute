import pytest

sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)


@pytest.fixture
def exporter():
    return InMemorySpanExporter()


@pytest.fixture
def provider(exporter):
    provider = sdk_trace.TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider
