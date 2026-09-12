# Contributing

Thanks for taking the time to contribute to `cinebox`! 🎬

This project is small and pragmatic. Keep changes tight and focused.

## Setup

```bash
uv sync --group dev
```

## Development loop

```bash
uv run pytest                 # entire hermetic suite (no network)
uv run ruff check src tests   # lint
uv run ruff format --check src tests
```

Lint and tests must stay green. The test suite is deliberately hermetic — it
never hits the network, so it stays fast and reproducible.

## Pull requests

1. Fork the repo and create a branch (`feat/…`, `fix/…`).
2. Make your change. If it touches CLI behavior, bump the affected tests.
3. Run `pytest` + `ruff` locally.
4. Open a PR with a short description of what and why.

## Style notes

- Target Python 3.11+.
- Keep new features off the critical import path (lazy imports where heavy).
- New config knobs get a default in `src/cinebox/config.py` and row in
  `src/cinebox/settings.py`.
- Never hard-code API keys or scrape private/authenticated endpoints —
  the project is API-key-free by design.

## Reporting issues

Open an issue with: the exact command you ran, your `cinebox --version`,
Python version, player in use, and a `--verbose` trace if it crashes.