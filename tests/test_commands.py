"""Focused coverage for Twitch IRC command parsing."""

import pytest

import twitch


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr(twitch.time, "sleep", lambda _seconds: None)
    instance = twitch.TwitchBot()
    sent = []
    monkeypatch.setattr(instance, "send_message", lambda channel, text: sent.append((channel, text)))
    return instance, sent


def privmsg(text: str, *, tagged: bool = False) -> str:
    tags = "@badge-info=;display-name=Tester;id=abc " if tagged else ""
    return f"{tags}:tester!tester@tester.tmi.twitch.tv PRIVMSG #noobenheim :{text}"


@pytest.mark.parametrize("tagged", [False, True])
def test_first_token_sing_command_handles_real_privmsg(bot, tagged):
    instance, sent = bot

    instance._handle_commands(privmsg("!sing", tagged=tagged))

    assert sent == [
        (instance.config.CHANNEL, "Daisy, Daisy, Give me your answer, do."),
        (instance.config.CHANNEL, "I'm half crazy all for the love of you."),
    ]


@pytest.mark.parametrize("text", ["!singing", "hello !sing", "!unknown", "plain chat"])
def test_non_commands_and_unknown_commands_do_nothing(bot, text):
    instance, sent = bot

    instance._handle_commands(privmsg(text))

    assert sent == []


def test_command_names_are_case_insensitive(bot):
    instance, sent = bot

    instance._handle_commands(privmsg("!SiNg"))

    assert sent[0] == (instance.config.CHANNEL, "Daisy, Daisy, Give me your answer, do.")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("!say hello world", "hello world"),
        ("!xkcd 123", "http://xkcd.com/123"),
        ("!youtube abc-123", "https://www.youtube.com/watch?v=abc-123"),
        ("!beer Tester", "*Gives a beer to Tester!* Drink up!"),
    ],
)
def test_command_arguments_come_only_from_chat_payload(bot, text, expected):
    instance, sent = bot

    instance._handle_commands(privmsg(text, tagged=True))

    assert sent[0] == (instance.config.CHANNEL, expected)


def test_die_argument_still_targets_the_configured_bot(bot):
    instance, sent = bot

    instance._handle_commands(privmsg(f"!die {instance.config.NICK}"))

    assert instance.running is False
    assert sent[-1] == (instance.config.MASTER, "I have to leave now :(")
