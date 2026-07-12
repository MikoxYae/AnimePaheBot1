#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Downloading, cleanup, and upload helpers.

Covers download safety limits (timeouts, size caps, disk space checks),
safe filenames, ffprobe detection with safe fallbacks, and a controlled
upload result instead of a silently-swallowed exception.
"""

import json
import os
import random
import re
import shutil
import string
import subprocess

import requests

from config import (
    DOWNLOAD_DIR,
    LOG_CHANNEL,
    MAX_DOWNLOAD_SIZE_MB,
    REQUEST_TIMEOUT_SECONDS,
)
from helper.database import get_upload_method
from helper.logger import log

MAX_DOWNLOAD_SIZE_BYTES = MAX_DOWNLOAD_SIZE_MB * 1024 * 1024
FFPROBE_TIMEOUT_SECONDS = 20


class DownloadError(RuntimeError):
    """Raised when a download fails or violates a safety limit."""


class UploadError(RuntimeError):
    """Raised when an upload to Telegram fails or cannot be confirmed."""


def create_short_name(name: str) -> str:
    if len(name) > 30:
        return "".join(word[0].upper() for word in name.split() if word)
    return name


def sanitize_filename(file_name: str) -> str:
    """Remove characters that are invalid in filenames or could enable path
    traversal (e.g. "..", "/")."""
    file_name = file_name.replace("..", "")
    file_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", file_name)
    file_name = file_name.strip().strip(".")
    return file_name or "episode"


def random_string(length: int) -> str:
    if length < 1:
        raise ValueError("Length must be a positive integer.")
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(length))


def _has_enough_disk_space(path: str, min_free_mb: int) -> bool:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        log.warning("Could not check disk space for %s: %s", path, exc)
        return True  # Do not block downloads just because the check failed.
    return (usage.free / (1024 * 1024)) >= min_free_mb


def safe_download_path(user_id, task_id: str, file_name: str) -> str:
    """Build a download path confined to DOWNLOAD_DIR/<user_id>/<task_id>/,
    resistant to path traversal from a malformed filename."""
    user_dir = os.path.join(DOWNLOAD_DIR, str(int(user_id)), sanitize_filename(str(task_id)))
    os.makedirs(user_dir, exist_ok=True)
    full_path = os.path.abspath(os.path.join(user_dir, sanitize_filename(file_name)))
    if not full_path.startswith(os.path.abspath(user_dir) + os.sep):
        raise DownloadError("Refusing to write outside the user's download directory.")
    return full_path


def download_file(url: str, download_path: str, min_free_disk_mb: int) -> str:
    """Stream a file to disk with a timeout, status check, content-type
    check, and a hard size cap enforced during streaming (not just trusting
    Content-Length, which can be missing or wrong).

    On any failure, the partial file is deleted before the exception is
    re-raised as a DownloadError.
    """
    if not _has_enough_disk_space(os.path.dirname(download_path), min_free_disk_mb):
        raise DownloadError("Not enough free disk space to start this download.")

    try:
        with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type.lower():
                raise DownloadError("The source returned an HTML page instead of a video file.")

            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_DOWNLOAD_SIZE_BYTES:
                raise DownloadError(
                    f"File is larger than the {MAX_DOWNLOAD_SIZE_MB}MB limit."
                )

            written = 0
            with open(download_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    written += len(chunk)
                    if written > MAX_DOWNLOAD_SIZE_BYTES:
                        raise DownloadError(
                            f"File exceeded the {MAX_DOWNLOAD_SIZE_MB}MB limit while downloading."
                        )
                    f.write(chunk)
        return download_path
    except (requests.exceptions.RequestException, DownloadError, OSError) as exc:
        if os.path.exists(download_path):
            try:
                os.remove(download_path)
            except OSError as cleanup_exc:
                log.warning("Failed to remove partial file %s: %s", download_path, cleanup_exc)
        if isinstance(exc, DownloadError):
            raise
        raise DownloadError(f"Download failed: {exc}") from exc


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def get_media_details(path: str):
    """Return (width, height, duration) using ffprobe, or safe zero
    defaults if ffprobe is missing, times out, or fails to parse the file.
    Never raises -- and never leaves these variables undefined.
    """
    width = height = duration = 0

    if not ffprobe_available():
        log.warning("ffprobe is not installed; falling back to default media metadata.")
        return width, height, duration

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-hide_banner",
                "-loglevel", "error",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            log.warning("ffprobe exited with %s for %s: %s", result.returncode, path, result.stderr)
            return width, height, duration

        media_info = json.loads(result.stdout)
        video_stream = next(
            (s for s in media_info.get("streams", []) if s.get("codec_type") == "video"), None
        )
        if video_stream:
            width = int(video_stream.get("width") or 0)
            height = int(video_stream.get("height") or 0)
        raw_duration = media_info.get("format", {}).get("duration")
        duration = int(float(raw_duration)) if raw_duration else 0
        return width, height, duration
    except subprocess.TimeoutExpired:
        log.warning("ffprobe timed out probing %s", path)
        return 0, 0, 0
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        log.warning("Failed to read media details for %s: %s", path, exc)
        return 0, 0, 0


async def send_and_delete_file(client, chat_id, file_path, thumbnail, caption, user_id):
    """Upload the downloaded file to the user and (optionally) forward it
    to the log channel. Raises `UploadError` on any failure instead of
    swallowing the exception -- callers must only report success after this
    function returns normally.
    """
    from config import COPY_UPLOADS_TO_LOG_CHANNEL

    upload_method = get_upload_method(user_id)
    thumb_path = None

    try:
        if thumbnail:
            candidate = await client.download_media(thumbnail) if isinstance(thumbnail, str) and thumbnail.startswith("http") is False and not os.path.exists(thumbnail) else thumbnail
            thumb_path = candidate if candidate and os.path.exists(str(candidate)) else None

        try:
            user_info = await client.get_users(user_id)
            username = user_info.username if user_info and user_info.username else "Unknown"
        except Exception as exc:  # noqa: BLE001
            log.warning("Could not fetch user info for %s: %s", user_id, exc)
            username = "Unknown"
        user_details = f"Downloaded by: @{username} (ID: {user_id})"

        if upload_method == "document":
            sent_message = await client.send_document(
                chat_id,
                file_path,
                thumb=thumb_path,
                caption=caption,
            )
        else:
            width, height, duration = get_media_details(file_path)
            sent_message = await client.send_video(
                chat_id,
                file_path,
                duration=duration or None,
                width=width or None,
                height=height or None,
                supports_streaming=True,
                thumb=thumb_path,
                caption=caption,
            )

        if sent_message is None:
            raise UploadError("Telegram did not confirm the upload.")

        if COPY_UPLOADS_TO_LOG_CHANNEL:
            try:
                await client.copy_message(
                    chat_id=LOG_CHANNEL,
                    from_chat_id=chat_id,
                    message_id=sent_message.id,
                    caption=f"{caption}\n\n{user_details}",
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to mirror upload to LOG_CHANNEL: %s", exc)
        else:
            try:
                await client.send_message(LOG_CHANNEL, user_details)
            except Exception as exc:  # noqa: BLE001
                log.warning("Failed to send metadata to LOG_CHANNEL: %s", exc)

        return sent_message
    except UploadError:
        raise
    except Exception as exc:
        raise UploadError(f"Upload failed: {exc}") from exc
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as exc:
                log.warning("Failed to remove uploaded file %s: %s", file_path, exc)
        if thumb_path and thumb_path != thumbnail and os.path.exists(str(thumb_path)):
            try:
                os.remove(thumb_path)
            except OSError as exc:
                log.warning("Failed to remove thumbnail %s: %s", thumb_path, exc)


def remove_directory(directory_path: str) -> None:
    if not directory_path or not os.path.exists(directory_path):
        return
    try:
        shutil.rmtree(directory_path)
    except OSError as exc:
        log.warning("Failed to remove directory %s: %s", directory_path, exc)
