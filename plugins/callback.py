#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

import html
import os
import re
import urllib.parse

from bs4 import BeautifulSoup
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN, DOWNLOAD_DIR, MIN_FREE_DISK_MB
from helper.database import (
    create_download_token,
    create_episode_session,
    get_caption,
    get_download_token,
    get_episode_session,
    get_search_session,
    get_thumbnail,
    save_upload_method,
    update_episode_session,
)
from helper.logger import log, log_to_channel
from helper.parsing import parse_episode_number
from plugins.direct_link import ExtractionError, get_dl_link
from plugins.file import (
    DownloadError,
    UploadError,
    create_short_name,
    download_file,
    remove_directory,
    safe_download_path,
    sanitize_filename,
    send_and_delete_file,
)
from plugins.headers import UpstreamRequestError, safe_request, session
from plugins.kwik import KwikLinkNotFoundError, extract_kwik_link
from plugins.queue import download_queue

import asyncio

START_CAPTION = "👋 Welcome to the Anime PaheBot! \n\nUse the buttons below for assistance or to contact the owner"
HELP_TEXT = (
    "Here is how to use the bot:\n\n"
    "1. /anime <anime_name> - Search for an anime.\n"
    "2. /set_thumb - Set a custom thumbnail.\n"
    "3. /options - Set upload options (Document or Video).\n"
    "4. /queue - View active downloads.\n"
    "5. /set_caption - Set custom caption.\n"
    "6. /see_caption - See current custom caption.\n"
    "7. /del_caption - Delete current custom caption"
)


async def _safe_edit_caption(message, text, reply_markup=None):
    try:
        await message.edit_caption(caption=text, reply_markup=reply_markup)
    except MessageNotModified:
        pass


async def _safe_edit_text(message, text, reply_markup=None):
    try:
        await message.edit_text(text=text, reply_markup=reply_markup)
    except MessageNotModified:
        pass


async def _expired(callback_query, text="This session has expired. Please try again."):
    await callback_query.answer(text, show_alert=True)


@Client.on_callback_query(filters.regex(r"^an:"))
async def anime_details(client, callback_query):
    try:
        _, token, idx_raw = callback_query.data.split(":", 2)
        idx = int(idx_raw)
    except (ValueError, IndexError):
        await _expired(callback_query, "This button is no longer valid.")
        return

    session_doc = await asyncio.to_thread(get_search_session, token)
    if not session_doc or session_doc.get("user_id") != callback_query.from_user.id:
        await _expired(callback_query)
        return

    results = session_doc.get("results", [])
    if idx < 0 or idx >= len(results):
        await _expired(callback_query, "This anime is no longer available. Please search again.")
        return

    anime_session = results[idx]["session"]
    query = session_doc.get("query", "")
    search_url = f"https://animepahe.ru/api?m=search&q={urllib.parse.quote_plus(query)}"

    try:
        response = (await asyncio.to_thread(safe_request, "GET", search_url)).json()
    except UpstreamRequestError as exc:
        await log_to_channel(client, str(exc), context="anime_details")
        await callback_query.answer("AnimePahe is not responding right now.", show_alert=True)
        return

    anime = next((a for a in response.get("data", []) if a.get("session") == anime_session), None)
    if not anime:
        await _expired(callback_query, "This anime is no longer available. Please search again.")
        return

    title = anime.get("title", "Unknown")
    poster_url = anime.get("poster")

    message_text = (
        f"**Title**: {html.escape(str(title))}\n"
        f"**Type**: {html.escape(str(anime.get('type', 'N/A')))}\n"
        f"**Episodes**: {html.escape(str(anime.get('episodes', 'N/A')))}\n"
        f"**Status**: {html.escape(str(anime.get('status', 'N/A')))}\n"
        f"**Season**: {html.escape(str(anime.get('season', 'N/A')))}\n"
        f"**Year**: {html.escape(str(anime.get('year', 'N/A')))}\n"
        f"**Score**: {html.escape(str(anime.get('score', 'N/A')))}\n"
        f"[Anime Link](https://animepahe.ru/anime/{urllib.parse.quote(str(anime_session))})\n\n"
        f"**Bot Made By**\n"
        f"    **[RAHAT](tg://user?id=1235222889)**"
    )

    try:
        episode_token = await asyncio.to_thread(
            create_episode_session,
            callback_query.from_user.id,
            callback_query.message.chat.id,
            anime_session,
            title,
            poster_url,
            [],
        )
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="anime_details:create_episode_session")
        await callback_query.answer("Could not open this anime right now. Please try again.", show_alert=True)
        return

    episode_button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Episodes", callback_data=f"ep_list:{episode_token}:1")]]
    )
    try:
        await client.send_photo(
            chat_id=callback_query.message.chat.id,
            photo=poster_url,
            caption=message_text,
            reply_markup=episode_button,
        )
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="anime_details:send_photo")
        await callback_query.answer("Could not display this anime right now.", show_alert=True)


async def _render_episode_list(client, callback_query, episode_token: str, page: int, edit: bool):
    episode_doc = await asyncio.to_thread(get_episode_session, episode_token)
    if not episode_doc or episode_doc.get("user_id") != callback_query.from_user.id:
        await _expired(callback_query)
        return

    anime_session = episode_doc["anime_session"]
    episodes_url = f"https://animepahe.ru/api?m=release&id={urllib.parse.quote(str(anime_session))}&sort=episode_asc&page={page}"
    try:
        response = (await asyncio.to_thread(safe_request, "GET", episodes_url)).json()
    except UpstreamRequestError as exc:
        await log_to_channel(client, str(exc), context="episode_list")
        await callback_query.answer("AnimePahe is not responding right now.", show_alert=True)
        return

    try:
        last_page = int(response.get("last_page", 1))
    except (TypeError, ValueError):
        last_page = 1
    episodes = response.get("data", [])

    episode_records = [{"label": ep.get("episode"), "session": ep.get("session")} for ep in episodes]

    await asyncio.to_thread(
        update_episode_session,
        episode_token,
        page=page,
        last_page=last_page,
        episodes=episode_records,
    )

    episode_buttons = [
        [InlineKeyboardButton(f"Episode {rec['label']}", callback_data=f"ep:{episode_token}:{i}")]
        for i, rec in enumerate(episode_records)
    ]

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("<", callback_data=f"pg:{episode_token}:{page - 1}"))
    if page < last_page:
        nav_buttons.append(InlineKeyboardButton(">", callback_data=f"pg:{episode_token}:{page + 1}"))
    if nav_buttons:
        episode_buttons.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(episode_buttons)
    text = f"Page {page}/{last_page}: Select an episode:"

    if edit:
        try:
            await callback_query.message.edit_reply_markup(reply_markup)
        except MessageNotModified:
            pass
    else:
        await callback_query.message.reply_text(text, reply_markup=reply_markup)


@Client.on_callback_query(filters.regex(r"^ep_list:"))
async def episode_list(client, callback_query):
    try:
        _, episode_token, page_raw = callback_query.data.split(":", 2)
        page = int(page_raw)
    except (ValueError, IndexError):
        await _expired(callback_query, "This button is no longer valid.")
        return
    await _render_episode_list(client, callback_query, episode_token, page, edit=False)


@Client.on_callback_query(filters.regex(r"^pg:"))
async def navigate_pages(client, callback_query):
    try:
        _, episode_token, page_raw = callback_query.data.split(":", 2)
        new_page = int(page_raw)
    except (ValueError, IndexError):
        await _expired(callback_query, "This button is no longer valid.")
        return

    episode_doc = await asyncio.to_thread(get_episode_session, episode_token)
    if not episode_doc or episode_doc.get("user_id") != callback_query.from_user.id:
        await _expired(callback_query)
        return

    last_page = episode_doc.get("last_page", 1)
    if new_page < 1:
        await callback_query.answer("You're already on the first page.", show_alert=True)
        return
    if new_page > last_page:
        await callback_query.answer("You're already on the last page.", show_alert=True)
        return

    await _render_episode_list(client, callback_query, episode_token, new_page, edit=True)


@Client.on_callback_query(filters.regex(r"^ep:"))
async def fetch_download_links(client, callback_query):
    try:
        _, episode_token, idx_raw = callback_query.data.split(":", 2)
        idx = int(idx_raw)
    except (ValueError, IndexError):
        await _expired(callback_query, "This button is no longer valid.")
        return

    episode_doc = await asyncio.to_thread(get_episode_session, episode_token)
    if not episode_doc or episode_doc.get("user_id") != callback_query.from_user.id:
        await _expired(callback_query)
        return

    episodes = episode_doc.get("episodes", [])
    if idx < 0 or idx >= len(episodes):
        await _expired(callback_query, "This episode is no longer available.")
        return

    episode_label = episodes[idx]["label"]
    episode_session_id = episodes[idx]["session"]
    anime_session = episode_doc["anime_session"]
    title = episode_doc.get("title", "Unknown")

    await asyncio.to_thread(update_episode_session, episode_token, current_episode=episode_label)

    episode_url = f"https://animepahe.ru/play/{urllib.parse.quote(str(anime_session))}/{urllib.parse.quote(str(episode_session_id))}"

    try:
        response = await asyncio.to_thread(safe_request, "GET", episode_url)
    except UpstreamRequestError as exc:
        await log_to_channel(client, str(exc), context="fetch_download_links")
        await callback_query.answer("AnimePahe is not responding right now.", show_alert=True)
        return

    soup = BeautifulSoup(response.content, "html.parser")
    download_links = soup.select("#pickDownload a.dropdown-item")
    if not download_links:
        await callback_query.message.reply_text("No download links found.")
        return

    buttons = []
    for link in download_links:
        href = link.get("href")
        label = link.get_text(strip=True)
        if not href:
            continue
        try:
            dl_token = await asyncio.to_thread(
                create_download_token,
                callback_query.from_user.id,
                callback_query.message.chat.id,
                title,
                episode_label,
                label,
                href,
            )
        except Exception as exc:  # noqa: BLE001
            await log_to_channel(client, str(exc), context="fetch_download_links:create_token")
            continue
        buttons.append([InlineKeyboardButton(label, callback_data=f"dl:{dl_token}")])

    if not buttons:
        await callback_query.message.reply_text("Could not prepare download links right now. Please try again.")
        return

    await callback_query.message.reply_text("Select a download link:", reply_markup=InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex(r"^set_method_"))
async def change_upload_method(client, callback_query):
    user_id = callback_query.from_user.id
    method = callback_query.data.split("_", 2)[2]
    if method not in ("document", "video"):
        await callback_query.answer("Unknown option.", show_alert=True)
        return

    try:
        await asyncio.to_thread(save_upload_method, user_id, method)
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="change_upload_method")
        await callback_query.answer("Could not save this setting right now.", show_alert=True)
        return

    await callback_query.answer(f"Upload method set to {method.capitalize()}")

    document_status = "✅" if method == "document" else "❌"
    video_status = "✅" if method == "video" else "❌"
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Document ({document_status})", callback_data="set_method_document"),
                InlineKeyboardButton(f"Video ({video_status})", callback_data="set_method_video"),
            ]
        ]
    )
    try:
        await callback_query.message.edit_reply_markup(buttons)
    except MessageNotModified:
        pass


async def _run_download(client, chat_id, user_id, download_record, dl_msg):
    """The actual download+upload job run by a queue worker."""
    task_id = str(download_record["_id"])
    quality_label = download_record.get("quality_label", "")
    episode_label = download_record.get("episode_label", "Unknown")
    title = download_record.get("anime_title", "Unknown Title")
    source_url = download_record["source_url"]

    try:
        kwik_link = extract_kwik_link(source_url)
        direct_link = get_dl_link(kwik_link)
    except (KwikLinkNotFoundError, ExtractionError) as exc:
        await dl_msg.edit(f"<b>Could not prepare this download:</b> {html.escape(str(exc))}")
        await log_to_channel(client, str(exc), context=f"extract_link:{task_id}")
        return

    resolution_match = re.search(r"\b\d{3,4}p\b", quality_label)
    resolution = resolution_match.group() if resolution_match else quality_label
    kind = "Dub" if "eng" in quality_label.lower() else "Sub"

    short_name = create_short_name(title)
    file_name = sanitize_filename(f"[{kind}] [{short_name}] [EP {episode_label}] [{resolution}].mp4")

    try:
        download_path = safe_download_path(user_id, task_id, file_name)
    except DownloadError as exc:
        await dl_msg.edit(f"<b>Error:</b> {html.escape(str(exc))}")
        return

    user_download_dir = os.path.dirname(download_path)

    try:
        await asyncio.to_thread(download_file, direct_link, download_path, MIN_FREE_DISK_MB)
        await dl_msg.edit("<b>Episode downloaded, uploading...</b>")

        user_thumbnail = await asyncio.to_thread(get_thumbnail, user_id)
        poster_url = None
        episode_doc = None
        # Best-effort: pull poster from the parent episode session if present.
        thumb_source = user_thumbnail

        if not thumb_source and download_record.get("poster"):
            poster_url = download_record["poster"]

        user_caption = await asyncio.to_thread(get_caption, user_id)
        caption_to_use = html.escape(user_caption) if user_caption else file_name

        await send_and_delete_file(client, chat_id, download_path, thumb_source or poster_url, caption_to_use, user_id)
        await dl_msg.edit("<b><pre>Episode Uploaded 🎉</pre></b>")
    except (DownloadError, UploadError) as exc:
        await dl_msg.edit(f"<b>Error:</b> {html.escape(str(exc))}")
        await log_to_channel(client, str(exc), context=f"download_task:{task_id}")
    except Exception as exc:  # noqa: BLE001
        await dl_msg.edit("<b>Something went wrong while processing this episode.</b>")
        await log_to_channel(client, str(exc), context=f"download_task:{task_id}")
        log.exception("Unexpected error in download task %s", task_id)
    finally:
        remove_directory(user_download_dir)


@Client.on_callback_query(filters.regex(r"^dl:"))
async def download_and_upload_file(client, callback_query):
    token = callback_query.data.split(":", 1)[1]
    record = await asyncio.to_thread(get_download_token, token)
    if not record or record.get("user_id") != callback_query.from_user.id:
        await _expired(callback_query, "This download link has expired. Please open the episode again.")
        return

    dedupe_key = f"{callback_query.from_user.id}:{record['source_url']}"
    if await download_queue.is_duplicate(dedupe_key):
        await callback_query.answer("This episode is already queued or downloading.", show_alert=True)
        return

    dl_msg = await callback_query.message.reply_text(
        f"<b>Added to queue:</b>\n<pre>{html.escape(str(record.get('episode_label', '')))}</pre>\n<b>Waiting for a free slot...</b>"
    )

    username = callback_query.from_user.username or f"user_{callback_query.from_user.id}"
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id

    async def run():
        await _run_download(client, chat_id, user_id, record, dl_msg)

    accepted, position, reason = await download_queue.enqueue(user_id, username, dedupe_key, run)
    if not accepted:
        if reason == "duplicate":
            await dl_msg.edit("<b>This episode is already queued or downloading.</b>")
        else:
            await dl_msg.edit("<b>The download queue is full right now. Please try again shortly.</b>")
        return

    if position and position > 1:
        try:
            await dl_msg.edit(f"<b>Queued.</b> Position in queue: {position}")
        except MessageNotModified:
            pass


@Client.on_callback_query(filters.regex(r"^help$"))
async def help_callback(client, callback_query):
    buttons = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Back", callback_data="back_start")],
            [InlineKeyboardButton("Close", callback_data="close")],
        ]
    )
    # /start sends a photo, so the message must be edited with
    # edit_caption(), never edit_text() (which only works on text messages).
    await _safe_edit_caption(callback_query.message, HELP_TEXT, buttons)


@Client.on_callback_query(filters.regex(r"^back_start$"))
async def back_to_start(client, callback_query):
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Owner", url="https://t.me/r4h4t_69"),
                InlineKeyboardButton("Help", callback_data="help"),
            ],
            [InlineKeyboardButton("Close", callback_data="close")],
        ]
    )
    await _safe_edit_caption(callback_query.message, START_CAPTION, buttons)


@Client.on_callback_query(filters.regex(r"^close$"))
async def close_callback(client, callback_query):
    try:
        await callback_query.message.delete()
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to delete message on close: %s", exc)
