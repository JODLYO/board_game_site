.PHONY: test lint format check

test:
	cd set_game_project && poetry run pytest . && poetry run ruff check

lint:
	cd set_game_project && poetry run mypy .

format:
	poetry run ruff format
