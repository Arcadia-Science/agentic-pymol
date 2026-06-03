## Development environment

```bash
uv sync --group dev
uv run pre-commit install
```

## Key commands

```bash
make test         # pytest
make typecheck    # pyright
make lint         # ruff check + ruff format --check
make format       # ruff format + ruff check --fix
make pre-commit   # run all hooks against all files
```
