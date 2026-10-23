# AGENT.md

Guidance for AI coding agents (and people) working in this repository.

## What this repository is

`apiroute` is a Python library for building API clients declaratively: one `@route` per endpoint, safe defaults, httpx underneath. It also ships a code generator (`apiroute generate openapi|wsdl`) that turns OpenAPI/Swagger specs and WSDLs into clients. It's released to PyPI as `apiroute`. See `README.md` for the user-facing documentation.

## Layout

| Path | What it is |
| --- | --- |
| `src/apiroute/` | The runtime library: `Client`, `Section`, `@route`, retries, request building, response conversion |
| `src/apiroute/codegen/` | The generator behind the `apiroute` CLI (`cli.py`), with `openapi/` and `wsdl/` front ends and the emitters that write client code |
| `tests/` | One test module per runtime class; `tests/codegen/`, `tests/soap/` and `tests/transports/` cover the generator, SOAP and transports |
| `.github/workflows/` | `ci.yml` and `release.yml` (release-please and PyPI) |
| `.agent/skills/apiroute-client.md` | Skill for creating and maintaining repositories of generated clients (e.g. `ebay-apiroute`) |

## Rules

- **Follow the existing style:** one class per file, small methods, and names that match the surrounding modules. Ruff enforces `E`, `F`, `I`, `B` and `UP` at line length 100.
- **Support Python 3.10 and newer.** Don't use syntax or stdlib features from later versions.
- **Keep optional dependencies optional.** The runtime depends only on `httpx`. pydantic, defusedxml (SOAP) and pyyaml (codegen) sit behind the `pydantic`, `soap` and `codegen` extras, so import them lazily.
- **Generated output is a public interface.** Downstream repositories regenerate their clients with each apiroute release, so a change to the emitters changes their code. Cover it in `tests/codegen/`.
- **Use conventional commits.** release-please derives versions from them:
  - `feat:` is a minor release
  - `fix:` is a patch
  - `chore:`, `docs:`, `test:` and `ci:` produce no release
- **Before committing:** `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`.

## Common tasks

- **Run the tests:** `uv sync`, then `uv run pytest`.
- **Try the generator:** `uv run apiroute generate openapi <spec-url-or-file> -o <scratch-dir> --models`.
- **Fix a generator bug found in a client repository:** reproduce it with a small spec in `tests/codegen/`, fix the emitter, and release; the client repository's Build workflow picks it up.
- **Release:** merge the release PR that release-please keeps open. Publishing uses PyPI trusted publishing (`release.yml`).

## Skill

`.agent/skills/apiroute-client.md` describes how to create, set up and maintain a client repository for any API with OpenAPI/Swagger specs or WSDLs, using this generator. Read it before creating or restructuring one.
