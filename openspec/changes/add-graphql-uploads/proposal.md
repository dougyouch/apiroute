## Why

GraphQL has no file type, and a JSON body can't carry binary data, so APIs that accept files over GraphQL use the [GraphQL multipart request spec](https://github.com/jaydenseric/graphql-multipart-request-spec). The operation goes as a `multipart/form-data` request with an `operations` field (the usual JSON, with each file's position set to `null`), a `map` field (which part fills which variable path), and one part per file. GraphQL Yoga supports it natively, and Apollo Server (through `graphql-upload`), Hasura, Strawberry, Graphene, gqlgen and others implement it. apiroute can't send these today: a file in a variable fails JSON encoding. It's the last item on the GraphQL list (runtime, schema validation, codegen, pagination, persisted queries, uploads).

## What Changes

- **New `apiroute.graphql.Upload(source, filename=None, content_type=None)`.** `source` is `bytes`, a file path, or a binary file object. The filename defaults to the path's or file's name, and the content type is guessed from the filename (else `application/octet-stream`).
- **Uploads are detected per call.** When any variable value, at any depth in dicts and lists, is an `Upload` or an open binary file, `GraphQLBody` sends the multipart request instead of JSON:
  - `operations` holds the operation with those values set to `null`;
  - `map` gives each file part's variable paths (`{"0": ["variables.file"], "1": ["variables.files.1"]}`);
  - then one part per file.

  Calls without files are byte-for-byte unchanged. No route option is needed.
- **Composes:** persisted queries put their `extensions` in `operations`; `paginate=` and `.aio` work as usual.
- **Retries:** files are read once, when the body is built, so a retry resends the same bytes.
- **Codegen:** an `Upload` scalar is `Any` (unchanged), so generated methods accept `Upload` objects and files in those variables, typed and dict alike. The README shows how.

Not in scope: streaming large files without reading them into memory, the spec's batched operations, Apollo Server's CSRF header (which a client sets through `headers`, as documented), and Shopify-style staged uploads (an ordinary mutation followed by a plain HTTP upload).

## Capabilities

### New Capabilities
- `graphql-uploads`: sending files in GraphQL variables using the multipart request spec.

### Modified Capabilities
<!-- None: requests without files are unchanged. -->

## Impact

- **New:** `apiroute/graphql/upload.py` (`Upload`) and `apiroute/graphql/graphql_uploads.py` (finding files in variables and building the map).
- **Changed:** `GraphQLBody` (the multipart path, through the existing `MultipartEncoder`); `apiroute.graphql` exports `Upload`.
- **No new dependencies.** Release: `feat:` (minor).
