import httpx
import pytest

from apiroute import Client, Section, route
from apiroute.caching import ConditionalCache
from apiroute.rate_limiting import RateLimiter
from apiroute.testing.sleep_recording import recorded_sleeps


def test_a_revalidation_still_waits_for_the_rate_limiter(transport, recorder):
    class Api(Client):
        base_url = "https://x.test"
        conditional_cache = ConditionalCache()
        rate_limiter = RateLimiter(requests=1, per=1.0, clock=lambda: 0.0)
        get_x = route("/x")

    recorder.respond(
        httpx.Response(200, json={"a": 1}, headers={"ETag": '"e"'}), httpx.Response(304)
    )
    with recorded_sleeps() as sleeps:
        assert Api(transport=transport).get_x() == {"a": 1}
        assert Api(transport=transport).get_x() == {"a": 1}
    assert sleeps == [1.0]
    assert recorder.last.headers["If-None-Match"] == '"e"'


def test_sections_take_their_clients_settings_unless_they_set_their_own():
    cache, limiter = ConditionalCache(), RateLimiter(requests=1)
    own = RateLimiter(requests=5)

    class Api(Client):
        conditional_cache = cache
        rate_limiter = limiter

        class a(Section):
            pass

        class b(Section):
            rate_limiter = own

        class c(Section):
            conditional_cache = None

    api = Api()
    assert api.a._request_config().rate_limiter is limiter
    assert api.a._request_config().conditional_cache is cache
    assert api.b._request_config().rate_limiter is own
    assert api.c._request_config().conditional_cache is None


@pytest.mark.parametrize("setting", ["rate_limiter", "conditional_cache", "telemetry"])
def test_subclasses_inherit_the_settings(setting):
    value = {"rate_limiter": RateLimiter(requests=1), "conditional_cache": ConditionalCache()}.get(
        setting
    )
    if value is None:
        pytest.importorskip("opentelemetry")
        from apiroute.telemetry import OpenTelemetry

        value = OpenTelemetry()
    Base = type("Base", (Client,), {setting: value})
    Sub = type("Sub", (Base,), {})
    assert getattr(Sub._config, setting) is value
