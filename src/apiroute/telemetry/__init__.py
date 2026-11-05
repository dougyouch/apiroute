"""Tracing requests: a client's `telemetry` setting (OpenTelemetry needs the otel extra)."""

from apiroute.telemetry.open_telemetry import OpenTelemetry

__all__ = ["OpenTelemetry"]
