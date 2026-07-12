#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Shared logging helper.

Use `log` for normal process logs (stdout/journald), and
`await log_to_channel(client, text)` to also mirror important events to the
configured Telegram log channel. `log_to_channel` is best-effort and never
raises -- a broken/unreachable log channel must never crash a handler.

Never pass secrets (bot token, API hash, GitHub token, Mongo URI, cookies,
auth headers) into either of these.
"""

import logging

from config import LOG_CHANNEL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

log = logging.getLogger("animepahebot")

_MAX_LOG_MESSAGE_LENGTH = 3500


def _truncate(text: str, limit: int = _MAX_LOG_MESSAGE_LENGTH) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n...[truncated]..."


async def log_to_channel(client, text: str, context: str = "") -> None:
    """Best-effort mirror of an error/event to the configured log channel."""
    message = f"{context}\n\n{text}" if context else text
    message = _truncate(message)
    try:
        await client.send_message(LOG_CHANNEL, message)
    except Exception as exc:  # noqa: BLE001 - a logging helper must not raise
        log.warning("Failed to deliver message to LOG_CHANNEL: %s", exc)
