# List recipes
default:
    @just --list

# Sync the dev virtual environment
sync:
    uv sync --extra dev

# Wipe and recreate the venv
reset:
    rm -rf .venv
    uv sync --extra dev

# Run unit tests
test *args:
    uv run pytest tests/ --cov {{ args }}

# Run integration tests (Playwright)
test-playwright *args:
    uv run playwright install --with-deps chromium
    uv run pytest tests/ --playwright -m needs_playwright {{ args }}

# Type check
typecheck:
    uv run mypy trame_pyvista

# Lint + format (pre-commit hooks)
lint:
    uvx pre-commit run --all-files

# Build wheel + sdist
build:
    uv build

# Run an example by relative path under examples/
example name:
    uv run python examples/{{ name }} --serve --port 0
