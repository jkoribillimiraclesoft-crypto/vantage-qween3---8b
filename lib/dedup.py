"""Deduplicate raw items against what's already stored and against each other."""

import difflib
import re


def _normalize(title):
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def dedup(raw_items, existing_urls, existing_titles, similarity_threshold=0.85):
    """Returns a deduplicated list. Drops items whose URL is already stored,
    or whose title is highly similar to an already-stored title or to an
    item already kept earlier in this same batch."""
    kept = []
    kept_norms = []
    existing_norms = [_normalize(t) for t in existing_titles]

    for item in raw_items:
        if not item.get("title") or not item.get("url"):
            continue
        if item["url"] in existing_urls:
            continue
        norm = _normalize(item["title"])
        if not norm:
            continue
        is_dupe = False
        for other in existing_norms + kept_norms:
            if difflib.SequenceMatcher(None, norm, other).ratio() >= similarity_threshold:
                is_dupe = True
                break
        if is_dupe:
            continue
        kept.append(item)
        kept_norms.append(norm)

    return kept
