from dataclasses import replace

from apiroute.codegen.api_definition import ApiDefinition, Group, Operation

SUFFIX = "_all"


class AllPagesMethods:
    """Adds a <name>_all method after each operation that pages (all_pages set): the same
    route and parameters, iterating every page's items. Run after --operation-names, so the
    method is named after the operation's final name."""

    def apply(self, definition: ApiDefinition) -> None:
        problems = []
        for group in [definition.root, *definition.groups]:
            problems += self._expand(group)
        if problems:
            raise ValueError("paginated methods: " + "; ".join(problems))

    def _expand(self, group: Group) -> list[str]:
        names = {operation.name: operation for operation in group.operations}
        problems = []
        expanded = []
        for operation in group.operations:
            expanded.append(operation)
            if operation.all_pages is None:
                continue
            paged = _all_pages(operation)
            if paged.name in names:
                where = f"{group.name}.{paged.name}" if group.name else paged.name
                problems.append(
                    f"{where}: {operation.operation_id}'s paginated method clashes with "
                    f"{names[paged.name].operation_id}"
                )
            expanded.append(paged)
        group.operations = expanded
        return problems


def _all_pages(operation: Operation) -> Operation:
    pagination = operation.all_pages
    return replace(
        operation,
        name=f"{operation.name}{SUFFIX}",
        response=pagination.item,
        response_plain=f"Iterator[{pagination.item_plain}]",
        all_pages=None,
        paginate=pagination,
    )
