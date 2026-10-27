from apiroute import Client, Section
from apiroute.transports.one_shot_transport import OneShotTransport
from apiroute.transports.transport_registry import TransportRegistry


class FakeTransport:
    def __init__(self):
        self.closed = False

    def send(self, spec):
        raise NotImplementedError

    def close(self):
        self.closed = True


class Api(Client):
    pass


class ChildApi(Api):
    pass


def test_default_is_one_shot_and_reused():
    registry = TransportRegistry()
    assert isinstance(registry.for_class(Api), OneShotTransport)
    assert registry.for_class(Api) is registry.for_class(ChildApi)


def test_class_registration_applies_to_subclasses_and_beats_the_default():
    registry = TransportRegistry()
    default, api = FakeTransport(), FakeTransport()
    registry.use(default)
    registry.use(api, Api)
    assert registry.for_class(ChildApi) is api
    assert registry.for_class(Section) is default


def test_registered_lists_each_transport_once_and_reset_forgets_them():
    registry = TransportRegistry()
    default, api = FakeTransport(), FakeTransport()
    registry.use(default)
    registry.use(api, Api)
    registry.use(api, ChildApi)
    assert registry.registered() == [api, default]
    registry.reset()
    assert isinstance(registry.for_class(Api), OneShotTransport)


def test_restore_puts_back_a_snapshot():
    registry = TransportRegistry()
    first, second = FakeTransport(), FakeTransport()
    registry.use(first)
    registry.use(first, Api)
    saved = registry.snapshot()
    registry.reset()
    registry.use(second, ChildApi)
    registry.restore(saved)
    assert registry.for_class(ChildApi) is first
    assert registry.snapshot() == saved
