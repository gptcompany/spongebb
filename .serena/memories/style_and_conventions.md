# Style and Conventions
- Python project with strict typing: `mypy` strict mode is enabled for first-party code.
- Linting via Ruff with `E,W,F,I,B,C4,UP,ARG,SIM`; line length 100.
- Tests use pytest with markers: `unit`, `integration`, `e2e`, `slow`.
- Async pytest mode is enabled (`asyncio_mode = auto`).
- Test files are organized by domain under `tests/unit`, `tests/integration`, `tests/e2e`, and `tests/visual`.
- Existing codebase favors typed functions/classes, domain-specific modules, and targeted test files mirroring package areas.