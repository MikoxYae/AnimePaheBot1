#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

import asyncio
import signal

from pyrogram import Client

from config import API_HASH, API_ID, BOT_TOKEN
from helper.database import DatabaseError, ensure_indexes, verify_connection
from helper.logger import log
from plugins.file import ffprobe_available
from plugins.queue import download_queue

app = Client(
    "AnimePaheBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="plugins"),
)


async def _startup_checks() -> None:
    log.info("Verifying MongoDB connection...")
    verify_connection()
    ensure_indexes()
    log.info("MongoDB is reachable and indexes are ready.")

    if not ffprobe_available():
        log.warning(
            "ffprobe was not found on PATH. Video uploads will fall back to "
            "default duration/width/height metadata. Install ffmpeg to fix this."
        )


async def main() -> None:
    try:
        await _startup_checks()
    except DatabaseError as exc:
        log.error("Startup check failed: %s", exc)
        raise SystemExit(1)

    await app.start()
    download_queue.start()
    log.info("Bot started.")

    stop_event = asyncio.Event()

    def _request_stop(*_args):
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            # add_signal_handler is not available on all platforms (e.g. Windows).
            pass

    try:
        await stop_event.wait()
    finally:
        log.info("Shutting down...")
        await download_queue.stop()
        await app.stop()
        log.info("Bot stopped cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
