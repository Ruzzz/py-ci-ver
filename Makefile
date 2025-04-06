ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))
export PYTHONPATH=$(ROOT_DIR)
export UV_NO_SYNC=1

-include pre.mk

# DEV

lock:
	uv lock -U

sync:
	uv sync --locked

deps:: lock sync

isort:
	ruff check --select I --fix

fmt:: isort
	ruff format

devver:
	ci-ver up ci_ver/__init__.py

check:
	ci-ver check ci_ver/__init__.py && \
	uv lock --check && \
	ruff format --check && \
	ruff check && \
	mypy ci_ver

fix:
	ruff check --fix --show-fixes

test:
	pytest --cov=ci_ver -v tests

# BUILD

build:
	uv build
.PHONY: build

upload:
	uv publish

clean:
	rm -rf dist/

-include post.mk
