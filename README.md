# AnimePaheBot

A Telegram bot (built with Pyrogram) for searching AnimePahe and downloading
episodes to Telegram.

## What changed in this fix

- **Security**: removed hardcoded bot token / API hash / MongoDB URI from
  `config.py`. All configuration now comes from environment variables and
  is validated at startup (missing/invalid values fail fast with a clear
  error instead of crashing later).
- **Stability**: fixed the invalid `pyroutils.MIN_CHANNEL_ID` startup hack,
  added proper async startup/shutdown, added timeouts and bounded retries
  on every outbound HTTP request, replaced the bare `except: pass` in
  `/broadcast`, fixed the malformed `/users` handler and `WAIT_MSG` string.
- **Correctness**: fixed the `/start` Help button (it now uses
  `edit_caption()` since `/start` sends a photo, plus a working Back
  button), removed the buggy `has_spoiler`/`thumb=None` overrides that
  broke custom thumbnails.
- **Session handling**: search results, episode lists, and download links
  are now stored in MongoDB behind short opaque tokens (`an:<token>:<idx>`,
  `ep:<token>:<idx>`, `dl:<token>`) instead of embedded in `callback_data`
  or kept in process memory. This fixes `BUTTON_DATA_INVALID` errors,
  removes the risk of one user's button resolving against another user's
  (or their own newer) search, and makes old buttons expire safely after
  `SESSION_TTL_SECONDS` (via a MongoDB TTL index) instead of accumulating
  forever.
- **Downloads**: real bounded download queue (`plugins/queue.py`) with a
  configurable concurrency limit, per-user fairness, request de-duplication,
  and a max queue size -- handlers enqueue and return immediately instead of
  blocking. Downloads now enforce a max file size (checked while
  streaming, not just via `Content-Length`), a minimum free-disk check,
  safe filenames with path-traversal prevention, and always clean up
  partial files.
- **Uploads**: upload success is only reported after Telegram actually
  confirms the message was sent -- failures raise a clear error instead of
  being silently swallowed.
- **ffprobe**: detected safely; if missing, the bot falls back to
  `duration/width/height = 0` instead of crashing, and logs a warning.
- **Parsing**: episode numbers like `"12.5"`, `"OVA"`, `"Special 1"` are
  parsed defensively for sorting and never crash the handler.
- **Encoding**: all user-controlled text placed into HTML-mode Telegram
  messages is now escaped with `html.escape()`; search queries used in
  AnimePahe URLs are now URL-encoded with `urllib.parse.quote_plus`.

## Required environment variables

See `.env.example` for the full list with comments. At minimum you need:

| Variable | Description |
|---|---|
| `API_ID` | Telegram API ID from https://my.telegram.org |
| `API_HASH` | Telegram API hash from https://my.telegram.org |
| `BOT_TOKEN` | Bot token from @BotFather |
| `MONGO_DB_URI` | MongoDB connection string (Atlas or self-hosted) |
| `LOG_CHANNEL` | Channel ID (or `@username`) the bot can post logs/uploads to |
| `OWNER_ID` | Your numeric Telegram user ID |

Never commit a real `.env` file -- it's excluded via `.gitignore`.

## Installing on a fresh Ubuntu VPS

```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip ffmpeg git

sudo useradd -r -m -d /opt/animepahebot -s /usr/sbin/nologin animepahebot
sudo -u animepahebot git clone https://github.com/MikoxYae/AnimePaheBot1.git /opt/animepahebot

cd /opt/animepahebot
sudo -u animepahebot python3 -m venv venv
sudo -u animepahebot ./venv/bin/pip install -U pip
sudo -u animepahebot ./venv/bin/pip install -r requirements.txt

sudo cp .env.example .env
sudo nano .env   # fill in real values
sudo chown animepahebot:animepahebot .env
sudo chmod 600 .env
```

### Start the bot directly (for testing)

```bash
sudo -u animepahebot ./venv/bin/python3 bot.py
```

### Run as a systemd service (recommended for production)

```bash
sudo cp deploy/animepahebot.service /etc/systemd/system/animepahebot.service
sudo systemctl daemon-reload
sudo systemctl enable --now animepahebot
sudo systemctl status animepahebot
journalctl -u animepahebot -f
```

## ffmpeg / ffprobe

Episode duration/width/height metadata (used for nicer video previews on
upload) requires the `ffmpeg`/`ffprobe` OS package, installed above via
`apt install ffmpeg`. If it's missing, the bot still works -- it just skips
that metadata and logs a warning.

## Known limitations

- Per-user download concurrency is approximate: a user at their limit is
  requeued with a short delay rather than perfectly scheduled, so heavy
  multi-user load can see minor ordering jitter. Overall concurrency
  (`MAX_CONCURRENT_DOWNLOADS`) is still strictly enforced.
- Kwik/AnimePahe are third-party sites outside this project's control --
  if they change their page structure, extraction can start failing again.
  The bot now detects challenge/CAPTCHA/HTML-error pages and reports a
  clear error instead of crashing, but it cannot bypass an active
  CAPTCHA.
- The bot only supports a single running `Client` instance; it is not
  designed for horizontal scaling across multiple processes sharing one
  bot token.
