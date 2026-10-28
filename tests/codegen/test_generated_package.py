import importlib
import inspect
import sys

import httpx
import pytest

from apiroute import AsyncHttpxClientTransport, HttpxClientTransport
from tests.conftest import needs_pydantic


def pet_json(**overrides):
    return {"id": 1, "name": "Rex", "createdAt": None, **overrides}


@pytest.fixture
def shop(generate):
    return generate("shop.yaml")


@pytest.fixture
def api(shop, recorder):
    mock = httpx.MockTransport(recorder)
    return shop.ShopApi(
        token="t0k",
        api_key="k3y",
        partner="p",
        transport=HttpxClientTransport(httpx.Client(transport=mock)),
        async_transport=AsyncHttpxClientTransport(httpx.AsyncClient(transport=mock)),
    )


def loaded(shop, suffix):
    return f"{shop.__name__}.{suffix}" in sys.modules


def module(shop, suffix):
    return importlib.import_module(f"{shop.__name__}.{suffix}")


def test_only_the_root_is_imported_until_used(shop, api, recorder):
    api.get_status()
    assert not loaded(shop, "pets.client")
    assert not loaded(shop, "models.client")


def test_dict_routes_send_auth_and_return_dicts(api, recorder, shop):
    recorder.respond(httpx.Response(200, json=[pet_json()]))
    pets = api.pets.list_pets(status="sold", limit=2, x_request_id="r1")
    request = recorder.last
    assert pets == [pet_json()]
    assert str(request.url).startswith("https://eu.shop.test/v1/pets?")
    assert dict(request.url.params) == {"partner_key": "p", "limit": "2", "status": "sold"}
    assert request.headers["Authorization"] == "Bearer t0k"
    assert request.headers["X-Api-Key"] == "k3y"
    assert request.headers["X-Request-Id"] == "r1"
    assert loaded(shop, "pets.client") and not loaded(shop, "pets.models.client")


def test_dict_signatures(api):
    signature = str(inspect.signature(api.pets.list_pets))
    assert signature.startswith("(*, status: Annotated[Literal['available', 'sold'], Query(")


def test_form_multipart_bytes_and_text(api, recorder):
    recorder.respond(
        httpx.Response(200, json={"id": 9}),
        httpx.Response(204),
        httpx.Response(200, content=b"\xff\xd8jpeg"),
        httpx.Response(200, text="receipt"),
    )
    assert api.store.place_order(body={"pet_id": 1}) == {"id": 9}
    assert recorder.last.headers["Content-Type"] == "application/x-www-form-urlencoded"
    api.pets.upload_photo(7, body={"file": ("a.jpg", b"x"), "caption": "hi"})
    assert recorder.last.headers["Content-Type"].startswith("multipart/form-data")
    assert api.pets.get_photo(7) == b"\xff\xd8jpeg"
    assert api.store.list("o1") == "receipt"


@needs_pydantic
def test_typed_calls_take_and_return_models(shop, api, recorder):
    recorder.respond(
        httpx.Response(201, json=pet_json(id=5, owner={"name": "Ann"}, kind={"barks": True}))
    )
    models = module(shop, "pets.models.models")
    pet = api.pets.models.create_pet(body=models.NewPet(name="Rex", status="available"))
    assert recorder.last_json() == {"name": "Rex", "status": "available"}
    assert isinstance(pet, models.Pet) and pet.id == 5 and pet.owner.name == "Ann"
    assert type(pet.kind).__name__ == "Dog"


@needs_pydantic
def test_a_typed_call_imports_only_the_models_it_returns(shop, api, recorder):
    recorder.respond(httpx.Response(200, json={"id": 3, "status": "placed"}))
    order = api.store.models.place_order(body={"pet_id": 1})
    assert order.status == "placed"
    assert loaded(shop, "store.models.schemas.order")
    assert not loaded(shop, "pets.models.schemas.owner")


@needs_pydantic
def test_typed_lists_and_wire_names(api, recorder):
    recorder.respond(httpx.Response(200, json=[pet_json(createdAt="2026-01-01", **{"from": "x"})]))
    (pet,) = api.pets.models.list_pets(status="sold")
    assert pet.created_at == "2026-01-01" and pet.from_ == "x"


@needs_pydantic
@pytest.mark.anyio
async def test_typed_and_dict_calls_through_aio(api, recorder):
    recorder.respond(httpx.Response(200, json=pet_json()), httpx.Response(200, json=pet_json()))
    assert (await api.pets.models.aio.get_pet(1)).name == "Rex"
    assert (await api.aio.pets.get_pet(1)) == pet_json()


@needs_pydantic
def test_models_index_is_lazy_but_complete(shop):
    index = module(shop, "pets.models.models")
    assert "Pet" in dir(index) and "Pet" in index.__all__
    assert not loaded(shop, "pets.models.schemas.owner")
    assert index.Pet.__name__ == "Pet"
    assert loaded(shop, "pets.models.schemas.owner")  # Pet and Owner share a module


def test_dict_only_generation_has_no_models(generate):
    package = generate("shop.yaml", models=False)
    assert not hasattr(package.ShopApi, "models")


def test_lazy_attributes_are_annotated_for_type_checkers_only(shop):
    source = inspect.getsource(sys.modules[f"{shop.__name__}.client"])
    # after the header, which wraps onto two lines when apiroute's version is long (a dev build)
    assert '# mypy: disable-error-code="empty-body"' in source.splitlines()[1:3]
    assert "if TYPE_CHECKING:\n    from .models.client import ShopApiModels\n" in source
    assert '    pets: PetsSection = lazy(".pets.client", "PetsSection")' in source
    assert '    models: ShopApiModels = lazy(".models.client", "ShopApiModels")' in source
    assert f"{shop.__name__}.pets.client" not in sys.modules  # still loaded on first use


def test_every_route_body_ends_with_an_ellipsis(shop):
    import ast

    # pyright accepts a docstring followed by ..., not a docstring alone
    source = inspect.getsource(module(shop, "pets.client"))
    routes = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.FunctionDef) and node.decorator_list
    ]
    assert routes
    for node in routes:
        last = node.body[-1]
        assert isinstance(last, ast.Expr) and last.value.value is Ellipsis, node.name


@needs_pydantic
def test_typed_uploads_keep_their_files(shop, api, recorder):
    recorder.respond(httpx.Response(204), httpx.Response(204))
    api.pets.models.upload_photo(7, body={"file": ("a.jpg", b"\xff\xd8", "image/jpeg")})
    part = recorder.last.content
    assert b'name="file"; filename="a.jpg"' in part and b"Content-Type: image/jpeg" in part
    assert b"\xff\xd8" in part
    models = module(shop, "pets.models.models")
    request = models.PetsUploadPhotoRequest(file=("b.jpg", b"\xff\xd9"), caption="hi")
    api.pets.models.upload_photo(8, body=request)
    assert b'filename="b.jpg"' in recorder.last.content and b"\xff\xd9" in recorder.last.content
    assert b'name="caption"' in recorder.last.content
