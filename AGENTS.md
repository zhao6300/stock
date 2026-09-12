# Repository Guide

- Keep every phase small and independently testable.
- Run `make test` after behavior changes.
- Do not add dependencies unless required and documented in `requirements.txt`.
- Keep source code in `src/` and tests in `tests/`.
- Use SQLite by default and environment variables for runtime secrets.

