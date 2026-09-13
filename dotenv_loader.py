"""Minimal .env loader shared by the AvicBotChat scripts (no external deps).

Loads KEY=VALUE lines into os.environ if the key is not already set.
Supports comments starting with #, blank lines, and optional wrapping quotes
(KEY="value" or KEY='value').
"""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists() or not dotenv_path.is_file():
        return

    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            continue

        if (len(val) >= 2) and (val[0] == val[-1]) and val[0] in ('"', "'"):
            val = val[1:-1]

        os.environ.setdefault(key, val)
