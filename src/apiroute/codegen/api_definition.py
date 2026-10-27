from dataclasses import dataclass, field

from apiroute.codegen.type_ref import TypeRef


@dataclass
class Parameter:
    """A path, query or header parameter of an operation."""

    name: str  # the Python name
    wire_name: str
    location: str  # "path", "query", "header", or "variable" for a GraphQL variable
    type: TypeRef
    required: bool
    description: str = ""


@dataclass
class RequestBody:
    type: TypeRef  # the model type, used by the .models layer
    required: bool
    body_format: str = "json"  # "json", "form" or "multipart"
    plain: str = "Any"  # the dict layer's type: "dict[str, Any]", "list[Any]" or "Any"


@dataclass
class SoapOperation:
    """How a WSDL operation is sent: its input element, envelope version and action."""

    element: str  # the input element's local name
    namespace: str  # its namespace, which body keys default to
    version: str  # "1.1" or "1.2"
    qualified: bool  # the schema's elementFormDefault
    action: str = ""
    response_namespace: str = ""


@dataclass
class GraphQLOperationSpec:
    """How a GraphQL operation is sent: its document (the operation and the fragments it
    uses) to the endpoint path."""

    document: str
    operation_name: str
    operation_type: str  # "query" or "mutation"
    path: str = "/graphql"
    # the response-key path to the connection a paginated method iterates; its Operation's
    # response is then the item type
    paginate: str | None = None


@dataclass
class Operation:
    """One endpoint, as both layers generate it."""

    name: str  # the Python method name, unique within its group
    method: str
    path: str  # with {python_name} placeholders
    summary: str = ""
    parameters: list[Parameter] = field(default_factory=list)
    body: RequestBody | None = None
    response: TypeRef | None = None  # the model type; None when there is no JSON body
    response_plain: str = "Any"  # the dict layer's return type
    returns: str = "json"  # "json", "text" or "bytes"
    headers: dict[str, str] = field(default_factory=dict)  # fixed headers, e.g. SOAPAction
    deprecated: bool = False
    soap: SoapOperation | None = None
    graphql: GraphQLOperationSpec | None = None
    operation_id: str = ""  # the spec's name for it: an operationId or a WSDL operation


@dataclass
class Group:
    """The root client or one section (an OpenAPI tag, a WSDL port)."""

    name: str  # the attribute and folder name; "" for the root
    class_name: str
    description: str = ""
    operations: list[Operation] = field(default_factory=list)


@dataclass
class ModelField:
    name: str
    alias: str | None  # the wire name, when it isn't the Python name
    type: TypeRef
    required: bool
    description: str = ""


@dataclass
class Model:
    """A pydantic model, or a type alias when alias_of is set (enums, arrays, unions)."""

    name: str
    fields: list[ModelField] = field(default_factory=list)
    description: str = ""
    alias_of: TypeRef | None = None
    # names the model's type comes from outside, name -> module: a GraphQL custom scalar
    # mapped with --scalar DateTime=datetime:datetime is the alias DateTime = datetime
    imports: dict[str, str] = field(default_factory=dict)


@dataclass
class AuthScheme:
    """How a credential reaches the request: an attribute on the client sent as a header
    or query parameter."""

    attribute: str  # the client attribute and __init__ argument, e.g. "token"
    location: str  # "header" or "query"
    wire_name: str  # e.g. "Authorization" or "api_key"
    style: str = "plain"  # "plain", "bearer" or "basic" (attribute holds "user:password")
    description: str = ""


@dataclass
class ApiDefinition:
    """What a reader produces and the emitter writes: one generated package."""

    client_name: str
    base_url: str | None
    title: str = ""
    description: str = ""
    source: str = ""
    root: Group = field(default_factory=lambda: Group("", ""))
    groups: list[Group] = field(default_factory=list)
    models: dict[str, Model] = field(default_factory=dict)
    auth: list[AuthScheme] = field(default_factory=list)
    # "package.module:Class", a hand-written Client subclass the root client extends instead
    # of Client; it owns auth, so the spec's security schemes aren't generated
    base_class: str | None = None
    # things the reader noticed that don't stop generation, e.g. a deprecated GraphQL field
    warnings: list[str] = field(default_factory=list)
