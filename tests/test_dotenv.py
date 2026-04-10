"""Tests for the .env loader and BotConfig."""

import os
import tempfile
from pathlib import Path

import pytest

# Import the loader from the main entrypoint
from avicbot import _load_dotenv


@pytest.fixture(autouse=True)
def clean_env():
    """Remove test env vars before/after each test."""
    keys = ["TEST_KEY", "TEST_QUOTED", "TEST_SINGLE", "TEST_EXISTING", "TEST_EMPTY"]
    saved = {k: os.environ.pop(k, None) for k in keys}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


def test_load_basic_key_value(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_KEY=hello_world\n")
    _load_dotenv(env_file)
    assert os.environ["TEST_KEY"] == "hello_world"


def test_load_strips_double_quotes(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text('TEST_QUOTED="quoted value"\n')
    _load_dotenv(env_file)
    assert os.environ["TEST_QUOTED"] == "quoted value"


def test_load_strips_single_quotes(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_SINGLE='single quoted'\n")
    _load_dotenv(env_file)
    assert os.environ["TEST_SINGLE"] == "single quoted"


def test_skips_comments(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("# this is a comment\nTEST_KEY=value\n")
    _load_dotenv(env_file)
    assert os.environ["TEST_KEY"] == "value"


def test_skips_blank_lines(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("\n\nTEST_KEY=value\n\n")
    _load_dotenv(env_file)
    assert os.environ["TEST_KEY"] == "value"


def test_does_not_override_existing(tmp_path):
    os.environ["TEST_EXISTING"] = "original"
    env_file = tmp_path / ".env"
    env_file.write_text("TEST_EXISTING=overridden\n")
    _load_dotenv(env_file)
    assert os.environ["TEST_EXISTING"] == "original"


def test_missing_file_is_noop(tmp_path):
    _load_dotenv(tmp_path / "nonexistent")
    # Should not raise


def test_skips_lines_without_equals(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("NOEQUALS\nTEST_KEY=works\n")
    _load_dotenv(env_file)
    assert os.environ["TEST_KEY"] == "works"
    assert "NOEQUALS" not in os.environ
