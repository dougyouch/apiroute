# AGENT.md

Guidance for AI coding agents (and people) working in this repository.

## What this repository is

`apiroute` is a Python library for building API clients declaratively: one `@route` per endpoint (and `graphql_route` per GraphQL operation), safe defaults, httpx underneath. It also ships a code generator (`apiroute generate openapi|wsdl|graphql`) that turns OpenAPI/Swagger specs, WSDLs, and GraphQL schemas with hand-written operations into clients. It's released to PyPI as `apiroute`. See `README.md` for the user-facing documentation.

## Layout

| Path | What it is |
| --- | --- |
| `src/apiroute/` | The runtime library: `Client`, `Section`, `@route`, retries, request building, response conversion |
| `src/apiroute/graphql/` | `graphql_route` for hand-written GraphQL operations: document reading, variable binding, `GraphQLBody`, `GraphQLDecoder`, `GraphQLError` |
| `src/apiroute/testing/` | Test helpers for code using apiroute clients: `MockTransport`, `mock_transport()`, `block_network()`, and the pytest plugin registered in `pyproject.toml` |
| `src/apiroute/codegen/` | The generator behind the `apiroute` CLI (`cli.py`), with `openapi/`, `wsdl/` and `graphql/` front ends (readers that build an `ApiDefinition`) and the emitters that write client code |
| `tests/` | One test module per runtime class; `tests/codegen/`, `tests/graphql/`, `tests/soap/`, `tests/testing/` and `tests/transports/` cover the generator, GraphQL, SOAP, the test helpers and transports |
| `.github/workflows/` | `ci.yml` (pull requests, and before each release) and `release.yml` (every push to main: tag, PyPI, GitHub release) |
| `scripts/next_release.py` | Works out each release's version and notes from the commits since the last tag |
| `.agent/skills/apiroute-client.md` | Skill for creating and maintaining repositories of generated clients for any API |

## Rules

- **Follow the existing style:** one class per file, small methods, and names that match the surrounding modules. Ruff enforces `E`, `F`, `I`, `B` and `UP` at line length 100.
- **Support Python 3.10 and newer.** Don't use syntax or stdlib features from later versions.
- **Keep optional dependencies optional.** The runtime depends only on `httpx`. pydantic, defusedxml (SOAP), graphql-core (GraphQL syntax checks) and pyyaml (codegen) sit behind the `pydantic`, `soap`, `graphql` and `codegen` extras, so import them lazily.
- **Generated output is a public interface.** Downstream repositories regenerate their clients with each apiroute release, so a change to the emitters changes their code. Cover it in `tests/codegen/`.
- **Every merge to main is a release.** There's no release PR; `release.yml` tests, tags and publishes each push to main. Merge only what's ready to ship.
- **Use conventional commits.** The version comes from the commits since the last tag:
  - `feat!:` (or a `BREAKING CHANGE:` footer) is a major release
  - `feat:` is a minor release
  - anything else (`fix:`, `docs:`, `chore:` ...) is a patch
- **The version lives in the git tag**, not `pyproject.toml` (hatch-vcs). Never tag by hand; the release workflow does.
- **Before committing:** `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`.

## Common tasks

- **Run the tests:** `uv sync`, then `uv run pytest`.
- **Try the generator:** `uv run apiroute generate openapi <spec-url-or-file> -o <scratch-dir> --models`.
- **Fix a generator bug found in a client repository:** reproduce it with a small spec in `tests/codegen/`, fix the emitter, and release; the client repository's Build workflow picks it up.
- **Release:** merge to main. `release.yml` runs CI, tags `vX.Y.Z`, publishes to PyPI (trusted publishing, the `pypi` environment) and creates the GitHub release with notes from the commits. A failed release can be rerun: every step skips what's already done.

## Skill

`.agent/skills/apiroute-client.md` describes how to create, set up and maintain a client repository for any API with OpenAPI/Swagger specs or WSDLs, using this generator. Read it before creating or restructuring one.
