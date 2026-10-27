## ADDED Requirements

### Requirement: Files in variables are sent as multipart requests
When any variable value of a `graphql_route` call, at any depth in dicts and lists, is an `apiroute.graphql.Upload` or an open binary file, the request SHALL be `multipart/form-data` following the GraphQL multipart request spec, with these fields in order:
- `operations`: the usual JSON payload, with each file's position set to `null`;
- `map`: a JSON object from part names (`"0"`, `"1"`, ...) to lists of variable paths;
- one file part per distinct upload.

Calls without uploads SHALL send exactly the JSON body they send today.

#### Scenario: One file
- **WHEN** `client.upload(file=Upload(b"hello", filename="a.txt"))` is called on `mutation Upload($file: Upload!) { ... }`
- **THEN** the request is multipart, `operations` has `"variables": {"file": null}`, `map` is `{"0": ["variables.file"]}`, and part `0` is `a.txt` with content `hello` and type `text/plain`

#### Scenario: Files in a list and in an input object
- **WHEN** variables are `{"files": [Upload(b"a"), Upload(b"b")], "input": {"avatar": Upload(b"c")}}`
- **THEN** `map` is `{"0": ["variables.files.0"], "1": ["variables.files.1"], "2": ["variables.input.avatar"]}`, and the file positions in `operations` are `null`

#### Scenario: The same file twice
- **WHEN** one `Upload` object is the value of two variables
- **THEN** it's sent as one part, whose map entry lists both paths

#### Scenario: No files
- **WHEN** a route is called without any upload in its variables
- **THEN** the request body and content type are the same JSON as before this change

### Requirement: Upload values
`Upload(source, filename=None, content_type=None)` SHALL accept `bytes`, a file path (`str` or `os.PathLike`), or a binary file object. The filename SHALL default to the path's or file object's base name, else `"upload"`. The content type SHALL default to the type guessed from the filename, else `application/octet-stream`. A path SHALL be read when the request body is built.

#### Scenario: From a path
- **WHEN** `Upload("/tmp/report.pdf")` is sent
- **THEN** the part's filename is `report.pdf`, its type is `application/pdf`, and its content is the file's bytes

#### Scenario: A bare open file
- **WHEN** a variable's value is `open("photo.png", "rb")`
- **THEN** it's sent as a file part named `photo.png` with type `image/png`

### Requirement: Uploads compose with other features
A multipart request SHALL be built once per call and resent unchanged on retries. With `persisted=True`, `operations` SHALL carry the persisted-query `extensions` (and no `query` in hash-only requests). `.aio` calls SHALL send the same request.

#### Scenario: Retry
- **WHEN** a call with an upload fails with a retryable error and is retried
- **THEN** both attempts send the same body, including the file's bytes

#### Scenario: Persisted upload
- **WHEN** a `persisted=True` route is called with an upload and the server misses the hash
- **THEN** both requests are multipart, the first `operations` without `query` and the second with it, and both have the same file part
