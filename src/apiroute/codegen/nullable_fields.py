import dataclasses

from apiroute.codegen.api_definition import ApiDefinition


class NullableFields:
    """Types every model field as accepting None (--nullable-fields), for specs whose schemas
    say a field is never null when the API does return null for it. Required fields stay
    required: they must be present, but may be null. A discriminator stays as it is, since it
    picks the member of a tagged union."""

    def apply(self, definition: ApiDefinition) -> None:
        for model in definition.models.values():
            model.fields = [
                field
                if field.discriminator
                else dataclasses.replace(field, type=field.type.optional())
                for field in model.fields
            ]
