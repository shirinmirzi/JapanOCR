SHELL := /bin/bash
export PATH := $(HOME)/.local/bin:$(PATH)

.PHONY: help install install-backend install-frontend \
	run-backend run-frontend \
	lint lint-backend lint-frontend \
	format format-backend format-frontend \
	format-check format-check-backend format-check-frontend \
	test test-backend test-frontend build-frontend check

help:
	@echo "Available targets:"
	@echo "  make install        - install backend and frontend dependencies"
	@echo "  make run-backend    - start the FastAPI dev server"
	@echo "  make run-frontend   - start the Vite dev server"
	@echo "  make lint           - run all lint checks"
	@echo "  make format         - auto-format backend and frontend"
	@echo "  make format-check   - verify formatting without changing files"
	@echo "  make test           - run all tests"
	@echo "  make check          - run the full quality gate"

install: install-backend install-frontend

install-backend:
	cd backend && poetry install --no-root

install-frontend:
	cd frontend && npm install

run-backend:
	cd backend && poetry run uvicorn main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && npm run dev -- --host 0.0.0.0

lint: lint-backend lint-frontend

lint-backend:
	cd backend && poetry run ruff check .

lint-frontend:
	cd frontend && npm run lint

format: format-backend format-frontend

format-backend:
	cd backend && poetry run ruff format .

format-frontend:
	cd frontend && npm run format

format-check: format-check-backend format-check-frontend

format-check-backend:
	cd backend && poetry run ruff format --check .

format-check-frontend:
	cd frontend && npm run format:check

test: test-backend test-frontend

test-backend:
	cd backend && poetry run pytest

test-frontend:
	cd frontend && npm run test

build-frontend:
	cd frontend && npm run build

check: lint format-check test build-frontend
