#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
twitch.py - AvicBot Twitch IRC Chat Bot

A fun, interactive Twitch chat bot that responds to various triggers and commands.
This bot connects to Twitch's IRC server and listens for messages in a specified
channel, responding with pre-defined messages, song lyrics, movie quotes, and more.

Original Version: 2015
Rewritten for Python 3.10+: 2026

Author: Léon "Avic" Simmons
License: MIT License

Usage:
    1. Create a .env file (see .env.example) and set TWITCH_OAUTH_TOKEN
    2. Run: python twitch.py
    
The bot will connect to the specified Twitch channel and begin responding to
chat messages automatically.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import logging          # For structured logging instead of print statements
import os               # For reading environment variables (.env)
import random           # For random number generation (reserved for future use)
import re               # For regular expression pattern matching
import socket           # For IRC socket connection
import sys              # For system exit codes
import time             # For delays between messages
from pathlib import Path

# -----------------------------------------------------------------------------
# .env LOADING (no external deps)
# -----------------------------------------------------------------------------
# Loads TWITCH_OAUTH_TOKEN from a repo-root .env file if present.
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

PASS: str = os.getenv("TWITCH_OAUTH_TOKEN", "").strip()
if PASS and not PASS.startswith("oauth:"):
    PASS = f"oauth:{PASS}"



# =============================================================================
# TYPE HINTS
# =============================================================================

from typing import Optional


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Set up logging to replace print statements with structured logging
# This provides timestamps, log levels, and better debugging capabilities
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Exit codes for the program
EXIT_SUCCESS: int = 0   # Program exited successfully
EXIT_FAILURE: int = 1   # Program encountered an error

# Buffer size for receiving IRC messages (in bytes)
# 10KB should be sufficient for most Twitch chat messages
BUFFER_SIZE: int = 10240

# Default delay between multi-line messages (in seconds)
# Twitch rate-limits messages, so we need delays to avoid being throttled
MESSAGE_DELAY: float = 2.0
LONG_MESSAGE_DELAY: float = 5.0
EXTRA_LONG_DELAY: float = 10.0


# =============================================================================
# BOT CONFIGURATION
# =============================================================================

class BotConfig:
    """
    Configuration class holding all bot settings.
    
    Centralizes all configuration in one place for easy modification.
    These values can be customized to change the bot's identity and behavior.
    
    Attributes:
        NICK: The bot's nickname displayed in chat
        CHANNEL: The Twitch channel to join (must include # prefix)
        SERVER: Twitch's IRC server hostname
        PORT: IRC server port (6667 for non-SSL)
        MASTER: The bot owner's username (for special commands)
        USERNAME: IRC username for authentication
        REALNAME: IRC "real name" field
    """
    
    NICK: str = "AvicBot"
    CHANNEL: str = "#noobenheim"
    SERVER: str = "irc.twitch.tv"
    PORT: int = 6667
    MASTER: str = "Avicennasis"
    USERNAME: str = "AvicBot"
    REALNAME: str = "Avicennasis"


# =============================================================================
# RESPONSE DICTIONARIES
# =============================================================================

# Dictionary of simple keyword -> response mappings
# When the bot sees a message ending with "keyword AvicBot" or "AvicBot keyword",
# it will respond with the corresponding message
SIMPLE_REPLIES: dict[str, str] = {
    'die':      "No, you",
    'goodbye':  "I'll miss you",
    'sayonara': "I'll miss you",
    'scram':    "No, you",
    'shout':    "NO I WON'T",
    'dance':    f"*{BotConfig.NICK} dances*",
    'hi':       "Hi!",
    'hello':    "Hello!",
    'howdy':    "Howdy there, partner!",
    'time':     "It is TIME for a RHYME",
    'master':   f"{BotConfig.MASTER} is my master",
}


# =============================================================================
# TWITCH BOT CLASS
# =============================================================================

class TwitchBot:
    """
    Main Twitch IRC Bot class.
    
    Handles connection to Twitch's IRC server, message parsing, and automated
    responses to various chat triggers. The bot responds to:
    - Direct commands (prefixed with !)
    - Keyword triggers (specific words in messages)
    - Direct mentions (messages containing the bot's name)
    
    Attributes:
        config: BotConfig instance with bot settings
        socket: The IRC socket connection
        running: Boolean flag to control the main loop
    
    Example:
        bot = TwitchBot()
        bot.connect()
        bot.run()
    """
    
    def __init__(self) -> None:
        """
        Initialize the TwitchBot with default configuration.
        
        Sets up the bot's configuration and prepares for connection.
        The socket is created but not connected until connect() is called.
        """
        self.config = BotConfig()
        self.socket: Optional[socket.socket] = None
        self.running: bool = True
        
        # Compile regex patterns for matching bot mentions
        # Pattern 1: "word AvicBot" - keyword before bot name
        # Pattern 2: "AvicBot word" - keyword after bot name
        self._pattern_before = re.compile(
            rf'.*:(\w+)\W*{self.config.NICK}\W*$',
            re.IGNORECASE
        )
        self._pattern_after = re.compile(
            rf'.*:{self.config.NICK}\W*(\w+)\W*$',
            re.IGNORECASE
        )

        # Cooldown tracker for 'lol' responses (in seconds)
        self.last_lol_trigger: float = 0

        # Compiled regex for whole-word matching of laughter keywords
        self._lol_pattern = re.compile(r'\b(lol|lmao|rofl)\b')
    
    # =========================================================================
    # CONNECTION METHODS
    # =========================================================================
    
    def connect(self) -> None:
        """
        Establish connection to Twitch IRC server.
        
        Creates a socket, connects to the server, authenticates with OAuth,
        and joins the configured channel. Sends an initial greeting message
        to confirm the bot is online.
        
        Raises:
            socket.error: If connection fails
            Exception: If authentication fails
        """
        logger.info(f"Connecting to {self.config.SERVER}:{self.config.PORT}...")
        
        # Create TCP socket for IRC connection
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.config.SERVER, self.config.PORT))
        # Authenticate with Twitch using OAuth token
        # The PASS command must be sent before NICK/USER
        if not PASS:
            raise RuntimeError(
                "Missing TWITCH_OAUTH_TOKEN. Add it to .env as "
                "TWITCH_OAUTH_TOKEN=oauth:... or export it in your environment."
            )

        self._send_raw(f"PASS {PASS}")
        self._send_raw(f"USER {self.config.USERNAME} 2 3 {self.config.REALNAME}")
        self._send_raw(f"NICK {self.config.NICK}")
        
        # Join the configured channel
        self._join_channel(self.config.CHANNEL)
        
        # Send greeting message to confirm bot is online
        self.send_message(self.config.CHANNEL, f"{self.config.NICK}: Online.")
        logger.info(f"Connected and joined {self.config.CHANNEL}")
    
    def _send_raw(self, message: str) -> None:
        """
        Send a raw IRC command to the server.
        
        Encodes the message to UTF-8 and appends the required CRLF terminator.
        
        Args:
            message: The raw IRC command to send (without line ending)
        """
        if self.socket:
            self.socket.send(f"{message}\r\n".encode("utf-8"))
    
    def _join_channel(self, channel: str) -> None:
        """
        Join an IRC channel.
        
        Args:
            channel: Channel name to join (should include # prefix)
        """
        self._send_raw(f"JOIN {channel}")
        logger.info(f"Joining channel: {channel}")
    
    def send_message(self, channel: str, message: str) -> None:
        """
        Send a chat message to a channel.
        
        This is the primary method for sending visible chat messages.
        
        Args:
            channel: Target channel for the message
            message: The message content to send
        """
        self._send_raw(f"PRIVMSG {channel} :{message}")
    
    def _pong(self) -> None:
        """
        Respond to server PING with PONG.
        
        IRC servers send periodic PING messages to verify the client is still
        connected. We must respond with PONG to maintain the connection.
        """
        self._send_raw("PONG :pingis")
    
    # =========================================================================
    # MAIN LOOP
    # =========================================================================
    
    def run(self) -> None:
        """
        Main bot loop - receives and processes messages continuously.
        
        Continuously receives data from the IRC server, processes each message,
        and responds to triggers. Includes a small delay to prevent CPU spinning.
        
        The loop runs until self.running is set to False (e.g., by the !die command).
        """
        logger.info("Bot is now running. Listening for messages...")
        
        while self.running:
            try:
                # Receive data from IRC server
                raw_data = self.socket.recv(BUFFER_SIZE)
                
                if not raw_data:
                    logger.warning("Connection closed by server")
                    break
                
                # Decode and clean up the message
                message = raw_data.decode("utf-8", errors="ignore").strip('\n\r')
                
                # Log received message for debugging
                logger.debug(f"Received: {message}")
                
                # Process the message for triggers and commands
                self._process_message(message)
                
            except socket.timeout:
                # Socket timeout is normal, just continue
                continue
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                break
    
    # =========================================================================
    # MESSAGE PROCESSING
    # =========================================================================
    
    def _process_message(self, message: str) -> None:
        """
        Process an incoming IRC message and trigger appropriate responses.
        
        This is the central message handler that checks for:
        1. Server PING (keepalive)
        2. Direct bot mentions with keywords
        3. Chat commands (prefixed with !)
        4. Various trigger keywords
        
        Args:
            message: The raw IRC message to process
        """
        # ---------------------------------------------------------------------
        # PING/PONG - Server keepalive
        # ---------------------------------------------------------------------
        if "PING :" in message:
            self._pong()
            return
        
        # ---------------------------------------------------------------------
        # DIRECT BOT MENTIONS - Check for word + botname patterns
        # ---------------------------------------------------------------------
        self._handle_direct_mention(message)
        
        # ---------------------------------------------------------------------
        # BANG COMMANDS - Commands prefixed with !
        # ---------------------------------------------------------------------
        self._handle_commands(message)
        
        # ---------------------------------------------------------------------
        # KEYWORD TRIGGERS - Various fun responses
        # ---------------------------------------------------------------------
        self._handle_triggers(message)
    
    def _handle_direct_mention(self, message: str) -> None:
        """
        Handle messages that directly mention the bot with a keyword.
        
        Matches patterns like "hello AvicBot" or "AvicBot hello" and
        responds with the appropriate message from SIMPLE_REPLIES.
        
        Args:
            message: The IRC message to check for mentions
        """
        # Try to match "word BotName" pattern
        match = self._pattern_before.match(message)
        
        # If that didn't match, try "BotName word" pattern
        if match is None:
            match = self._pattern_after.match(message)
        
        # If we found a match, look up the keyword and respond
        if match:
            keyword = match.group(1).lower()
            if keyword in SIMPLE_REPLIES:
                self.send_message(self.config.CHANNEL, SIMPLE_REPLIES[keyword])
                logger.info(f"Sent dictionary response for: {keyword}")
    
    def _handle_commands(self, message: str) -> None:
        """
        Handle chat commands prefixed with !
        
        Supported commands:
            !die <botname>  - Gracefully disconnect the bot
            !say <text>     - Echo text back to chat
            !sing           - Sing a song
            !random         - Generate a "random" number
            !commands       - List available commands
            !xkcd <num>     - Link to an XKCD comic
            !youtube <id>   - Link to a YouTube video
            !beer <user>    - Give a beer to someone
        
        Args:
            message: The IRC message to check for commands
        """
        channel = self.config.CHANNEL
        
        # -----------------------------------------------------------------
        # !die - Gracefully shut down the bot
        # -----------------------------------------------------------------
        if f"!die {self.config.NICK}" in message:
            self.send_message(channel, "Do you wanna build a snowman?")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "It doesn't have to be a snowman.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "Ok, Bye :(")
            self.send_message(self.config.MASTER, "I have to leave now :(")
            logger.info("Bot shutting down via !die command")
            self.running = False
            return
        
        # -----------------------------------------------------------------
        # !say - Echo a message back to chat
        # -----------------------------------------------------------------
        if "!say " in message:
            parts = message.split("!say ", 1)
            if len(parts) > 1:
                text = parts[1]
                self.send_message(channel, text)
                self.send_message(self.config.MASTER, f"Message sent: {text}")
                logger.info(f"Sent say command: {text}")
        
        # -----------------------------------------------------------------
        # !sing - Sing "Daisy Bell" (HAL 9000 reference)
        # -----------------------------------------------------------------
        if "!sing" in message:
            self.send_message(channel, "Daisy, Daisy, Give me your answer, do.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "I'm half crazy all for the love of you.")
            logger.info("Sent sing command")
        
        # -----------------------------------------------------------------
        # !random - Return a "random" number (d20 joke)
        # Chosen by fair dice roll. Guaranteed to be random.
        # -----------------------------------------------------------------
        if "!random" in message:
            self.send_message(channel, "7.")
            logger.info("Sent random number")
        
        # -----------------------------------------------------------------
        # !commands - List all available commands
        # -----------------------------------------------------------------
        if "!commands" in message:
            self.send_message(channel, "Commands:")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "!say: I echo back whatever you say.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "!sing: I sing, duh.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "!random: Returns a random number.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "!die: Makes me leave :(")
            logger.info("Sent command list")
        
        # -----------------------------------------------------------------
        # !xkcd - Link to an XKCD comic
        # -----------------------------------------------------------------
        if "!xkcd " in message:
            parts = message.split("!xkcd ", 1)
            if len(parts) > 1:
                comic_num = parts[1].strip()
                self.send_message(channel, f"http://xkcd.com/{comic_num}")
                logger.info(f"Sent XKCD link: {comic_num}")
        
        # -----------------------------------------------------------------
        # !youtube - Link to a YouTube video
        # -----------------------------------------------------------------
        if "!youtube " in message:
            parts = message.split("!youtube ", 1)
            if len(parts) > 1:
                video_id = parts[1].strip()
                self.send_message(channel, f"https://www.youtube.com/watch?v={video_id}")
                logger.info(f"Sent YouTube link: {video_id}")
        
        # -----------------------------------------------------------------
        # !beer - Give a virtual beer to someone
        # -----------------------------------------------------------------
        if "!beer " in message:
            parts = message.split("!beer ", 1)
            if len(parts) > 1:
                recipient = parts[1].strip()
                self.send_message(channel, f"*Gives a beer to {recipient}!* Drink up!")
                logger.info(f"Sent beer to: {recipient}")
    
    def _handle_triggers(self, message: str) -> None:
        """
        Handle keyword triggers that cause fun responses.
        
        These are easter eggs that respond to various keywords in chat,
        including movie quotes, song lyrics, and internet humor.
        
        Args:
            message: The IRC message to check for triggers
        """
        channel = self.config.CHANNEL
        msg_lower = message.lower()
        
        # =================================================================
        # MOVIE & TV REFERENCES
        # =================================================================
        
        # The Matrix - Classic "what is the matrix" response
        if "what is the matrix?" in msg_lower:
            self.send_message(channel, 
                "No-one can be told what the matrix is. You have to see it for yourself.")
            logger.info("Sent Matrix quote")
        
        # Location query - Where are we?
        if "where are we?" in msg_lower:
            self.send_message(channel, 
                f"Last I checked, we were in {channel}, sooo...")
            logger.info("Sent location response")
        
        # =================================================================
        # PORTAL GAME REFERENCES
        # =================================================================
        
        # Portal - The cake is a lie!
        if "cake" in msg_lower:
            self.send_message(channel, "The cake is a lie!")
            logger.info("Sent cake response")
        
        # Portal - Thinking with portals
        if "portal" in msg_lower:
            self.send_message(channel, "Now you're thinking with portals!")
            logger.info("Sent portal response")
        
        # Portal 2 - Cave Johnson's lemon rant
        if "lemons" in msg_lower:
            self.send_message(channel, 
                "When life gives you lemons, don't make lemonade. "
                "Make life take the lemons back! Get mad!")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "I don't want your damn lemons! What the hell am I supposed to do with these!?")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "Demand to see life's manager! Make life rue the day it thought "
                "it could give Cave Johnson lemons!")
            logger.info("Sent lemons speech")
        
        # =================================================================
        # SHIA LABEOUF - The Song
        # =================================================================
        
        if "shia labeouf" in msg_lower:
            self.send_message(channel, "Running for your life from Shia Labeouf.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "He's brandishing a knife. It's Shia Labeouf.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "Lurking in the shadows... Hollywood superstar Shia Labeouf.")
            logger.info("Sent Shia LaBeouf song")
        
        # Request Shia song
        if "request shia" in msg_lower:
            self.send_message(channel, 
                "!request https://www.youtube.com/watch?v=o0u4M6vppCI")
            logger.info("Sent Shia LaBeouf video request")
        
        # =================================================================
        # MUSIC REFERENCES
        # =================================================================
        
        # Haddaway - What is Love
        if " love" in msg_lower:
            self.send_message(channel, "What is love? Baby, don't hurt me.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "Don't hurt me.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "No more.")
            logger.info("Sent Haddaway song")
        
        # Blink-182 - All The Small Things
        if "work sucks" in msg_lower:
            self.send_message(channel, 
                "I know. She left me roses by the stairs.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, "Surprises let me know she cares.")
            logger.info("Sent Blink-182 lyrics")
        
        # They Might Be Giants - New York City
        if "new york city" in msg_lower:
            self.send_message(channel, 
                "'Cause everyone's your friend in New York City! "
                "And everything looks beautiful when you're young and pretty.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "The streets are paved with diamonds and there's just so much to see. "
                "But the best thing about New York City is you and me.")
            logger.info("Sent New York City lyrics")
        
        # The Muppets - Rainbow Connection
        if "rainbow" in msg_lower:
            self.send_message(channel, 
                "Someday we'll find it, the rainbow connection. "
                "The lovers, the dreamers and me.")
            logger.info("Sent Rainbow Connection")
        
        # The Duck Song
        if "duck" in msg_lower:
            self.send_message(channel, "A duck walked up to a lemonade stand...")
            logger.info("Sent Duck Song")
        
        # =================================================================
        # MUSICAL THEATER
        # =================================================================
        
        # Avenue Q - Everyone's A Little Bit Racist
        if "racist" in msg_lower:
            self.send_message(channel, 
                "Everyone's a little bit racist, Sometimes.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "Doesn't mean we go around committing hate crimes!")
            logger.info("Sent Avenue Q lyrics")
        
        # The Producers - Springtime for Hitler
        if "hitler" in msg_lower:
            self.send_message(channel, 
                "Springtime for Hitler and Germany! Deutschland is happy and gay!")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "We're marching to a faster pace! Look out, here comes the master race!")
            logger.info("Sent The Producers - Hitler")
        
        if "nazi" in msg_lower:
            self.send_message(channel, 
                "Don't be stupid, be a smarty, come and join the Nazi party!")
            logger.info("Sent The Producers - Nazi")
        
        # Gilbert & Sullivan - The Pirates of Penzance
        if "major-general" in msg_lower:
            self._sing_major_general()
        
        # =================================================================
        # MOANA SONGS
        # =================================================================
        
        # You're Welcome - Maui's song
        if "thanks" in msg_lower:
            self.send_message(channel, "So what can I say except you're welcome?")
            logger.info("Sent You're Welcome")
        elif "thank you" in msg_lower:
            self.send_message(channel, 
                "I guess it's just my way of being me! You're welcome, you're welcome!")
            logger.info("Sent You're Welcome")
        
        # Shiny - Tamatoa's song
        if "shiny" in msg_lower:
            self.send_message(channel, 
                "Shiny! Watch me dazzle like a diamond in the rough. "
                "Strut my stuff; my stuff is so")
            time.sleep(LONG_MESSAGE_DELAY)
            self.send_message(channel, 
                "Shiny! Send your armies but they'll never be enough. "
                "My shell's too tough!")
            logger.info("Sent Shiny song")
        
        # =================================================================
        # INTERNET HUMOR & MISC
        # =================================================================
        
        # Classic internet humor
        if "boobs" in msg_lower:
            self.send_message(channel, "BOOBS!")
            logger.info("Sent BOOBS!")
        
        if "boobies" in msg_lower:
            self.send_message(channel, "BOOBIES!")
            logger.info("Sent BOOBIES!")
        
        # Common chat expressions
        if "yay" in msg_lower:
            self.send_message(channel, "Yay! ^_^")
            logger.info("Sent Yay!")
        
        # Check for laughter keywords with whole-word matching and cooldown
        # Cooldown: 5 minutes (300 seconds)
        if self._lol_pattern.search(msg_lower):
            current_time = time.time()
            if current_time - self.last_lol_trigger > 300:
                self.send_message(channel, "lol")
                self.last_lol_trigger = current_time
                logger.info("Sent lol")
        
        # Ping response triggers lol (keep chat active)
        if "PING :tmi.twitch.tv" in message:
            self.send_message(channel, "lol")
            logger.info("Sent lol (ping trigger)")
        
        # Crazy loop
        if "crazy" in msg_lower:
            self.send_message(channel, 
                "Crazy? I was crazy once. They locked me up in a padded room until I died.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "They put 3 flowers on my grave. Two grew up, and one grew down.")
            time.sleep(MESSAGE_DELAY)
            self.send_message(channel, 
                "The roots tickled my nose. It drove me crazy.")
            logger.info("Sent Crazy message")
        
        # =================================================================
        # OWNER SUPPORT
        # =================================================================
        
        # Compliment the owner's music picks
        if (":avicennasis!avicennasis@avicennasis.tmi.twitch.tv "
            "PRIVMSG #noobenheim :!request " in message):
            self.send_message(channel, "Ooo, good pick Avic!")
            logger.info("Sent owner compliment")
        
        # Rival bot harassment (friendly competition)
        if ":noobbot2000!noobbot2000@noobbot2000.tmi.twitch.tv PRIVMSG" in message:
            self.send_message(channel, "I'm a better bot. -_-")
            logger.info("Sent bot rivalry message")
    
    def _sing_major_general(self) -> None:
        """
        Sing "I Am the Very Model of a Modern Major-General" from Pirates of Penzance.
        
        This is the full song, delivered with appropriate dramatic pauses.
        Gilbert & Sullivan would be proud (or horrified).
        """
        channel = self.config.CHANNEL
        
        # Verse 1
        lyrics_v1 = [
            "I am the very model of a modern Major-General,",
            "I've information vegetable, animal, and mineral,",
            "I know the kings of England, and I quote the fights historical",
            "From Marathon to Waterloo, in order categorical;",
            "I'm very well acquainted, too, with matters mathematical,",
            "I understand equations, both the simple and quadratical,",
            "About binomial theorem I'm teeming with a lot o' news,",
        ]
        
        for line in lyrics_v1:
            self.send_message(channel, line)
            time.sleep(LONG_MESSAGE_DELAY)
        
        self.send_message(channel, 
            "With many cheerful facts about the square of the hypotenuse.")
        time.sleep(LONG_MESSAGE_DELAY)
        
        # Verse 2
        lyrics_v2 = [
            "I'm very good at integral and differential calculus;",
            "I know the scientific names of beings animalculous:",
            "In short, in matters vegetable, animal, and mineral,",
            "I am the very model of a modern Major-General.",
            "I know our mythic history, King Arthur's and Sir Caradoc's;",
            "I answer hard acrostics, I've a pretty taste for paradox,",
            "I quote in elegiacs all the crimes of Heliogabalus,",
            "In conics I can floor peculiarities parabolous;",
            "I can tell undoubted Raphaels from Gerard Dows and Zoffanies,",
            "I know the croaking chorus from The Frogs of Aristophanes!",
            "Then I can hum a fugue of which I've heard the music's din afore,",
        ]
        
        for line in lyrics_v2:
            self.send_message(channel, line)
            time.sleep(LONG_MESSAGE_DELAY)
        
        self.send_message(channel, 
            "And whistle all the airs from that infernal nonsense Pinafore.")
        time.sleep(LONG_MESSAGE_DELAY)
        
        # Verse 3
        lyrics_v3 = [
            "Then I can write a washing bill in Babylonic cuneiform,",
            "And tell you ev'ry detail of Caractacus's uniform.",
            "In short, in matters vegetable, animal, and mineral,",
            "I am the very model of a modern Major-General.",
            "In fact, when I know what is meant by 'mamelon' and 'ravelin',",
            "When I can tell at sight a Mauser rifle from a javelin,",
            "When such affairs as sorties and surprises I'm more wary at,",
            "And when I know precisely what is meant by 'commissariat',",
            "When I have learnt what progress has been made in modern gunnery,",
            "When I know more of tactics than a novice in a nunnery",
            "In short, when I've a smattering of elemental strategy",
        ]
        
        for line in lyrics_v3:
            self.send_message(channel, line)
            time.sleep(LONG_MESSAGE_DELAY)
        
        self.send_message(channel, 
            "You'll say a better Major-General has never sat a gee.")
        time.sleep(LONG_MESSAGE_DELAY)
        
        # Finale
        finale = [
            "For my military knowledge, though I'm plucky and adventury,",
            "Has only been brought down to the beginning of the century;",
            "But still, in matters vegetable, animal, and mineral,",
            "I am the very model of a modern Major-General.",
        ]
        
        for line in finale:
            self.send_message(channel, line)
            time.sleep(LONG_MESSAGE_DELAY)
        
        logger.info("Sent Major-General full song")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main() -> int:
    """
    Main entry point for the Twitch bot.
    
    Creates a TwitchBot instance, connects to the server, and runs the main loop.
    Handles keyboard interrupts gracefully for clean shutdown.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    logger.info("=" * 60)
    logger.info("AvicBot Twitch IRC Bot")
    logger.info("Author: Léon 'Avic' Simmons")
    logger.info("License: MIT")
    logger.info("=" * 60)
    
    try:
        # Create and configure the bot
        bot = TwitchBot()
        
        # Connect to Twitch IRC
        bot.connect()
        
        # Run the main message loop
        bot.run()
        
        logger.info("Bot shut down gracefully")
        return EXIT_SUCCESS
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C)")
        return EXIT_SUCCESS
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return EXIT_FAILURE


# Standard Python idiom to run main() when script is executed directly
# This allows the module to be imported without automatically running
if __name__ == "__main__":
    sys.exit(main())
