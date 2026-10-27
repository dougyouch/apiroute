## Context

`GraphQLBody` is a route's `body_format`. It receives the rendered variables (a dict) and returns `(content, content_type)`. `BodyEncoder` uses that content type, and `RequestBuilder` builds the body once, before the retry loop. `MultipartEncoder` turns a dict into `multipart/form-data` with httpx: values that are bytes, open files or `(filename, content, type)` tuples become file parts, and other values become fields. httpx writes fields before files.

The multipart request spec, for a single operation:
```
operations: {"query": "mutation ($file: Upload!) { upload(file: $file) { id } }", "variables": {"file": null}}
map:        {"0": ["variables.file"]}
0:          <file bytes>
```
Fields must come in this order: `operations`, `map`, then the files.

## Goals / Non-Goals

**Goals:**
- Files go in variables like any other value, and the right request is chosen per call, with no route flag.
- Requests without files are unchanged, byte for byte.
- It works with persisted queries, pagination, async and retries.

**Non-Goals:**
- Streaming uploads; batched operations; adding server-specific CSRF headers automatically.

## Decisions

### 1. An explicit `Upload` value, plus open binary files

`Upload(source, filename=None, content_type=None)`:
- `source` can be:
  - `bytes`;
  - a `str` or `os.PathLike` path, read when the body is built;
  - a binary file object (anything with `read()`).
- `filename` defaults to the path's name or the file object's `name` (its basename), else `"upload"`.
- `content_type` is `mimetypes.guess_type(filename)`, else `application/octet-stream`.

A bare open binary file (`io.IOBase`) in a variable is also an upload, matching what `MultipartEncoder` accepts. Bare `bytes` are not: GraphQL variables have no binary type, so bytes are more likely a mistake than a file, and JSON encoding would fail loudly anyway.

*Alternative:* treat `pathlib.Path` values as uploads. Rejected because it's too implicit, since a path might be meant as a string variable. `Upload(path)` is one word longer and unambiguous.

### 2. Detection and the map: `GraphQLUploads`

`GraphQLUploads.extract(variables)` walks dicts and lists (not other objects) and returns two things:
- a copy of the variables with each upload replaced by `None`;
- the uploads in order, with their paths (`variables.file`, `variables.input.files.0`).

Two variables holding the same `Upload` object share one part: its map entry lists both paths, as the spec allows.

### 3. `GraphQLBody` chooses JSON or multipart per call

`GraphQLBody.__call__` builds the payload as today: `query`, or the persisted extensions; `operationName`; and variables with `None` values left out. Then it extracts uploads. With none, it returns the JSON as before. With some:
- `operations` is the payload JSON, with each upload's position as an explicit `null`. The spec requires the key to be present, so the "leave out `None` variables" rule isn't applied to upload positions.
- `map` is `{"0": ["variables.a"], ...}`.
- The parts are `"0"`, `"1"`, ... as `(filename, bytes, content_type)`.

It returns `MultipartEncoder().encode({"operations": ..., "map": ..., "0": ..., ...})`. Dict order keeps `operations` before `map`, and httpx writes fields before files.

Files are read into bytes at this point. That's why a retry resends identical content: the body is built once per call. It also means a file object is read once per call.

### 4. Persisted queries and pagination

Persisted variants are `GraphQLBody` instances in hash or register mode, so they produce multipart requests with `extensions` inside `operations`, as servers implementing both expect. Pagination's cursor goes into the variables, which stay JSON inside `operations`.

### 5. Codegen

There's no change. An `Upload` (or `File`) scalar is a custom scalar, so it maps to `Any`, and generated methods accept `Upload` objects and files there. `--scalar Upload=apiroute.graphql:Upload` isn't recommended, because pydantic input models would then need arbitrary types allowed. The README documents passing `Upload` to generated methods.

### 6. Typed calls keep files intact

`TypedClient._plain` used to dump request models with pydantic's JSON mode, which can't serialize an `Upload`. And pydantic's Python mode reads an open file in an `Any` field as a list of its lines, which consumes it. So `_plain` now works on a copy of the model with open files wrapped in `Upload`, made with `model_copy(update=...)` so the caller's model is untouched. It dumps that copy in Python mode, then converts the values JSON can't hold (datetimes, enums, UUIDs) with `pydantic_core.to_jsonable_python`, the same conversion JSON mode uses, while leaving files alone. That function exists since pydantic 2.0.

*Found testing a generated client against Yoga:* `AvatarInput(avatar=Upload(...))` failed to serialize until this change.

## Tested against GraphQL Yoga

With GraphQL Yoga 5.7 and its APQ plugin running locally, the server reported each file's name, type, size and SHA-256. All of these arrived byte-exact:
- bytes, a 200 KB binary from a path, and a bare open file;
- a list of three files;
- a file in an input object;
- `.aio`;
- a persisted upload (miss and registration with the file, then hash-only);
- a generated client (dict and typed), including files inside typed input models.

Calls without files stayed JSON.

The persisted case found a separate bug in 1.11.0, fixed in its own commit. Yoga's APQ plugin answers a miss with HTTP 404, which the hash-only request rejected before reading the `PersistedQueryNotFound` body.

## Risks / Trade-offs

- **[Large files are read into memory]** → This is documented. Streaming is a possible later change.
- **[Apollo Server rejects multipart requests without a CSRF header]** (`Apollo-Require-Preflight: true`) → It's documented as a `headers` entry on the client or route. Yoga and others don't need it.
- **[A server without multipart support]** → It answers with an error, which surfaces as `GraphQLError` or `UnexpectedResponse` like any other.

## Open Questions

- Streaming uploads (httpx can stream multipart) would need `BodyEncoder` to accept a stream. Is it worth doing once someone needs large files?
