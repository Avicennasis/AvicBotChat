#!/usr/bin/env python3
"""AvicBotChat - one entrypoint for both bots (flat repo).

Run either bot from a single command using flags:
  python avicbot.py --Twitch
  python avicbot.py --Wikimedia

Or run both:
  python avicbot.py --Twitch --Wikimedia

Secrets/config are loaded from a repo-root .env file (see .env.example).
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _load_dotenv(dotenv_path: Path) -> None:
    """Minimal .env loader (no external deps).

    Loads KEY=VALUE lines into os.environ if the key is not already set.
    Supports:
      - comments starting with #
      - blank lines
      - optional wrapping quotes: KEY="value" or KEY='value'
    """
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

        # Strip surrounding quotes.
        if (len(val) >= 2) and (val[0] == val[-1]) and val[0] in ('"', "'"):
            val = val[1:-1]

        os.environ.setdefault(key, val)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="avicbot",
        description="Run AvicBot Twitch and/or Wikimedia IRC bots from one entrypoint.",
    )

    # Keep the flag casing the user asked for, but also accept lowercase.
    p.add_argument(
        "--Twitch",
        "--twitch",
        dest="twitch",
        action="store_true",
        help="Run the Twitch IRC bot (twitch.py).",
    )
    p.add_argument(
        "--Wikimedia",
        "--wikimedia",
        dest="wikimedia",
        action="store_true",
        help="Run the async IRC bot (avicbotirc.py).",
    )
    p.add_argument("--version", action="version", version="AvicBotChat 2026.02")
    return p


def _spawn(script_path: Path) -> subprocess.Popen:
    """Spawn a bot as a child process using the current Python interpreter."""
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script: {script_path}")

    # Start a new session so we can terminate the whole process group cleanly.
    kwargs: dict = {}
    if os.name != "nt":
        kwargs["start_new_session"] = True

    return subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(ROOT),
        env=os.environ.copy(),
        **kwargs,
    )


def _terminate(proc: subprocess.Popen) -> None:
    """Best-effort termination."""
    try:
        if proc.poll() is not None:
            return

        if os.name == "nt":
            proc.terminate()
            return

        # On POSIX, terminate the whole process group.
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # Load repo-root .env (optional) so both bots can share secrets/config.
    _load_dotenv(ROOT / ".env")

    if not args.twitch and not args.wikimedia:
        _build_parser().print_help(sys.stderr)
        return 2

    procs: list[subprocess.Popen] = []

    try:
        if args.twitch:
            procs.append(_spawn(ROOT / "twitch.py"))
        if args.wikimedia:
            procs.append(_spawn(ROOT / "avicbotirc.py"))

        # Wait for all children. If any exits non-zero, bubble it up.
        exit_code = 0
        for p in procs:
            rc = p.wait()
            if rc != 0 and exit_code == 0:
                exit_code = rc
        return exit_code

    except KeyboardInterrupt:
        for p in procs:
            _terminate(p)
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                try:
                    if os.name == "nt":
                        p.kill()
                    else:
                        os.killpg(p.pid, signal.SIGKILL)
                except Exception:
                    pass
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
