"""Tests for IRC message parsing and language lookups."""

import pytest

from avicbotwikimedia import IRCBot, BotConfig, LANGUAGE_CODES


@pytest.fixture
def bot():
    config = BotConfig(nick="TestBot", server="localhost", port=6667)
    return IRCBot(config)


class TestParseMessage:
    def test_privmsg(self, bot):
        result = bot.parse_message(":Nick!user@host PRIVMSG #channel :Hello world")
        assert result is not None
        sender, command, target, message = result
        assert "Nick" in sender
        assert command == "PRIVMSG"
        assert target == "#channel"
        assert message == "Hello world"

    def test_privmsg_no_message(self, bot):
        result = bot.parse_message(":Nick!user@host JOIN #channel")
        assert result is not None
        _, command, target, _ = result
        assert command == "JOIN"
        assert target == "#channel"

    def test_ping(self, bot):
        # PING doesn't have prefix
        result = bot.parse_message("PING :server.example.com")
        assert result is not None
        _, command, target, _ = result
        assert command == "PING"

    def test_empty_message(self, bot):
        result = bot.parse_message("")
        assert result is None

    def test_message_with_colons(self, bot):
        result = bot.parse_message(":Nick!user@host PRIVMSG #ch :time: 12:30")
        assert result is not None
        _, _, _, message = result
        assert message == "time: 12:30"

    def test_sender_extraction(self, bot):
        result = bot.parse_message(":LongNick123!~user@192.168.1.1 PRIVMSG #test :hi")
        assert result is not None
        sender, _, _, _ = result
        assert sender.startswith("LongNick123")


class TestLanguageLookups:
    def test_common_codes(self):
        assert LANGUAGE_CODES["en"] == "English"
        assert LANGUAGE_CODES["es"] == "Spanish"
        assert LANGUAGE_CODES["ja"] == "Japanese"
        assert LANGUAGE_CODES["zh"] == "Chinese"

    def test_special_codes(self):
        assert LANGUAGE_CODES["zh-yue"] == "Cantonese"
        assert LANGUAGE_CODES["be-x-old"] == "Belarusian (Taraškievica)"
        assert LANGUAGE_CODES["simple"] == "Simple English"
        assert LANGUAGE_CODES["zh-min-nan"] == "Min Nan"
        assert LANGUAGE_CODES["zh-classical"] == "Classical Chinese"

    def test_regional_codes(self):
        assert LANGUAGE_CODES["war"] == "Waray-Waray"
        assert LANGUAGE_CODES["ceb"] == "Cebuano"
        assert LANGUAGE_CODES["sco"] == "Scots"

    def test_unknown_code(self):
        assert "zzz" not in LANGUAGE_CODES

    def test_dictionary_size(self):
        # Should have 290+ entries
        assert len(LANGUAGE_CODES) > 290


class TestConversationalPatterns:
    def test_pattern_before_nick(self, bot):
        match = bot._pattern_before.search("hello TestBot")
        assert match is not None
        assert match.group(1).lower() == "hello"

    def test_pattern_after_nick(self, bot):
        match = bot._pattern_after.search("TestBot dance")
        assert match is not None
        assert match.group(1).lower() == "dance"

    def test_no_match(self, bot):
        match = bot._pattern_before.search("unrelated message")
        assert match is None
        match = bot._pattern_after.search("unrelated message")
        assert match is None
