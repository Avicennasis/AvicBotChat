# Changelog

All notable changes to `AvicBotChat` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffolding.

## [1.0.0] - 2026-07-02

### Added
- Twitch IRC bot (`twitch.py`): TLS connection on port 6697, chat commands
  (`!sing`, `!say`, `!random`, `!commands`, `!xkcd`, `!youtube`, `!beer`,
  `!die`), and keyword/dictionary response triggers.
- Wikimedia/Libera IRC bot (`avicbotwikimedia.py`): async client over TLS,
  Wikipedia/Wikimedia lookups, language-code database, `!cauth` and `!link`
  commands, and NickServ authentication.
- Shared minimal `.env` loader (`dotenv_loader.py`) used by all three entry
  points, with no external dependency.
- `pytest` test suite and `ruff` lint/format gate (CI on Python 3.14).
