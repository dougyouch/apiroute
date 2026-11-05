from apiroute.codegen.api_definition import ApiDefinition


class ModelUsage:
    """Which models a client sends (request bodies, directly or nested) and which it receives
    (responses and webhook payloads): a change breaks callers differently on each side."""

    def __init__(self, definition: ApiDefinition):
        self._definition = definition
        operations = [
            operation
            for group in [definition.root, *definition.groups]
            for operation in group.operations
        ]
        sent = {name for o in operations if o.body for name in o.body.type.models}
        sent |= {name for o in operations for p in o.parameters for name in p.type.models}
        received = {name for o in operations if o.response for name in o.response.models}
        received |= {n for w in definition.webhooks if w.payload for n in w.payload.models}
        self.sent = self._closure(sent)
        self.received = self._closure(received)

    def _closure(self, names: set[str]) -> set[str]:
        models = self._definition.models
        seen: set[str] = set()
        pending = list(names)
        while pending:
            name = pending.pop()
            if name in seen or name not in models:
                continue
            seen.add(name)
            model = models[name]
            if model.alias_of is not None:
                pending.extend(model.alias_of.models)
            pending.extend(m for f in model.fields for m in f.type.models)
        return seen
