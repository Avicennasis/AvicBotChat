# AvicBotChat (flat repo)

Two bots, one launcher:

- **Twitch bot** (Twitch IRC / tmi): `twitch.py`
- **Wikimedia bot** (regular IRC, async): `avicbotwikimedia.py`

## Setup

1) Copy the example env file:

```bash
cp .env.example .env
```

2) Edit `.env` and set your Twitch token:

```env
TWITCH_OAUTH_TOKEN=oauth:your_token_here
```

(You can also put the Wikimedia bot settings in `.env` using the `AVICBOT_...` variables below.)

## Run

```bash
python avicbot.py --Twitch
python avicbot.py --Wikimedia
python avicbot.py --Twitch --Wikimedia
```

## Configuration

### Twitch

- **Required:** `TWITCH_OAUTH_TOKEN` (in `.env` or your shell environment)
- To change the Twitch bot nick/channel/master, edit the `BotConfig` class near the top of `twitch.py`.

### Wikimedia / IRC

All settings are environment variables (so `.env` works great):

- `AVICBOT_SERVER` (default: `irc.libera.chat`)
- `AVICBOT_PORT` (default: `6667`)
- `AVICBOT_CHANNELS` comma-separated (default: `#avicbot`)
- `AVICBOT_NICK` (default: `AvicBot`)
- `AVICBOT_MASTER` (default: `Avicennasis`)
- `AVICBOT_USERNAME` (default: `AvicBot`)
- `AVICBOT_REALNAME` (default: `Avicennasis`)
- `AVICBOT_PASSWORD` (optional NickServ password)
- `AVICBOT_BUFFER_SIZE` (default: `10240`)

## Repo layout (intentionally minimal)

- `avicbot.py` launcher
- `twitch.py` Twitch bot
- `avicbotwikimedia.py` IRC bot
- `.env.example` template
- `README.md`
- `LICENSE`

`.env` is ignored by git.
