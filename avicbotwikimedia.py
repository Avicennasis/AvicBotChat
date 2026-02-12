#!/usr/bin/env python3
"""
AvicBotIRC - A Modern Python IRC Bot

This module implements a fully-featured IRC bot designed for connecting to IRC networks.
The bot provides various utility commands including language code lookups, Wikipedia/Wikimedia
tool links, and fun interactive responses.

Architecture:
    - Uses Python's asyncio for non-blocking network I/O
    - IRCBot class encapsulates all bot functionality
    - Commands are handled via a dispatcher pattern
    - Configuration is loaded from environment variables with sensible defaults

Author: Léon "Avic" Simmons (Avicennasis)
License: MIT License
Copyright (c) 2015-2026 Léon "Avic" Simmons

Original Version: 2015
Updated: January 2026
"""

import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


# -----------------------------------------------------------------------------
# .env LOADING (no external deps)
# -----------------------------------------------------------------------------
# Loads configuration from a repo-root .env file if present.
# Environment variables always win over .env entries.

def _load_dotenv(dotenv_path: Path) -> None:
    """Minimal .env loader.

    Supports KEY=VALUE lines, optional quotes, comments starting with #.
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

        if (len(val) >= 2) and (val[0] == val[-1]) and val[0] in ('"', "'"):
            val = val[1:-1]

        os.environ.setdefault(key, val)


_load_dotenv(Path(__file__).resolve().parent / ".env")


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
# Set up logging to provide visibility into bot operations.
# Log level can be adjusted via the LOG_LEVEL environment variable.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AvicBot")


# =============================================================================
# BOT CONFIGURATION
# =============================================================================
# Configuration is loaded from environment variables with fallback defaults.
# This allows deployment flexibility without code changes.

@dataclass
class BotConfig:
    """
    Bot configuration data class.
    
    All settings can be overridden via environment variables:
        - AVICBOT_NICK: Bot's IRC nickname
        - AVICBOT_SERVER: IRC server hostname
        - AVICBOT_PORT: IRC server port (default: 6667)
        - AVICBOT_CHANNELS: Comma-separated list of channels to join
        - AVICBOT_MASTER: Bot owner's nickname (receives notifications)
        - AVICBOT_USERNAME: IRC username
        - AVICBOT_REALNAME: IRC "real name" field
        - AVICBOT_PASSWORD: NickServ password (optional)
        - AVICBOT_BUFFER_SIZE: Socket buffer size in bytes
    
    Attributes:
        nick: The bot's IRC nickname displayed to other users
        server: IRC server hostname to connect to
        port: IRC server port number
        channels: List of channels to auto-join on connect
        master: Owner's nickname who receives admin notifications
        username: IRC username (ident)
        realname: "Real name" shown in WHOIS queries
        password: Optional NickServ password for authentication
        buffer_size: Size of the network receive buffer in bytes
    """
    nick: str = field(default_factory=lambda: os.getenv("AVICBOT_NICK", "AvicBot"))
    server: str = field(default_factory=lambda: os.getenv("AVICBOT_SERVER", "irc.libera.chat"))
    port: int = field(default_factory=lambda: int(os.getenv("AVICBOT_PORT", "6667")))
    channels: list[str] = field(default_factory=lambda: os.getenv("AVICBOT_CHANNELS", "#avicbot").split(","))
    master: str = field(default_factory=lambda: os.getenv("AVICBOT_MASTER", "Avicennasis"))
    username: str = field(default_factory=lambda: os.getenv("AVICBOT_USERNAME", "AvicBot"))
    realname: str = field(default_factory=lambda: os.getenv("AVICBOT_REALNAME", "Avicennasis"))
    password: Optional[str] = field(default_factory=lambda: os.getenv("AVICBOT_PASSWORD"))
    buffer_size: int = field(default_factory=lambda: int(os.getenv("AVICBOT_BUFFER_SIZE", "10240")))


# =============================================================================
# LANGUAGE CODE DATABASE
# =============================================================================
# Comprehensive dictionary mapping ISO 639 language codes to their full names.
# This replaces the original implementation's 280+ individual if-statements
# with a single efficient dictionary lookup.
#
# Sources: Wikipedia language editions, ISO 639-1 and 639-3 codes
# Last updated: January 2026

LANGUAGE_CODES: dict[str, str] = {
    # Major world languages (ISO 639-1)
    "en": "English",
    "sv": "Swedish",
    "de": "German",
    "nl": "Dutch",
    "fr": "French",
    "ru": "Russian",
    "it": "Italian",
    "es": "Spanish",
    "vi": "Vietnamese",
    "pl": "Polish",
    "ja": "Japanese",
    "pt": "Portuguese",
    "zh": "Chinese",
    "uk": "Ukrainian",
    "ca": "Catalan",
    "fa": "Persian",
    "no": "Norwegian",
    "ar": "Arabic",
    "fi": "Finnish",
    "id": "Indonesian",
    "ro": "Romanian",
    "hu": "Hungarian",
    "cs": "Czech",
    "ko": "Korean",
    "sr": "Serbian",
    "ms": "Malay",
    "tr": "Turkish",
    "da": "Danish",
    "sk": "Slovak",
    "bg": "Bulgarian",
    "he": "Hebrew",
    "lt": "Lithuanian",
    "hr": "Croatian",
    "sl": "Slovenian",
    "et": "Estonian",
    "el": "Greek",
    "hi": "Hindi",
    "th": "Thai",
    "mk": "Macedonian",
    "bn": "Bengali",
    "af": "Afrikaans",
    "ka": "Georgian",
    "az": "Azerbaijani",
    "bs": "Bosnian",
    "lv": "Latvian",
    "sq": "Albanian",
    "is": "Icelandic",
    "my": "Burmese",
    "sw": "Swahili",
    "ne": "Nepali",
    "si": "Sinhalese",
    "km": "Khmer",
    "mn": "Mongolian",
    "lo": "Lao",
    "ha": "Hausa",
    "zu": "Zulu",
    "am": "Amharic",
    "so": "Somali",
    "mt": "Maltese",
    "lb": "Luxembourgish",
    "ga": "Irish",
    "cy": "Welsh",
    "gd": "Scottish Gaelic",
    "fo": "Faroese",
    "kl": "Greenlandic",
    
    # Regional and minority languages
    "war": "Waray-Waray",
    "ceb": "Cebuano",
    "sh": "Serbo-Croatian",
    "uz": "Uzbek",
    "eo": "Esperanto",
    "kk": "Kazakh",
    "eu": "Basque",
    "hy": "Armenian",
    "gl": "Galician",
    "nn": "Norwegian (Nynorsk)",
    "vo": "Volapük",
    "la": "Latin",
    "simple": "Simple English",
    "ce": "Chechen",
    "be": "Belarusian",
    "oc": "Occitan",
    "mg": "Malagasy",
    "ur": "Urdu",
    "new": "Newar",
    "ta": "Tamil",
    "tt": "Tatar",
    "pms": "Piedmontese",
    "tl": "Tagalog",
    "te": "Telugu",
    "be-x-old": "Belarusian (Taraškievica)",
    "br": "Breton",
    "ht": "Haitian",
    "jv": "Javanese",
    "mr": "Marathi",
    "ml": "Malayalam",
    "zh-yue": "Cantonese",
    "ba": "Bashkir",
    "ky": "Kirghiz",
    "pnb": "Western Punjabi",
    "cv": "Chuvash",
    "tg": "Tajik",
    "sco": "Scots",
    "fy": "West Frisian",
    "lmo": "Lombard",
    "yo": "Yoruba",
    "an": "Aragonese",
    "ast": "Asturian",
    "zh-min-nan": "Min Nan",
    "io": "Ido",
    "gu": "Gujarati",
    "scn": "Sicilian",
    "bpy": "Bishnupriya Manipuri",
    "nds": "Low Saxon",
    "ku": "Kurdish",
    "als": "Alemannic",
    "qu": "Quechua",
    "su": "Sundanese",
    "pa": "Punjabi",
    "kn": "Kannada",
    "ckb": "Sorani",
    "bar": "Bavarian",
    "ia": "Interlingua",
    "nap": "Neapolitan",
    "arz": "Egyptian Arabic",
    "bug": "Buginese",
    "bat-smg": "Samogitian",
    "wa": "Walloon",
    "map-bms": "Banyumasan",
    "yi": "Yiddish",
    "mzn": "Mazandarani",
    "nah": "Nahuatl",
    "vec": "Venetian",
    "sah": "Sakha",
    "os": "Ossetian",
    "mrj": "Hill Mari",
    "sa": "Sanskrit",
    "li": "Limburgish",
    "hsb": "Upper Sorbian",
    "roa-tara": "Tarantino",
    "or": "Oriya",
    "pam": "Kapampangan",
    "mhr": "Meadow Mari",
    "se": "Northern Sami",
    "mi": "Maori",
    "ilo": "Ilokano",
    "bcl": "Central Bicolano",
    "hif": "Fiji Hindi",
    "gan": "Gan",
    "ps": "Pashto",
    "rue": "Rusyn",
    "glk": "Gilaki",
    "nds-nl": "Dutch Low Saxon",
    "diq": "Zazaki",
    "bo": "Tibetan",
    "azb": "South Azerbaijani",
    "vls": "West Flemish",
    "bh": "Bihari",
    "fiu-vro": "Võro",
    "xmf": "Mingrelian",
    "co": "Corsican",
    "tk": "Turkmen",
    "sc": "Sardinian",
    "gv": "Manx",
    "vep": "Vepsian",
    "hak": "Hakka",
    "csb": "Kashubian",
    "lrc": "Northern Luri",
    "kv": "Komi",
    "zea": "Zeelandic",
    "crh": "Crimean Tatar",
    "frr": "North Frisian",
    "zh-classical": "Classical Chinese",
    "eml": "Emilian-Romagnol",
    "wuu": "Wu",
    "ay": "Aymara",
    "udm": "Udmurt",
    "stq": "Saterland Frisian",
    "kw": "Cornish",
    "nrm": "Norman",
    "as": "Assamese",
    "rm": "Romansh",
    "szl": "Silesian",
    "koi": "Komi-Permyak",
    "lad": "Ladino",
    "sd": "Sindhi",
    "fur": "Friulian",
    "ie": "Interlingue",
    "gn": "Guarani",
    "pcd": "Picard",
    "dv": "Divehi",
    "dsb": "Lower Sorbian",
    "lij": "Ligurian",
    "cbk-zam": "Zamboanga Chavacano",
    "cdo": "Min Dong",
    "ksh": "Ripuarian",
    "ext": "Extremaduran",
    "gag": "Gagauz",
    "mwl": "Mirandese",
    "ang": "Anglo-Saxon",
    "lez": "Lezgian",
    "ug": "Uyghur",
    "ace": "Acehnese",
    "pi": "Pali",
    "pag": "Pangasinan",
    "nv": "Navajo",
    "frp": "Franco-Provençal",
    "sn": "Shona",
    "kab": "Kabyle",
    "myv": "Erzya",
    "ln": "Lingala",
    "pfl": "Palatinate German",
    "xal": "Kalmyk",
    "krc": "Karachay-Balkar",
    "haw": "Hawaiian",
    "rw": "Kinyarwanda",
    "pdc": "Pennsylvania German",
    "kaa": "Karakalpak",
    "to": "Tongan",
    "arc": "Aramaic",
    "nov": "Novial",
    "kbd": "Kabardian Circassian",
    "av": "Avar",
    "bxr": "Buryat",
    "bjn": "Banjar",
    "tet": "Tetum",
    "pap": "Papiamentu",
    "tpi": "Tok Pisin",
    "na": "Nauruan",
    "tyv": "Tuvan",
    "lbe": "Lak",
    "jbo": "Lojban",
    "ty": "Tahitian",
    "roa-rup": "Aromanian",
    "mdf": "Moksha",
    "za": "Zhuang",
    "ig": "Igbo",
    "wo": "Wolof",
    "nso": "Northern Sotho",
    "srn": "Sranan",
    "kg": "Kongo",
    "ab": "Abkhazian",
    "ltg": "Latgalian",
    "om": "Oromo",
    "chy": "Cheyenne",
    "rmy": "Romani",
    "cu": "Old Church Slavonic",
    "tw": "Twi",
    "mai": "Maithili",
    "gom": "Goan Konkani",
    "tn": "Tswana",
    "chr": "Cherokee",
    "pih": "Norfolk",
    "bi": "Bislama",
    "got": "Gothic",
    "sm": "Samoan",
    "ss": "Swati",
    "mo": "Moldovan",
    "rn": "Kirundi",
    "ki": "Kikuyu",
    "xh": "Xhosa",
    "pnt": "Pontic",
    "bm": "Bambara",
    "iu": "Inuktitut",
    "ee": "Ewe",
    "lg": "Luganda",
    "ts": "Tsonga",
    "st": "Sesotho",
    "ks": "Kashmiri",
    "ak": "Akan",
    "fj": "Fijian",
    "ik": "Inupiak",
    "sg": "Sango",
    "ff": "Fula",
    "dz": "Dzongkha",
    "ny": "Chichewa",
    "ti": "Tigrinya",
    "ch": "Chamorro",
    "ve": "Venda",
    "tum": "Tumbuka",
    "cr": "Cree",
    "ng": "Ndonga",
    "cho": "Choctaw",
    "kj": "Kuanyama",
    "mh": "Marshallese",
    "ho": "Hiri Motu",
    "ii": "Sichuan Yi",
    "aa": "Afar",
    "mus": "Muscogee",
    "hz": "Herero",
    "kr": "Kanuri",
    "min": "Minangkabau",
}


# =============================================================================
# CONVERSATIONAL REPLIES
# =============================================================================
# Dictionary mapping trigger words to bot responses.
# When a user addresses the bot with one of these words, it responds accordingly.

CONVERSATIONAL_REPLIES: dict[str, str] = {
    "die": "No, you",
    "goodbye": "I'll miss you",
    "sayonara": "I'll miss you",
    "scram": "No, you",
    "shout": "NO I WON'T",
    "dance": "*dances*",
    "hello": "Hi",
    "howdy": "Hi",
    "time": "It is TIME for a RHYME",
    "master": "",  # Will be set dynamically with bot master's name
}


# =============================================================================
# IRC BOT CLASS
# =============================================================================

class IRCBot:
    """
    Asynchronous IRC Bot implementation.
    
    This class encapsulates all IRC bot functionality including connection management,
    message parsing, and command handling. It uses Python's asyncio for non-blocking
    network operations, allowing the bot to handle multiple messages efficiently.
    
    Features:
        - Automatic reconnection on connection loss
        - NickServ authentication support
        - Command-based message handling
        - Conversational reply triggers
        - Language code lookups
        - Wikimedia tool integration
    
    Example:
        >>> config = BotConfig()
        >>> bot = IRCBot(config)
        >>> asyncio.run(bot.run())
    
    Attributes:
        config: BotConfig instance containing bot settings
        reader: asyncio StreamReader for receiving data
        writer: asyncio StreamWriter for sending data
        running: Boolean flag indicating if bot is running
        replies: Dictionary of conversational trigger words and responses
    """
    
    def __init__(self, config: BotConfig) -> None:
        """
        Initialize the IRC bot with the given configuration.
        
        Args:
            config: BotConfig instance containing all bot settings
        """
        self.config = config
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.running: bool = False
        
        # Set up the conversational replies with dynamic master name
        self.replies = CONVERSATIONAL_REPLIES.copy()
        self.replies["master"] = f"{self.config.master} is my master"

        # Compile regex patterns for matching bot mentions
        # Pattern 1: "word AvicBot" - keyword before bot name
        # Pattern 2: "AvicBot word" - keyword after bot name
        self._pattern_before = re.compile(
            rf"(\w+)\W*{self.config.nick}\W*$", re.IGNORECASE
        )
        self._pattern_after = re.compile(
            rf"{self.config.nick}\W*(\w+)\W*$", re.IGNORECASE
        )

    async def connect(self) -> None:
        """
        Establish a connection to the IRC server.
        
        This method opens an async TCP connection to the configured IRC server
        and port. Upon successful connection, it sends the required IRC
        registration commands (USER and NICK) to identify the bot.
        
        Raises:
            ConnectionError: If unable to connect to the server
            asyncio.TimeoutError: If connection times out
        """
        logger.info(f"Connecting to {self.config.server}:{self.config.port}...")
        
        # Open async TCP connection to the IRC server
        self.reader, self.writer = await asyncio.open_connection(
            self.config.server,
            self.config.port
        )
        
        logger.info("Connection established, sending registration...")
        
        # Send USER command: USER <username> <mode> <unused> :<realname>
        # Mode 2 indicates we want to receive wallops and be invisible
        await self.send_raw(f"USER {self.config.username} 2 3 {self.config.realname}")
        
        # Send NICK command to set our nickname
        await self.send_raw(f"NICK {self.config.nick}")
        
        # Authenticate with NickServ if password is configured
        if self.config.password:
            logger.info("Authenticating with NickServ...")
            await self.send_raw(f"PRIVMSG NickServ :identify {self.config.password}")
    
    async def send_raw(self, message: str) -> None:
        """
        Send a raw IRC protocol message to the server.
        
        IRC protocol requires messages to end with CRLF (\\r\\n).
        This method handles the encoding and line termination automatically.
        
        Args:
            message: The raw IRC protocol message to send (without CRLF)
        
        Note:
            This is a low-level method. For sending channel messages,
            use send_message() instead.
        """
        if self.writer is None:
            logger.error("Cannot send message: not connected")
            return
        
        # Encode the message and append IRC protocol line terminator
        self.writer.write(f"{message}\r\n".encode("utf-8"))
        await self.writer.drain()  # Ensure data is sent
        logger.debug(f">>> {message}")
    
    async def send_message(self, target: str, message: str) -> None:
        """
        Send a PRIVMSG to a channel or user.
        
        PRIVMSG is the IRC command used for both channel messages and
        private messages. The target determines the recipient.
        
        Args:
            target: Channel name (e.g., "#channel") or nickname for PM
            message: The message text to send
        """
        await self.send_raw(f"PRIVMSG {target} :{message}")
    
    async def join_channel(self, channel: str) -> None:
        """
        Join an IRC channel.
        
        Sends the JOIN command to enter the specified channel.
        The channel name should include the # prefix.
        
        Args:
            channel: Channel name to join (e.g., "#mychannel")
        """
        await self.send_raw(f"JOIN {channel}")
        logger.info(f"Joined channel: {channel}")
    
    async def handle_ping(self, payload: str) -> None:
        """
        Respond to server PING with PONG to maintain connection.
        
        IRC servers periodically send PING messages to verify the client
        is still connected. Failing to respond with PONG results in
        disconnection (ping timeout).
        
        Args:
            payload: The payload from the PING message to echo back
        """
        await self.send_raw(f"PONG :{payload}")
        logger.debug("Responded to PING")
    
    async def handle_message(self, sender: str, target: str, message: str) -> None:
        """
        Process an incoming PRIVMSG and dispatch to appropriate handler.
        
        This is the main message routing method. It examines incoming messages
        for commands (prefixed with !) and conversational triggers (when the
        bot's nick is mentioned).
        
        Args:
            sender: Nickname of the message sender
            target: Channel or nickname where message was sent
            message: The message content
        """
        # Determine where to send replies
        # If message was sent to a channel, reply there; otherwise reply to sender
        reply_target = target if target.startswith("#") else sender
        
        # Check for commands (messages starting with !)
        if message.startswith("!"):
            await self.handle_command(sender, reply_target, message)
            return
        
        # Check for conversational triggers when bot nick is mentioned
        # Patterns: "word AvicBot" or "AvicBot word"
        match = self._pattern_before.search(message) or self._pattern_after.search(message)
        if match:
            word = match.group(1).lower()
            if word in self.replies:
                await self.send_message(reply_target, self.replies[word])
    
    async def handle_command(self, sender: str, reply_target: str, message: str) -> None:
        """
        Parse and execute bot commands.
        
        Commands are messages starting with ! and may include arguments.
        This method routes each command to its appropriate handler.
        
        Supported commands:
            !commands - List available commands
            !die <botname> - Gracefully disconnect (owner only)
            !say <text> - Echo text to channel
            !guc <username> - Global User Contributions link
            !cauth <username> - CentralAuth page link
            !link <path> - Custom link builder
            !lang <code>? - Language code lookup
            !sing - Bot sings a song
            !random - Random number (fair dice roll)
        
        Args:
            sender: Nickname of the command sender
            reply_target: Where to send command output
            message: The full command message including !
        """
        # Parse command and arguments
        parts = message.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        # ====== !commands - List available commands ======
        if command == "!commands":
            await self.send_message(reply_target, "Commands:")
            await asyncio.sleep(0.1)
            await self.send_message(reply_target, "!say: Say stuff | !lang <code>?: Language lookup")
            await asyncio.sleep(0.1)
            await self.send_message(reply_target, "!cauth: CentralAuth page for a user")
            await asyncio.sleep(0.1)
            await self.send_message(reply_target, "!guc: Global User Contributions page")
            await asyncio.sleep(0.1)
            await self.send_message(reply_target, "!die: Makes me leave :(")
        
        # ====== !die - Disconnect from IRC ======
        elif command == "!die" and args.lower() == self.config.nick.lower():
            await self.send_message(reply_target, "Do you wanna build a snowman?")
            await asyncio.sleep(0.1)
            await self.send_message(reply_target, "It doesn't have to be a snowman.")
            await asyncio.sleep(0.1)
            await self.send_message(reply_target, "Ok, Bye :(")
            await self.send_message(self.config.master, "I have to leave now :(")
            self.running = False  # Signal main loop to stop
        
        # ====== !say - Echo message to channel ======
        elif command == "!say" and args:
            await self.send_message(reply_target, args)
            await self.send_message(self.config.master, f"Message sent: {args}")
        
        # ====== !guc - Global User Contributions lookup ======
        # Links to Wikimedia's Global User Contributions tool
        elif command == "!guc" and args:
            url = f"https://guc.toolforge.org/?user={args}&blocks=true"
            await self.send_message(reply_target, url)
            await self.send_message(self.config.master, url)
        
        # ====== !cauth - CentralAuth page lookup ======
        # Links to Wikimedia's CentralAuth page for the user
        elif command == "!cauth" and args:
            url = f"https://meta.wikimedia.org/wiki/Special:CentralAuth/{args}"
            await self.send_message(reply_target, url)
            await self.send_message(self.config.master, url)
        
        # ====== !link - Custom link builder ======
        elif command == "!link" and args:
            url = f"http://avicbot.org/{args}"
            await self.send_message(reply_target, url)
            await self.send_message(self.config.master, url)
        
        # ====== !sing - Sing a song ======
        elif command == "!sing":
            await self.send_message(reply_target, "Daisy, Daisy, Give me your answer, do.")
            await asyncio.sleep(0.1)
            await self.send_message(reply_target, "I'm half crazy all for the love of you.")
        
        # ====== !random - Random number ======
        # This was chosen by a fair roll of a d20. Guaranteed to be random.
        elif command == "!random":
            await self.send_message(reply_target, "7.")
        
        # ====== !lang - Language code lookup ======
        # Format: !lang <code>? (e.g., "!lang en?")
        elif command == "!lang" and args:
            await self.handle_language_lookup(reply_target, args)
    
    async def handle_language_lookup(self, reply_target: str, args: str) -> None:
        """
        Look up a language code and respond with the full language name.
        
        This replaces the original 280+ if-statements with a single
        dictionary lookup, making the code more maintainable and efficient.
        
        Args:
            reply_target: Channel or user to send the response to
            args: The language code query (e.g., "en?" or "zh-yue?")
        """
        # Strip trailing ? and whitespace, normalize to lowercase
        code = args.rstrip("? ").lower()
        
        if code in LANGUAGE_CODES:
            language_name = LANGUAGE_CODES[code]
            await self.send_message(reply_target, f"{code} is {language_name}!")
        else:
            await self.send_message(reply_target, f"Unknown language code: {code}")
    
    def parse_message(self, raw_message: str) -> Optional[tuple[str, str, str, str]]:
        """
        Parse a raw IRC protocol message into its components.
        
        IRC message format: [:prefix] command [params] [:trailing]
        For PRIVMSG: :nick!user@host PRIVMSG #channel :message text
        
        Args:
            raw_message: The raw IRC protocol message string
        
        Returns:
            Tuple of (sender_nick, command, target, message) or None if parse fails
        
        Example:
            >>> parse_message(":Nick!user@host PRIVMSG #channel :Hello world")
            ("Nick", "PRIVMSG", "#channel", "Hello world")
        """
        # Match IRC message format with optional prefix
        # Group 1: sender nick (from prefix like :Nick!user@host)
        # Group 2: command (e.g., PRIVMSG, JOIN, PING)
        # Group 3: target (channel or nick)
        # Group 4: message content (after the :)
        match = re.match(
            r"^(?::(\S+?)(?:!|\s))?\s*(\S+)\s+(\S+)\s*(?::(.*))?$",
            raw_message
        )
        
        if match:
            sender = match.group(1) or ""
            command = match.group(2)
            target = match.group(3)
            message = match.group(4) or ""
            return sender, command, target, message
        
        return None
    
    async def run(self) -> None:
        """
        Main bot event loop.
        
        This method:
        1. Connects to the IRC server
        2. Joins configured channels
        3. Continuously reads and processes incoming messages
        4. Handles PING/PONG keepalive
        5. Routes PRIVMSG to message handlers
        
        The loop continues until self.running is set to False
        (typically via the !die command) or a connection error occurs.
        """
        await self.connect()
        self.running = True
        
        # Join all configured channels
        for channel in self.config.channels:
            await self.join_channel(channel.strip())
        
        logger.info("Bot is now running. Listening for messages...")
        
        # Buffer for accumulating partial messages
        buffer = ""
        
        while self.running:
            try:
                # Read data from the server
                # IRC messages are line-delimited, so we read and split by lines
                if self.reader is None:
                    logger.error("Reader is None, connection lost")
                    break
                
                data = await self.reader.read(self.config.buffer_size)
                
                if not data:
                    logger.warning("Connection closed by server")
                    break
                
                # Decode and add to buffer, then process complete lines
                buffer += data.decode("utf-8", errors="replace")
                lines = buffer.split("\r\n")
                
                # Keep the last incomplete line in the buffer
                buffer = lines.pop()
                
                for line in lines:
                    if not line:
                        continue
                    
                    logger.debug(f"<<< {line}")
                    
                    # Handle PING to keep connection alive
                    if line.startswith("PING"):
                        # Extract ping payload (everything after "PING :")
                        payload = line.split(":", 1)[1] if ":" in line else "pingis"
                        await self.handle_ping(payload)
                        continue
                    
                    # Parse and route other messages
                    parsed = self.parse_message(line)
                    if parsed:
                        sender, command, target, message = parsed
                        
                        if command == "PRIVMSG":
                            await self.handle_message(sender, target, message)
                
                # Small delay to prevent CPU spinning
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                logger.info("Bot shutdown requested")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(1)  # Brief delay before retry
        
        # Clean up connection
        await self.disconnect()
    
    async def disconnect(self) -> None:
        """
        Gracefully disconnect from the IRC server.
        
        Sends a QUIT message and closes the connection properly.
        """
        logger.info("Disconnecting from IRC server...")
        
        try:
            if self.writer:
                await self.send_raw("QUIT :Goodbye!")
                self.writer.close()
                await self.writer.wait_closed()
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
        
        self.reader = None
        self.writer = None
        logger.info("Disconnected.")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> int:
    """
    Application entry point.
    
    Creates the bot configuration from environment variables,
    instantiates the IRCBot, and runs the async event loop.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    logger.info("=" * 60)
    logger.info("AvicBotIRC - Starting up")
    logger.info("=" * 60)
    
    try:
        # Load configuration from environment or use defaults
        config = BotConfig()
        
        logger.info(f"Bot Nick: {config.nick}")
        logger.info(f"Server: {config.server}:{config.port}")
        logger.info(f"Channels: {', '.join(config.channels)}")
        logger.info(f"Master: {config.master}")
        
        # Create and run the bot
        bot = IRCBot(config)
        asyncio.run(bot.run())
        
        logger.info("Bot shutdown complete.")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user (Ctrl+C)")
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


# Run the bot when executed directly (not imported as a module)
if __name__ == "__main__":
    sys.exit(main())
