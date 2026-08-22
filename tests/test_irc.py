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


class TestLoggableVerb:
    """`send_raw` must never write any slice of an outgoing line to the log.

    Redacting auth commands and then logging `message.split(" ", 1)[0]`
    leaves the logged value data-dependent on the line itself, which is why
    this was reported three times (CodeQL alerts #1, #9, #12 — fixed,
    dismissed, then raised again when the line moved). The logged label now
    comes from a constant table, so no substring of an outgoing line can
    reach the log regardless of what the redaction branch does.

    Each test carries a NEGATIVE CONTROL asserting the old naive approach
    DID echo the token, per the house style.
    """

    @staticmethod
    def _naive(message: str) -> str:
        """The previous implementation, kept as the negative control."""
        return message.split(" ", 1)[0]

    def test_known_verb_maps_to_a_literal(self):
        from avicbotwikimedia import _loggable_verb

        assert _loggable_verb("PRIVMSG #chan :hello") == "PRIVMSG"
        assert _loggable_verb("privmsg #chan :hello") == "PRIVMSG"

    def test_unknown_verb_is_not_echoed(self):
        from avicbotwikimedia import _loggable_verb

        line = "SUPERSECRET hunter2"
        # negative control: the old approach echoed the raw token
        assert self._naive(line) == "SUPERSECRET"
        assert _loggable_verb(line) == "UNKNOWN"

    def test_auth_verbs_are_never_loggable(self):
        from avicbotwikimedia import _loggable_verb

        # Excluded from the table deliberately, so that even if the
        # redaction branch in send_raw is later changed, these cannot leak.
        for line in ("PASS hunter2", "NICKSERV IDENTIFY hunter2"):
            assert self._naive(line) != "UNKNOWN"  # negative control
            assert _loggable_verb(line) == "UNKNOWN"

    def test_no_substring_of_the_line_survives(self):
        from avicbotwikimedia import _LOGGABLE_IRC_VERBS, _loggable_verb

        payload = "hunter2"
        allowed = set(_LOGGABLE_IRC_VERBS.values()) | {"UNKNOWN"}
        # negative control: a bare credential with no space leaked verbatim
        assert self._naive(payload) == payload
        for line in (f"PASS {payload}", f"WEIRD {payload}", payload):
            out = _loggable_verb(line)
            assert payload not in out
            assert out in allowed


class TestTLSContext:
    """The Twitch bot sends its OAuth token via PASS, so the TLS floor matters.

    `ssl.create_default_context()` leaves `minimum_version` at the
    MINIMUM_SUPPORTED sentinel, which permits TLS 1.0/1.1 wherever the
    platform still enables them (CodeQL alert #13).
    """

    def test_context_pins_tls12_floor(self):
        import ssl

        from twitch import _make_tls_context

        # Negative control: exhibit a context that FAILS the assertion below,
        # so it cannot pass vacuously. Deliberately not asserting anything
        # about create_default_context()'s own default — that varies by
        # interpreter (3.12 reports the MINIMUM_SUPPORTED sentinel, 3.14
        # already pins TLS 1.2), so a control built on it passes locally and
        # fails in CI, which is exactly what happened here.
        permissive = ssl.create_default_context()
        permissive.minimum_version = ssl.TLSVersion.TLSv1
        assert permissive.minimum_version < ssl.TLSVersion.TLSv1_2

        assert _make_tls_context().minimum_version >= ssl.TLSVersion.TLSv1_2

    def test_context_still_verifies_certificates(self):
        import ssl

        from twitch import _make_tls_context

        ctx = _make_tls_context()
        # hardening the floor must not weaken verification
        assert ctx.verify_mode == ssl.CERT_REQUIRED
        assert ctx.check_hostname is True
