#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Extract the final direct-download link from a Kwik link.

Kwik's obfuscated redirect script changes shape over time; this module
validates every extracted field before using it and raises a controlled
`ExtractionError` instead of crashing on missing regex groups.
"""

import re

import requests

from config import REQUEST_TIMEOUT_SECONDS

s = requests.Session()


class ExtractionError(RuntimeError):
    """Raised when the Kwik page cannot be parsed into a direct link."""


def step_2(data: str, separator: int, base: int = 10) -> str:
    mapped_range = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
    numbers = mapped_range[0:base]
    total = 0
    for index, value in enumerate(data[::-1]):
        total += int(value if value.isdigit() else 0) * (separator ** index)
    result = ""
    while total > 0:
        result = numbers[int(total % base)] + result
        total = (total - (total % base)) // base
    return result or "0"


def step_1(data: str, key: str, load: str, separator: str):
    payload = ""
    i = 0
    separator = int(separator)
    load = int(load)
    while i < len(data):
        chunk = ""
        while data[i] != key[separator]:
            chunk += data[i]
            i += 1
        for index, value in enumerate(key):
            chunk = chunk.replace(value, str(index))
        payload += chr(int(step_2(chunk, separator, 10)) - load)
        i += 1

    matches = re.findall(
        r'action="([^"]+)" method="POST"><input type="hidden" name="_token"\s+value="([^"]+)',
        payload,
    )
    if not matches:
        raise ExtractionError("Kwik page layout has changed; could not find the download form.")
    return matches[0]


def get_dl_link(link: str) -> str:
    try:
        resp = s.get(link, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise ExtractionError(f"Could not reach Kwik: {exc}") from exc

    lowered = resp.text.lower()
    if "checking your browser" in lowered or "cloudflare" in lowered or "captcha" in lowered:
        raise ExtractionError("Kwik returned a challenge/CAPTCHA page instead of the video.")

    matches = re.findall(r'\("(\S+)",\d+,"(\S+)",(\d+),(\d+)', resp.text)
    if not matches:
        raise ExtractionError("Could not find the obfuscated script parameters on the Kwik page.")

    data, key, load, separator = matches[0]
    try:
        url, token = step_1(data=data, key=key, load=load, separator=separator)
    except IndexError as exc:
        raise ExtractionError("Unexpected Kwik page structure.") from exc

    try:
        resp = s.post(
            url=url,
            data={"_token": token},
            headers={"referer": link},
            allow_redirects=False,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.RequestException as exc:
        raise ExtractionError(f"Could not reach Kwik's download endpoint: {exc}") from exc

    location = resp.headers.get("location")
    if not location:
        raise ExtractionError("Kwik did not return a redirect to the direct download link.")
    return location
