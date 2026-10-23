import asyncio

import pytest

from apiroute.transports import async_pooled_transport
from apiroute.transports.async_pooled_transport import AsyncPooledTransport
from tests.transports.conftest import spec


@pytest.mark.anyio
async def test_shares_one_client_within_a_loop(mock, created_async_clients):
    transport = AsyncPooledTransport(transport=mock)
    await asyncio.gather(transport.send(spec()), transport.send(spec()))
    assert len(created_async_clients) == 1


def test_each_event_loop_gets_its_own_client(mock, created_async_clients):
    transport = AsyncPooledTransport(transport=mock)
    asyncio.run(transport.send(spec()))
    asyncio.run(transport.send(spec()))
    assert len(created_async_clients) == 2


@pytest.mark.anyio
async def test_opens_a_new_client_after_a_fork(mock, created_async_clients, monkeypatch):
    transport = AsyncPooledTransport(transport=mock)
    await transport.send(spec())
    monkeypatch.setattr(async_pooled_transport.os, "getpid", lambda: -1)
    await transport.send(spec())
    assert len(created_async_clients) == 2


@pytest.mark.anyio
async def test_aclose_closes_the_loops_client(mock, created_async_clients):
    transport = AsyncPooledTransport(transport=mock)
    await transport.send(spec())
    await transport.aclose()
    assert created_async_clients[0].is_closed
    await transport.send(spec())
    assert len(created_async_clients) == 2
