## 1. Runtime

- [x] 1.1 `Upload` (bytes, path or file object; filename and content-type defaults) exported from `apiroute.graphql`
- [x] 1.2 `GraphQLUploads.extract`: walk dicts and lists, replace uploads with `None`, record paths, and share parts for one object used twice
- [x] 1.3 `GraphQLBody`: multipart when uploads are present (`operations`, `map`, parts, through `MultipartEncoder`); JSON unchanged otherwise
- [x] 1.5 `TypedClient._plain`: keep `Upload` values and open files (wrapped) in request models, converting the rest as JSON mode does
- [x] 1.4 Tests: `Upload` defaults; extraction; body shapes (one file, nested, a shared file, no files unchanged); through a client with `MockTransport` (sync, `.aio`, retry, persisted miss)

## 2. Docs and checks

- [x] 2.1 README: uploads in the GraphQL section (including Apollo's CSRF header) and in "GraphQL clients" (passing `Upload` to generated methods)
- [x] 2.2 Ruff, the full suite, the lowest-dependencies run, and a live check against GraphQL Yoga run locally: one file, several files in a list, a file in an input object, a persisted upload, and a generated client
