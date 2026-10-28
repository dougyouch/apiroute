import json

from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from tests.codegen.conftest import FIXTURES


def read(spec="shop.yaml"):
    return OpenApiReader(str(FIXTURES / spec), "ShopApi").read()


def test_base_url_with_server_variables_and_groups_by_first_tag():
    definition = read()
    assert definition.base_url == "https://eu.shop.test/v1"
    assert [g.name for g in definition.groups] == ["pets", "store"]
    assert [o.name for o in definition.root.operations] == ["get_status"]
    assert definition.groups[0].description == "Pets for sale."


def test_operation_names_paths_and_parameters():
    pets = read().groups[0]
    names = [o.name for o in pets.operations]
    assert names == [
        "list_pets",
        "create_pet",
        "get_pet",
        "delete_pet",
        "get_photo",
        "upload_photo",
    ]
    get_pet = pets.operations[2]
    assert get_pet.path == "/pets/{pet_id}"  # pet-id renamed, tag prefix stripped from the id
    list_pets = pets.operations[0]
    assert [(p.name, p.location, p.required) for p in list_pets.parameters] == [
        ("limit", "query", False),
        ("status", "query", True),
        ("x_request_id", "header", False),
    ]


def test_bodies_and_responses():
    definition = read()
    pets, store = definition.groups
    create, delete, photo, upload = (pets.operations[i] for i in (1, 3, 4, 5))
    assert create.body.type.expr == "NewPet" and create.body.required
    assert create.response.expr == "Pet"
    assert delete.deprecated and delete.response is None and delete.response_plain == "None"
    assert photo.returns == "bytes"
    assert upload.body.body_format == "multipart"
    order, receipt = store.operations
    assert order.body.body_format == "form"
    assert order.response.expr == "Order"  # from common.yaml
    assert receipt.name == "list" and receipt.returns == "text"


def test_models_merge_all_of_and_keep_wire_names():
    models = read().models
    pet = {f.name: f for f in models["Pet"].fields}
    assert set(pet) == {"name", "tags", "status", "id", "created_at", "owner", "from_", "kind"}
    assert pet["created_at"].alias == "createdAt" and pet["created_at"].type.expr == "str | None"
    assert pet["from_"].alias == "from"
    assert pet["kind"].type.expr == "Dog | Cat"
    assert pet["id"].required and pet["name"].required and not pet["owner"].required
    assert models["PetStatus"].alias_of.expr == "Literal['available', 'sold']"


def test_auth_schemes():
    auth = read().auth
    assert [(a.attribute, a.location, a.wire_name, a.style) for a in auth] == [
        ("token", "header", "Authorization", "bearer"),
        ("api_key", "header", "X-Api-Key", "plain"),
        ("partner", "query", "partner_key", "plain"),
    ]


def test_swagger2():
    definition = read("swagger2.json")
    assert definition.base_url == "https://old.test/api"
    get_user, update_user, upload = definition.root.operations
    assert get_user.response.expr == "User"
    assert update_user.body.type.expr == "User"
    assert upload.body.body_format == "multipart"
    assert definition.auth[0].style == "basic"


def test_content_type_accept_and_authorization_parameters_are_skipped(tmp_path):
    spec = (
        (FIXTURES / "shop.yaml")
        .read_text()
        .replace(
            "        - {name: X-Request-Id, in: header, schema: {type: string}}",
            "        - {name: X-Request-Id, in: header, schema: {type: string}}\n"
            "        - {name: Content-Type, in: header, required: true, schema: {type: string}}\n"
            "        - {name: authorization, in: header, required: true, schema: {type: string}}",
        )
    )
    (tmp_path / "shop.yaml").write_text(spec)
    (tmp_path / "common.yaml").write_text((FIXTURES / "common.yaml").read_text())
    definition = OpenApiReader(str(tmp_path / "shop.yaml"), "ShopApi").read()
    list_pets = definition.groups[0].operations[0]
    assert [p.wire_name for p in list_pets.parameters] == ["limit", "status", "X-Request-Id"]


def test_a_body_that_can_hold_nothing_is_no_body(tmp_path):
    form = "application/x-www-form-urlencoded"
    empty = {"type": "object", "properties": {}, "additionalProperties": False}
    open_object = {"type": "object"}
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Forms", "version": "1"},
        "paths": {
            "/v1/customers": {
                # Stripe's reads: an empty form schema that allows no properties
                "get": _form_operation("GetCustomers", form, empty),
                "post": _form_operation("PostCustomers", form, open_object),
            },
        },
    }
    path = tmp_path / "forms.json"
    path.write_text(json.dumps(spec))
    get, post = OpenApiReader(str(path), "FormsApi").read().root.operations
    assert get.body is None
    assert post.body is not None and post.body.body_format == "form"


def _form_operation(operation_id, media, schema):
    return {
        "operationId": operation_id,
        "requestBody": {"content": {media: {"schema": schema}}},
        "responses": {"200": {"description": "ok"}},
    }


def test_parameter_styles_are_kept(tmp_path):
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "Styles", "version": "1"},
        "paths": {
            "/v1/customers": {
                "get": {
                    "operationId": "GetCustomers",
                    "parameters": [
                        {"name": "created", "in": "query", "style": "deepObject", "schema": {}},
                        {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                    ],
                    "responses": {"200": {"description": "ok"}},
                }
            }
        },
    }
    path = tmp_path / "styles.json"
    path.write_text(json.dumps(spec))
    (operation,) = OpenApiReader(str(path), "StylesApi").read().root.operations
    assert [(p.name, p.style) for p in operation.parameters] == [
        ("created", "deepObject"),
        ("limit", ""),
    ]
