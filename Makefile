MODULE_NAME="macpmd"

# Default target: print usage message
.PHONY: help
help:
	@echo "Usage:"
	@echo "  make build        - Build project and documentation"
	@echo "  make docs         - Build HTML documentation"
	@echo "  make clean        - Clean built package and documentation"
	@echo "  make check        - Format check and lint source"
	@echo "  make format       - Format source using Ruff"
	@echo "  make black        - Format source using Black (for long strings)"
	@echo "  make lint         - Lint source using pyright"
	@echo "  make dev          - Just create dev (.venv) setup"
	@echo "  make publish      - Publish output/ to PyPI and docs"

# Version string from git tags (falls back to commit hash if no tags)
VERSION_STR=$(shell git describe --tags --always 2>/dev/null | sed 's/-/.post.dev/' | sed 's/-g/-/')

# Generate _version.py with the current version
.PHONY: version
version:
	@echo '__version__ = "$(VERSION_STR)"' > macpmd/_version.py

# Build the project
.PHONY: build
build: check-dependencies format-check lint version docs
	rm -rf output/
	uv build --out-dir output
	rm -f output/*.tar.gz
	cd html && uv run python -m zipfile -c ../output/macpmd-$(VERSION_STR)-docs.zip .

# Publish (requires output/ from make build)
.PHONY: publish
publish: check-dependencies
	uv run wj-publish output/

# Generate CLI help files for documentation
.PHONY: docs-help
docs-help: check-dependencies version
	@mkdir -p docs/mkdocs/_include
	COLUMNS=80 uv run macpmd --help > docs/mkdocs/_include/help_main.txt
	COLUMNS=80 uv run macpmd add --help > docs/mkdocs/_include/help_add.txt
	COLUMNS=80 uv run macpmd start --help > docs/mkdocs/_include/help_start.txt
	COLUMNS=80 uv run macpmd stop --help > docs/mkdocs/_include/help_stop.txt
	COLUMNS=80 uv run macpmd restart --help > docs/mkdocs/_include/help_restart.txt
	COLUMNS=80 uv run macpmd delete --help > docs/mkdocs/_include/help_delete.txt
	COLUMNS=80 uv run macpmd list --help > docs/mkdocs/_include/help_list.txt
	COLUMNS=80 uv run macpmd logs --help > docs/mkdocs/_include/help_logs.txt

# Build the documentation
.PHONY: docs
docs: docs-help
	rm -rf html/
	VERSION=$(VERSION_STR) uv run wj-mkdocs -f docs/mkdocs.yml -d docs/mkdocs -o html/
	cp docs/docinfo.* html/
	rm -rf docs/mkdocs/_include html/_include

# Clean build artefacts
.PHONY: clean
clean: check-dependencies
	rm -rf html/ output/
	uv clean

# Check the format of code
.PHONY: check
check: format-check lint

# Check the format of code
.PHONY: format-check
format-check: check-dependencies
	uv run ruff format --check .
	uv run ruff check .

# Fix format of the code
.PHONY: format
format: check-dependencies
	uv run ruff format .
	uv run ruff check . --fix

# Fix format of the code
.PHONY: black
black: check-dependencies
	uv run black --preview --enable-unstable-feature string_processing .
	uv run ruff format .
	uv run ruff check . --fix

# Lint the code
.PHONY: lint
lint: check-dependencies
	uv run pyright

# Just create dev (.venv) setup
.PHONY: dev
dev: check-dependencies

# Check if uv is installed, install it if not
.PHONY: check-dependencies
check-dependencies: version
	uv --version 2>/dev/null && true || pip3 install uv
	uv sync
