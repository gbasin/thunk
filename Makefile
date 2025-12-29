.PHONY: lint format typecheck test build

UV ?= uv

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff format .

typecheck:
	$(UV) run pyright src/thunk tests

test:
	$(UV) run pytest

build:
	$(UV) build
