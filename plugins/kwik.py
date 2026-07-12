#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Extract the kwik.si link from an AnimePahe episode download page."""

import re

import requests
from bs4 import BeautifulSoup

from config import REQUEST_TIMEOUT_SECONDS

KWIK_LINK_RE = re.compile(r"https://kwik\.si/f/[\w\d]+")


class KwikLinkNotFoundError(RuntimeError):
    """Raised when no kwik.si link could be located on the page."""


def extract_kwik_link(url: str) -> str:
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise KwikLinkNotFoundError(f"Could not load the download page: {exc}") from exc

    soup = BeautifulSoup(response.text, "html.parser")
    for script in soup.find_all("script", type="text/javascript"):
        match = KWIK_LINK_RE.search(script.text or "")
        if match:
            return match.group(0)

    raise KwikLinkNotFoundError("No kwik.si link found on the download page.")
