"""Hand-built Page objects for strategy tests."""

import httpx

from apiroute.pagination import Page


def page(data, url="https://api.test/items", headers=None, items=None, request=None, index=0):
    response = httpx.Response(200, json=data, headers=headers, request=httpx.Request("GET", url))
    return Page(data, response, request, index, items if items is not None else [])
