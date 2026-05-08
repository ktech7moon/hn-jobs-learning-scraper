.PHONY: help install test lint format check clean naive graduated compare

help:
	@echo "Targets:"
	@echo "  install     pip install -e .[dev] (run inside .venv)"
	@echo "  test        pytest"
	@echo "  lint        ruff check ."
	@echo "  format      ruff format ."
	@echo "  check       ruff check . && ruff format --check . && pytest"
	@echo "  clean       remove caches and build artifacts"
	@echo "  naive       hn-scraper naive (Slice 1)"
	@echo "  graduated   hn-scraper graduated (Slice 2)"
	@echo "  compare     hn-scraper compare (Slice 2)"

install:
	pip install -e ".[dev]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

check:
	ruff check .
	ruff format --check .
	pytest

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -prune -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist

naive:
	hn-scraper naive

graduated:
	hn-scraper graduated

compare:
	hn-scraper compare
