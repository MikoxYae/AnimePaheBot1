#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Central configuration for AnimePaheBot.

Every value is read from environment variables (see .env.example). The rest
of the codebase keeps importing the same names it always has (API_ID,
API_HASH, BOT_TOKEN, ADMIN, LOG_CHANNEL, MONGO_URL, DB_NAME, START_PIC,
DOWNLOAD_DIR) so no other module needs to change how it imports config.

Required variables are validated at import time. If anything required is
missing or malformed, the bot fails fast with a clear message instead of
crashing later with a confusing traceback.
"""

import os
import sys

from dotenv import load_dotenv

# Load variables from a .env file in the working directory, if present.
# Real exported environment variables (e.g. from systemd's
# EnvironmentFile=) always take priority over .env.
load_dotenv(override=False)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _get_env(*names, default=None):
    """Return the first non-empty environment variable among `names`."""
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return default


def _require_str(*names, label):
    value = _get_env(*names)
    if not value:
        raise ConfigError(f"Missing required environment variable: {label}")
    return value


def _require_int(*names, label):
    raw = _require_str(*names, label=label)
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"{label} must be an integer, got: {raw!r}")


def _optional_int(*names, default):
    raw = _get_env(*names)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"Expected an integer for {names[0]}, got: {raw!r}")


def _optional_bool(*names, default):
    raw = _get_env(*names)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _load():
    api_id = _require_int("API_ID", label="API_ID")
    api_hash = _require_str("API_HASH", label="API_HASH")
    bot_token = _require_str("BOT_TOKEN", label="BOT_TOKEN")

    # LOG_CHANNEL may be a numeric Telegram channel id (e.g. -1001234567890)
    # or, where Pyrogram supports it, a public @username.
    log_channel_raw = _require_str("LOG_CHANNEL", label="LOG_CHANNEL")
    try:
        log_channel = int(log_channel_raw)
    except ValueError:
        log_channel = log_channel_raw.lstrip("@")

    # OWNER_ID is the documented name; ADMIN is accepted too for
    # backwards compatibility with older deployments of this bot.
    admin = _require_int("OWNER_ID", "ADMIN", label="OWNER_ID")

    mongo_url = _require_str("MONGO_DB_URI", "MONGO_URL", label="MONGO_DB_URI")
    db_name = _get_env("DB_NAME", default="mdb")

    start_pic_raw = _get_env(
        "START_PIC",
        default="https://graph.org/file/dfd1842d8a2dcc536a2b7.jpg",
    )
    start_pic = start_pic_raw.split()

    download_dir = os.path.abspath(_get_env("DOWNLOAD_DIR", default="./downloads"))

    return {
        "API_ID": api_id,
        "API_HASH": api_hash,
        "BOT_TOKEN": bot_token,
        "LOG_CHANNEL": log_channel,
        "ADMIN": admin,
        "OWNER_ID": admin,
        "MONGO_URL": mongo_url,
        "DB_NAME": db_name,
        "START_PIC": start_pic,
        "DOWNLOAD_DIR": download_dir,
        "MAX_CONCURRENT_DOWNLOADS": _optional_int("MAX_CONCURRENT_DOWNLOADS", default=2),
        "MAX_DOWNLOADS_PER_USER": _optional_int("MAX_DOWNLOADS_PER_USER", default=1),
        "MAX_QUEUE_SIZE": _optional_int("MAX_QUEUE_SIZE", default=50),
        "MAX_DOWNLOAD_SIZE_MB": _optional_int("MAX_DOWNLOAD_SIZE_MB", default=1900),
        "REQUEST_TIMEOUT_SECONDS": _optional_int("REQUEST_TIMEOUT_SECONDS", default=30),
        "MIN_FREE_DISK_MB": _optional_int("MIN_FREE_DISK_MB", default=2500),
        "SESSION_TTL_SECONDS": _optional_int("SESSION_TTL_SECONDS", default=3600),
        "COPY_UPLOADS_TO_LOG_CHANNEL": _optional_bool(
            "COPY_UPLOADS_TO_LOG_CHANNEL", default=True
        ),
    }


try:
    _cfg = _load()
except ConfigError as exc:
    sys.stderr.write(f"\n[CONFIG ERROR] {exc}\n")
    sys.stderr.write("Copy .env.example to .env (or export the variable) and try again.\n\n")
    raise SystemExit(1)

API_ID = _cfg["API_ID"]
API_HASH = _cfg["API_HASH"]
BOT_TOKEN = _cfg["BOT_TOKEN"]
LOG_CHANNEL = _cfg["LOG_CHANNEL"]
ADMIN = _cfg["ADMIN"]
OWNER_ID = _cfg["OWNER_ID"]
MONGO_URL = _cfg["MONGO_URL"]
DB_NAME = _cfg["DB_NAME"]
START_PIC = _cfg["START_PIC"]
DOWNLOAD_DIR = _cfg["DOWNLOAD_DIR"]
MAX_CONCURRENT_DOWNLOADS = _cfg["MAX_CONCURRENT_DOWNLOADS"]
MAX_DOWNLOADS_PER_USER = _cfg["MAX_DOWNLOADS_PER_USER"]
MAX_QUEUE_SIZE = _cfg["MAX_QUEUE_SIZE"]
MAX_DOWNLOAD_SIZE_MB = _cfg["MAX_DOWNLOAD_SIZE_MB"]
REQUEST_TIMEOUT_SECONDS = _cfg["REQUEST_TIMEOUT_SECONDS"]
MIN_FREE_DISK_MB = _cfg["MIN_FREE_DISK_MB"]
SESSION_TTL_SECONDS = _cfg["SESSION_TTL_SECONDS"]
COPY_UPLOADS_TO_LOG_CHANNEL = _cfg["COPY_UPLOADS_TO_LOG_CHANNEL"]
