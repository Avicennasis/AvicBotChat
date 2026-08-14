"""Regression tests for the whole-word chat triggers (Redmine #49439).

Commit 86c924e converted the last twelve bare-substring triggers in
``TwitchBot._handle_triggers`` to the ``_word_in`` whole-word helper. These
tests exercise the real trigger path with the socket-facing methods stubbed,
and assert three things per converted trigger:

1. NEGATIVE CONTROL: the old bare-substring check *does* match the
   false-positive message, so the bug being fixed was real and the case is
   not vacuously green.
2. The fixed code does not respond to that false-positive message at all.
3. The fixed code still responds to a legitimate whole-word message.
"""

import pytest

import twitch


@pytest.fixture
def fire(monkeypatch):
    """Return ``fire(message) -> (messages_sent, sang_major_general)``.

    Everything patched here goes through ``monkeypatch`` so it is undone at
    the end of the test rather than leaking into the rest of the session.
    The inter-message delays are zeroed instead of stubbing ``time.sleep``,
    which would otherwise be a process-wide change to the stdlib module.
    """
    monkeypatch.setattr(twitch, "MESSAGE_DELAY", 0)
    monkeypatch.setattr(twitch, "LONG_MESSAGE_DELAY", 0)

    bot = twitch.TwitchBot()
    sent: list[str] = []
    sang: list[bool] = []
    monkeypatch.setattr(bot, "send_message", lambda _channel, message: sent.append(message))
    monkeypatch.setattr(bot, "_sing_major_general", lambda: sang.append(True))

    def _fire(message: str) -> tuple[list[str], bool]:
        sent.clear()
        sang.clear()
        bot._handle_triggers(message)
        return list(sent), bool(sang)

    return _fire


# (trigger, false-positive message, legitimate message, expected reply fragment,
#  whether the trigger answers with the Major-General song instead of a message)
CASES = [
    ("lemons", "nice lemonsqueezer", "when life gives you lemons", "When life gives you lemons", False),
    ("rainbow", "double rainbows everywhere", "sing rainbow connection", "the rainbow connection", False),
    ("racist", "reading antiracist books", "that's racist", "Everyone's a little bit racist", False),
    ("hitler", "studying hitlerism", "hitler jokes again", "Springtime for Hitler", False),
    ("nazi", "the rise of nazism", "grammar nazi", "join the Nazi party", False),
    ("major-general", "the major-generals arrived", "do the major-general song", None, True),
    ("thanks", "happy thanksgiving", "thanks bot", "So what can I say except you're welcome?", False),
    ("thank you", "go thank yourself", "thank you so much", "my way of being me", False),
    ("boobs", "boobsledding season", "boobs", "BOOBS!", False),
    ("boobies", "a boobiesque painting", "boobies", "BOOBIES!", False),
    ("yay", "yayyy", "yay!", "Yay! ^_^", False),
    ("crazy", "welcome to crazytown", "that's crazy", "Crazy? I was crazy once", False),
]


@pytest.mark.parametrize(
    ("word", "fp_message", "ok_message", "reply_fragment", "sings_major_general"),
    CASES,
    ids=[case[0] for case in CASES],
)
def test_trigger_matches_whole_words_only(fire, word, fp_message, ok_message, reply_fragment, sings_major_general):
    # 1. Negative control: the pre-fix bare-substring check fired on this message.
    assert word in fp_message.lower(), f"{word!r} is not a substring of {fp_message!r}"

    # 2. The false positive must no longer draw any response.
    sent, sang = fire(fp_message)
    assert sent == [], f"{word!r} still fires on {fp_message!r}"
    assert not sang, f"{word!r} still sings the Major-General on {fp_message!r}"

    # 3. A legitimate whole-word use must still fire.
    sent, sang = fire(ok_message)
    if sings_major_general:
        assert sang, f"{word!r} no longer sings the Major-General on {ok_message!r}"
    else:
        assert any(reply_fragment in message for message in sent), (
            f"{word!r} no longer fires on {ok_message!r}: sent={sent}"
        )
