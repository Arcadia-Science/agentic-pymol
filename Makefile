.PHONY: lint
lint:
	uv run ruff check --exit-zero .
	uv run ruff format --check .

.PHONY: format
format:
	uv run ruff format .
	uv run ruff check --fix .

.PHONY: typecheck
typecheck:
	uv run pyright

.PHONY: pre-commit
pre-commit:
	uv run pre-commit run --all-files

.PHONY: test
test:
	uv run pytest -v tests/

.PHONY: clean
clean:
	rm -rf dist .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} +
