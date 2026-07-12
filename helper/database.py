#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""MongoDB-backed persistence.

In addition to the original thumbnail/caption/upload-method/user
collections, this module holds TTL-backed, token-keyed session state for:

- search_sessions   -- results of an /anime search (replaces the old
                        in-memory `user_queries` dict).
- episode_sessions   -- the episode list for one anime detail view
                        (replaces the old in-memory `episode_data` dict).
- download_tokens    -- short-lived mapping from a short callback token to
                        the full download request (replaces embedding full
                        AnimePahe/Kwik URLs directly in callback_data).

Every session record carries `created_at` and a Mongo TTL index expires it
automatically after `SESSION_TTL_SECONDS` -- old buttons naturally stop
resolving instead of leaking memory or growing forever.
"""

import secrets
from datetime import datetime, timezone

from pymongo import ASCENDING, MongoClient
from pymongo.errors import PyMongoError

from config import DB_NAME, MONGO_URL, SESSION_TTL_SECONDS

client_db = MongoClient(MONGO_URL, serverSelectionTimeoutMS=10_000)
db = client_db[DB_NAME]

thumbnails_col = db["thumbnails"]
captions_col = db["captions"]
upload_method_col = db["upload_methods"]
user_data_col = db["users"]

search_sessions_col = db["search_sessions"]
episode_sessions_col = db["episode_sessions"]
download_tokens_col = db["download_tokens"]


class DatabaseError(RuntimeError):
    """Raised when a MongoDB operation fails, so handlers can show a
    friendly message instead of crashing."""


def verify_connection() -> None:
    """Fail fast at startup if MongoDB is unreachable."""
    try:
        client_db.admin.command("ping")
    except PyMongoError as exc:
        raise DatabaseError(f"Could not reach MongoDB: {exc}") from exc


def ensure_indexes() -> None:
    """Create required indexes. Safe to call on every startup."""
    try:
        for col in (search_sessions_col, episode_sessions_col, download_tokens_col):
            col.create_index(
                [("created_at", ASCENDING)],
                expireAfterSeconds=SESSION_TTL_SECONDS,
                name="ttl_created_at",
            )
        user_data_col.create_index("_id", name="user_id_idx")
    except PyMongoError as exc:
        raise DatabaseError(f"Could not create MongoDB indexes: {exc}") from exc


def _new_token() -> str:
    return secrets.token_urlsafe(6)


def _insert_session(col, payload: dict) -> str:
    """Insert a session document with a fresh unique short token as _id."""
    for _ in range(5):
        token = _new_token()
        payload_with_id = {
            "_id": token,
            "created_at": datetime.now(timezone.utc),
            **payload,
        }
        try:
            col.insert_one(payload_with_id)
            return token
        except PyMongoError as exc:
            if "duplicate key" in str(exc).lower():
                continue
            raise DatabaseError(f"Could not save session: {exc}") from exc
    raise DatabaseError("Could not allocate a unique session token")


# --- Thumbnails -----------------------------------------------------------

def save_thumbnail(user_id, file_id):
    thumbnails_col.update_one(
        {"user_id": user_id},
        {"$set": {"thumbnail": file_id}},
        upsert=True,
    )


def get_thumbnail(user_id):
    record = thumbnails_col.find_one({"user_id": user_id})
    return record["thumbnail"] if record else None


def delete_thumbnail(user_id):
    thumbnails_col.delete_one({"user_id": user_id})


# --- Captions ---------------------------------------------------------------

def save_caption(user_id, caption):
    captions_col.update_one(
        {"user_id": user_id},
        {"$set": {"caption": caption}},
        upsert=True,
    )


def get_caption(user_id):
    record = captions_col.find_one({"user_id": user_id})
    return record["caption"] if record else None


def delete_caption(user_id):
    captions_col.delete_one({"user_id": user_id})


# --- Upload method -----------------------------------------------------------

def save_upload_method(user_id, method):
    upload_method_col.update_one(
        {"user_id": user_id},
        {"$set": {"method": method}},
        upsert=True,
    )


def get_upload_method(user_id):
    record = upload_method_col.find_one({"user_id": user_id})
    return record["method"] if record else "document"  # Default is 'document'


# --- Users -----------------------------------------------------------------

def present_user(user_id: int) -> bool:
    return bool(user_data_col.find_one({"_id": user_id}))


def add_user(user_id: int):
    user_data_col.update_one({"_id": user_id}, {"$setOnInsert": {"_id": user_id}}, upsert=True)


def full_userbase():
    return [doc["_id"] for doc in user_data_col.find({}, {"_id": 1})]


def del_user(user_id: int):
    user_data_col.delete_one({"_id": user_id})


# --- Search sessions (replaces the old in-memory user_queries dict) --------

def create_search_session(user_id, chat_id, query: str, results: list) -> str:
    """`results` is a list of {"session": str, "title": str} dicts."""
    return _insert_session(
        search_sessions_col,
        {"user_id": user_id, "chat_id": chat_id, "query": query, "results": results},
    )


def get_search_session(token: str):
    return search_sessions_col.find_one({"_id": token})


# --- Episode sessions (replaces the old in-memory episode_data dict) -------

def create_episode_session(user_id, chat_id, anime_session, title, poster, episodes: list) -> str:
    """`episodes` is a list of {"label": str, "session": str} dicts, in
    display order (index into this list is what callback_data references)."""
    return _insert_session(
        episode_sessions_col,
        {
            "user_id": user_id,
            "chat_id": chat_id,
            "anime_session": anime_session,
            "title": title,
            "poster": poster,
            "episodes": episodes,
            "page": 1,
            "last_page": 1,
        },
    )


def get_episode_session(token: str):
    return episode_sessions_col.find_one({"_id": token})


def update_episode_session(token: str, **fields):
    if not fields:
        return
    episode_sessions_col.update_one({"_id": token}, {"$set": fields})


# --- Download tokens (replaces embedding full URLs in callback_data) ------

def create_download_token(user_id, chat_id, anime_title, episode_label, quality_label, source_url) -> str:
    return _insert_session(
        download_tokens_col,
        {
            "user_id": user_id,
            "chat_id": chat_id,
            "anime_title": anime_title,
            "episode_label": episode_label,
            "quality_label": quality_label,
            "source_url": source_url,
        },
    )


def get_download_token(token: str):
    return download_tokens_col.find_one({"_id": token})
