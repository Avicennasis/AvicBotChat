# Changelog

All notable changes to `AvicBotChat` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
No versioned release has been published yet: the GitHub `v0.0.1` entry is a
draft, and the CLI's historical `2026.02` identifier is not a Git tag or
release. Published versions will follow
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project scaffolding (2026-02-12).
- Twitch IRC bot (`twitch.py`): TLS connection on port 6697, chat commands
  (`!sing`, `!say`, `!random`, `!commands`, `!xkcd`, `!youtube`, `!beer`,
  `!die`), and keyword/dictionary response triggers.
- Wikimedia/Libera IRC bot (`avicbotwikimedia.py`): async client,
  Wikipedia/Wikimedia lookups, language-code database, `!cauth` and `!link`
  commands, and NickServ authentication.
- `pytest` test suite and `ruff` lint/format gate (CI on Python 3.14).

### Changed
- Shared minimal `.env` loader (`dotenv_loader.py`) used by all three entry
  points, with no external dependency.
- Wikimedia/Libera IRC connections now verify TLS on port 6697.
