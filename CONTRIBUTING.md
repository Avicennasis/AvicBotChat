# Contributing to AvicBotChat

Thanks for considering a contribution. Bug reports, docs fixes, and small
improvements are all welcome.

## Dev setup

```bash
git clone https://github.com/Avicennasis/AvicBotChat.git
cd AvicBotChat
python3 -m venv .venv && . .venv/bin/activate
pip install ruff pytest python-dotenv
pre-commit install
```

(There is no `pyproject.toml` — dependencies are installed manually
above. See `tests/` for the unit-test deps and the `.py` files at the
repo root for the runtime deps.)

## Running the tests

```bash
pytest tests/ -v
```

CI runs the same `pytest tests/ -v` plus `ruff check .` and
`ruff format --check .` against Python 3.12. Make sure both are clean
locally before opening a PR.

## Code style

This project uses [ruff](https://github.com/astral-sh/ruff) for linting
and formatting, wired in via pre-commit. Ruff's `S` rule group covers
the security checks that used to live in bandit. `pre-commit run --all-files`
runs the full check locally; CI runs the same hooks.

## PR checklist

- [ ] Tests added or updated; `pytest` is green locally.
- [ ] `pre-commit run --all-files` is clean.
- [ ] README and docs updated if public behavior changed.
- [ ] `CHANGELOG.md` updated under `[Unreleased]`.

## Code of Conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
Be respectful; assume good faith.
