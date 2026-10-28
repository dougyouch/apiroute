from apiroute.codegen.api_definition import ApiDefinition, Group, Model, ModelField
from apiroute.codegen.nullable_fields import NullableFields
from apiroute.codegen.type_ref import TypeRef


def test_every_field_accepts_none_and_stays_required():
    label = Model(
        "Label",
        fields=[
            ModelField("name", None, TypeRef("str"), required=True),
            ModelField("description", None, TypeRef("str"), required=True),
            ModelField("color", None, TypeRef("str | None"), required=False),
        ],
    )
    labels = Model("Labels", alias_of=TypeRef.model("Label"))
    definition = ApiDefinition(
        client_name="Api",
        base_url="https://api.test",
        title="",
        description="",
        source="spec.yaml",
        root=Group("", "Api"),
        models={"Label": label, "Labels": labels},
    )
    NullableFields().apply(definition)
    assert [(f.type.expr, f.required) for f in label.fields] == [
        ("str | None", True),
        ("str | None", True),
        ("str | None", False),
    ]
    assert labels.alias_of.expr == "Label"
