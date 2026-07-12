#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

import asyncio
import html
import random
import urllib.parse

import pyrogram.errors
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bs4 import BeautifulSoup

from config import ADMIN, START_PIC
from helper.database import (
    add_user,
    del_user,
    full_userbase,
    get_caption,
    get_thumbnail,
    get_upload_method,
    present_user,
    save_caption,
    save_thumbnail,
)
from helper.logger import log, log_to_channel
from plugins.headers import UpstreamRequestError, safe_json, safe_request, session
from plugins.queue import download_queue

WAIT_MSG = "<b>Processing ...</b>"
REPLY_ERROR = "<code>Use this command as a reply to any Telegram message, with no extra text.</code>"


async def _track_user(client, user_id: int) -> None:
    """Record a new user, without letting a database hiccup crash the
    handler that's serving them."""
    try:
        if not await asyncio.to_thread(present_user, user_id):
            await asyncio.to_thread(add_user, user_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to record user %s: %s", user_id, exc)
        await log_to_channel(client, str(exc), context=f"track_user({user_id})")


def _start_view():
    start_pic = random.choice(START_PIC)
    caption = "👋 Welcome to the Anime PaheBot! \n\nUse the buttons below for assistance or to contact the owner"
    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Owner", url="https://t.me/r4h4t_69"),
                InlineKeyboardButton("Help", callback_data="help"),
            ],
            [InlineKeyboardButton("Close", callback_data="close")],
        ]
    )
    return start_pic, caption, buttons


@Client.on_message(filters.command("start") & filters.private)
async def start(client, message):
    await _track_user(client, message.from_user.id)
    start_pic, caption, buttons = _start_view()
    await client.send_photo(
        chat_id=message.chat.id,
        photo=start_pic,
        caption=caption,
        reply_markup=buttons,
    )


@Client.on_message(filters.command("set_thumb") & filters.private)
async def set_thumbnail(client, message):
    if not message.reply_to_message or not message.reply_to_message.photo:
        await message.reply_text("Please reply to a photo with this command.")
        return
    file_id = message.reply_to_message.photo.file_id
    try:
        await asyncio.to_thread(save_thumbnail, message.from_user.id, file_id)
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="set_thumbnail")
        await message.reply_text("Could not save your thumbnail right now. Please try again later.")
        return
    await message.reply_text("Thumbnail saved successfully!")


@Client.on_message(filters.command("see_thumb") & filters.private)
async def see_thumbnail(client, message):
    try:
        thumbnail = await asyncio.to_thread(get_thumbnail, message.from_user.id)
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="see_thumbnail")
        await message.reply_text("Could not load your thumbnail right now. Please try again later.")
        return
    if thumbnail:
        await client.send_photo(message.chat.id, thumbnail, caption="Your custom thumbnail.")
    else:
        await message.reply_text("No custom thumbnail found in the database.")


@Client.on_message(filters.command("del_thumb") & filters.private)
async def del_thumbnail(client, message):
    from helper.database import delete_thumbnail

    try:
        thumbnail = await asyncio.to_thread(get_thumbnail, message.from_user.id)
        if thumbnail:
            await asyncio.to_thread(delete_thumbnail, message.from_user.id)
            await message.reply_text("Custom thumbnail deleted successfully!")
        else:
            await message.reply_text("No custom thumbnail found in the database.")
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="del_thumbnail")
        await message.reply_text("Could not delete your thumbnail right now. Please try again later.")


@Client.on_message(filters.command("set_caption") & filters.private)
async def save_caption_command(client, message):
    if message.reply_to_message and message.reply_to_message.text:
        caption = message.reply_to_message.text
        try:
            await asyncio.to_thread(save_caption, message.from_user.id, caption)
        except Exception as exc:  # noqa: BLE001
            await log_to_channel(client, str(exc), context="save_caption")
            await message.reply_text("Could not save your caption right now. Please try again later.")
            return
        await message.reply_text(f"<b>Caption saved:</b> \n\n <code>{html.escape(caption)}</code>")
    else:
        await message.reply_text("Please reply to a text message to save it as a caption.")


@Client.on_message(filters.command("see_caption") & filters.private)
async def see_caption_command(client, message):
    try:
        caption = await asyncio.to_thread(get_caption, message.from_user.id)
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="see_caption")
        await message.reply_text("Could not load your caption right now. Please try again later.")
        return
    if caption:
        await message.reply_text(f"<b>Your current caption:</b> \n\n <code>{html.escape(caption)}</code>")
    else:
        await message.reply_text("No custom caption found in the database.")


@Client.on_message(filters.command("del_caption") & filters.private)
async def delete_caption_command(client, message):
    from helper.database import delete_caption

    try:
        caption = await asyncio.to_thread(get_caption, message.from_user.id)
        if caption:
            await asyncio.to_thread(delete_caption, message.from_user.id)
            await message.reply_text("Custom caption deleted successfully!")
        else:
            await message.reply_text("No custom caption found in the database.")
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="delete_caption")
        await message.reply_text("Could not delete your caption right now. Please try again later.")


@Client.on_message(filters.command("options") & filters.private)
async def set_upload_options(client, message):
    user_id = message.from_user.id
    try:
        current_method = await asyncio.to_thread(get_upload_method, user_id)
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="set_upload_options")
        await message.reply_text("Could not load your upload settings right now. Please try again later.")
        return

    document_status = "✅" if current_method == "document" else "❌"
    video_status = "✅" if current_method == "video" else "❌"

    buttons = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(f"Document ({document_status})", callback_data="set_method_document"),
                InlineKeyboardButton(f"Video ({video_status})", callback_data="set_method_video"),
            ]
        ]
    )
    await message.reply_text(f"Your Current Upload Method: {current_method.capitalize()}", reply_markup=buttons)


@Client.on_message(filters.command("anime") & filters.private)
async def search_anime(client, message):
    from helper.database import create_search_session

    await _track_user(client, message.from_user.id)

    try:
        query = message.text.split(None, 1)[1].strip()
    except IndexError:
        await message.reply_text("Usage: <code>/anime anime_name</code>")
        return
    if not query:
        await message.reply_text("Usage: <code>/anime anime_name</code>")
        return

    search_url = f"https://animepahe.ru/api?m=search&q={urllib.parse.quote_plus(query)}"
    try:
        response = safe_json(await asyncio.to_thread(safe_request, "GET", search_url))
    except UpstreamRequestError as exc:
        await log_to_channel(client, str(exc), context="search_anime")
        await message.reply_text("AnimePahe is not responding right now. Please try again later.")
        return

    results = response.get("data") or []
    if not results:
        await message.reply_text("Anime not found.")
        return

    session_results = [
        {"session": anime["session"], "title": anime.get("title", "Unknown")} for anime in results
    ]

    try:
        token = await asyncio.to_thread(
            create_search_session, message.from_user.id, message.chat.id, query, session_results
        )
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="search_anime:create_session")
        await message.reply_text("Could not start a search session right now. Please try again later.")
        return

    anime_buttons = [
        [InlineKeyboardButton(item["title"], callback_data=f"an:{token}:{idx}")]
        for idx, item in enumerate(session_results)
    ]
    reply_markup = InlineKeyboardMarkup(anime_buttons)
    gif_url = "https://telegra.ph/file/33067bb12f7165f8654f9.mp4"
    await message.reply_video(
        video=gif_url,
        caption=f"Search Result For <code>{html.escape(query)}</code>",
        reply_markup=reply_markup,
        quote=True,
    )


@Client.on_message(filters.command("users") & filters.private & filters.user(ADMIN))
async def get_users(client, message):
    msg = await client.send_message(chat_id=message.chat.id, text=WAIT_MSG)
    try:
        users = await asyncio.to_thread(full_userbase)
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="get_users")
        await msg.edit("Could not load the user count right now.")
        return
    await msg.edit(f"{len(users)} users are using this bot")


@Client.on_message(filters.private & filters.command("broadcast") & filters.user(ADMIN))
async def send_text(client, message):
    if not message.reply_to_message:
        msg = await message.reply(REPLY_ERROR)
        await asyncio.sleep(8)
        await msg.delete()
        return

    try:
        user_ids = await asyncio.to_thread(full_userbase)
    except Exception as exc:  # noqa: BLE001
        await log_to_channel(client, str(exc), context="broadcast:load_userbase")
        await message.reply("Could not load the user list right now. Please try again later.")
        return

    broadcast_msg = message.reply_to_message
    total = successful = blocked = deleted = unsuccessful = 0

    pls_wait = await message.reply("<i>Broadcasting Message.. This will take some time</i>")
    for chat_id in user_ids:
        total += 1
        try:
            await broadcast_msg.copy(chat_id)
            successful += 1
        except pyrogram.errors.FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                await broadcast_msg.copy(chat_id)
                successful += 1
            except Exception as exc:  # noqa: BLE001
                unsuccessful += 1
                log.warning("Broadcast retry failed for %s: %s", chat_id, exc)
        except pyrogram.errors.UserIsBlocked:
            await asyncio.to_thread(del_user, chat_id)
            blocked += 1
        except pyrogram.errors.InputUserDeactivated:
            await asyncio.to_thread(del_user, chat_id)
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            unsuccessful += 1
            log.warning("Broadcast failed for %s: %s", chat_id, exc)

    status = (
        "<b><u>Broadcast Completed</u>\n\n"
        f"Total Users: <code>{total}</code>\n"
        f"Successful: <code>{successful}</code>\n"
        f"Blocked Users: <code>{blocked}</code>\n"
        f"Deleted Accounts: <code>{deleted}</code>\n"
        f"Unsuccessful: <code>{unsuccessful}</code></b>"
    )
    await pls_wait.edit(status)


@Client.on_message(filters.command("queue") & filters.private)
async def view_queue(client, message):
    summary = download_queue.active_summary()
    if not summary:
        await message.reply_text("No active downloads.")
        return

    queue_text = "Active Downloads:\n"
    for i, (username, task_count) in enumerate(summary, start=1):
        queue_text += f"{i}. @{username} (Active Task = {task_count})\n"
    await message.reply_text(queue_text, disable_web_page_preview=True)


@Client.on_message(filters.command("latest") & filters.private)
async def send_latest_anime(client, message):
    api_url = "https://animepahe.ru/api?m=airing&page=1"
    try:
        response = safe_json(await asyncio.to_thread(safe_request, "GET", api_url))
    except UpstreamRequestError as exc:
        await log_to_channel(client, str(exc), context="send_latest_anime")
        await message.reply_text("AnimePahe is not responding right now. Please try again later.")
        return

    anime_list = response.get("data") or []
    if not anime_list:
        await message.reply_text("No latest anime available at the moment.")
        return

    latest_anime_text = "<b>📺 Latest Airing Anime:</b>\n\n"
    for idx, anime in enumerate(anime_list, start=1):
        title = html.escape(str(anime.get("anime_title", "Unknown")))
        anime_session = anime.get("anime_session", "")
        episode = html.escape(str(anime.get("episode", "?")))
        link = f"https://animepahe.ru/anime/{urllib.parse.quote(str(anime_session))}"
        latest_anime_text += f"<b>{idx}) <a href='{link}'>{title}</a> [E{episode}]</b>\n"

    await message.reply_text(latest_anime_text, disable_web_page_preview=True)


@Client.on_message(filters.command("airing") & filters.private)
async def send_airing_anime(client, message):
    api_url = "https://animepahe.ru/anime/airing"
    try:
        response = await asyncio.to_thread(safe_request, "GET", api_url)
    except UpstreamRequestError as exc:
        await log_to_channel(client, str(exc), context="send_airing_anime")
        await message.reply_text("AnimePahe is not responding right now. Please try again later.")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    anime_list = soup.select(".index-wrapper .index a")
    if not anime_list:
        await message.reply_text("No airing anime available at the moment.")
        return

    airing_anime_text = "<b>🎬 Currently Airing Anime:</b>\n\n"
    for idx, anime in enumerate(anime_list, start=1):
        title = html.escape(anime.get("title", "Unknown Title"))
        airing_anime_text += f"<b>{idx}) {title}</b>\n"

    await message.reply_text(airing_anime_text, disable_web_page_preview=True)
