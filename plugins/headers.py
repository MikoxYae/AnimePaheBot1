#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Shared HTTP session + a small wrapper adding timeouts, status
validation, and bounded retries to every outbound request.
"""

import time

import requests

from config import REQUEST_TIMEOUT_SECONDS
from helper.logger import log

session = requests.Session()
session.headers.update({
    'authority': 'animepahe.ru',
    'accept': 'application/json, text/javascript, */*; q=0.01',
    'accept-language': 'en-US,en;q=0.9',
    'cookie': '__ddg2_=;',
    'dnt': '1',
    'sec-ch-ua': '"Not A(Brand";v="99", "Microsoft Edge";v="121", "Chromium";v="121"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'x-requested-with': 'XMLHttpRequest',
    'referer': 'https://animepahe.ru',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
})

MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 1.5
RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class UpstreamRequestError(RuntimeError):
    """Raised when a request to an external site fails after retries."""


def safe_request(method: str, url: str, retries: int = MAX_RETRIES, timeout=None, **kwargs):
    """`requests` wrapper with a timeout, status validation, and bounded
    retries for timeouts/connection errors/5xx responses.

    Raises `UpstreamRequestError` (never a raw, unhandled exception type)
    so callers can present a friendly message instead of crashing.
    """
    timeout = timeout or REQUEST_TIMEOUT_SECONDS
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < retries:
                last_exc = UpstreamRequestError(
                    f"{url} returned {response.status_code}"
                )
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            response.raise_for_status()
            return response
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_exc = exc
            log.warning("Request to %s failed (attempt %d/%d): %s", url, attempt, retries, exc)
            if attempt < retries:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
        except requests.exceptions.HTTPError as exc:
            raise UpstreamRequestError(f"{url} returned an error: {exc}") from exc
    raise UpstreamRequestError(f"{url} failed after {retries} attempts: {last_exc}")


def safe_json(response):
    """Parse a response as JSON, raising `UpstreamRequestError` on malformed
    JSON instead of letting a raw `ValueError` escape."""
    try:
        return response.json()
    except ValueError as exc:
        raise UpstreamRequestError(f"Malformed JSON response from {response.url}") from exc
