#..........This Bot Made By [RAHAT](https://t.me/r4h4t_69)..........#
#..........Anyone Can Modify This As He Likes..........#
#..........Just one requests do not remove my credit..........#

"""Small parsing helpers shared across plugins."""

import re


def parse_episode_number(label):
    """Best-effort numeric value for an episode label, for sorting only.

    Handles plain integers ("12"), decimals ("12.5"), and returns None for
    non-numeric labels ("OVA", "Special 1", "Recap") instead of raising --
    callers must never assume every episode label is `int(episode)`.
    """
    if label is None:
        return None
    match = re.search(r"\d+(?:\.\d+)?", str(label))
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None
