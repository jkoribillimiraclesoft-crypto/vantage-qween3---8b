"""Fetch raw candidate items from each configured source.

Every fetcher returns (items, error) where items is a list of dicts:
    {title, url, source, published, raw_summary}
and error is None on success or a short string describing what went wrong.
A failed source never raises — the pipeline logs it and moves on, per the
'handle API failures gracefully' requirement.
"""

import datetime
import xml.etree.ElementTree as ET

import requests

try:
    import feedparser
except ImportError:
    feedparser = None

TIMEOUT = 12
HEADERS = {"User-Agent": "VANTAGE-AI-Intelligence/1.0 (personal research tool)"}


def _safe_date(struct_time):
    if not struct_time:
        return datetime.date.today().isoformat()
    try:
        return datetime.date(*struct_time[:3]).isoformat()
    except Exception:
        return datetime.date.today().isoformat()


def fetch_rss(source_cfg):
    if feedparser is None:
        return [], "feedparser not installed"
    try:
        resp = requests.get(source_cfg["url"], headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            return [], f"could not parse feed ({parsed.bozo_exception})"
        items = []
        for entry in parsed.entries[: source_cfg.get("max_results", 8)]:
            items.append(dict(
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                source=source_cfg["name"],
                published=_safe_date(entry.get("published_parsed") or entry.get("updated_parsed")),
                raw_summary=(entry.get("summary", "") or "")[:600],
            ))
        return items, None
    except Exception as e:
        return [], str(e)


def fetch_arxiv(source_cfg):
    try:
        params = {
            "search_query": source_cfg["query"],
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": source_cfg.get("max_results", 8),
        }
        resp = requests.get("http://export.arxiv.org/api/query", params=params, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(resp.content)
        items = []
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")
            summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip().replace("\n", " ")
            link = entry.findtext("atom:id", default="", namespaces=ns)
            published = entry.findtext("atom:published", default="", namespaces=ns)[:10]
            items.append(dict(title=title, url=link, source="arXiv",
                               published=published or datetime.date.today().isoformat(),
                               raw_summary=summary[:600]))
        return items, None
    except Exception as e:
        return [], str(e)


def fetch_hackernews(source_cfg):
    try:
        top_ids = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json",
                                headers=HEADERS, timeout=TIMEOUT).json()
        keywords = [k.lower() for k in source_cfg.get("keywords", [])]
        items = []
        # Scan more IDs than we need since most stories won't match keywords.
        for story_id in top_ids[:150]:
            if len(items) >= source_cfg.get("max_results", 10):
                break
            try:
                story = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                                      headers=HEADERS, timeout=TIMEOUT).json()
            except Exception:
                continue
            if not story or "title" not in story:
                continue
            title_lower = story["title"].lower()
            if not any(k in title_lower for k in keywords):
                continue
            items.append(dict(
                title=story["title"],
                url=story.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
                source="Hacker News",
                published=datetime.date.fromtimestamp(story.get("time", 0)).isoformat() if story.get("time") else datetime.date.today().isoformat(),
                raw_summary=f"Hacker News discussion, {story.get('score', 0)} points, {story.get('descendants', 0)} comments.",
            ))
        return items, None
    except Exception as e:
        return [], str(e)


def fetch_github(source_cfg):
    # GitHub's search API rejects queries that are only logical operators
    # (topic:a OR topic:b) with no free-text term, so we query per-topic and
    # merge, deduping by repo id along the way.
    topics = source_cfg.get("topics", [])
    per_topic = max(1, source_cfg.get("max_results", 8) // max(1, len(topics)))
    seen_ids = set()
    items = []
    errors = []
    for topic in topics:
        try:
            params = {"q": f"topic:{topic}", "sort": "updated", "order": "desc", "per_page": per_topic}
            resp = requests.get("https://api.github.com/search/repositories", params=params,
                                 headers={**HEADERS, "Accept": "application/vnd.github+json"}, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            for repo in data.get("items", []):
                if repo["id"] in seen_ids:
                    continue
                seen_ids.add(repo["id"])
                items.append(dict(
                    title=f"{repo['full_name']}: {repo.get('description') or 'no description'}",
                    url=repo["html_url"],
                    source="GitHub",
                    published=(repo.get("pushed_at") or repo.get("updated_at") or "")[:10] or datetime.date.today().isoformat(),
                    raw_summary=f"{repo.get('stargazers_count', 0)} stars, language: {repo.get('language') or 'n/a'}. {repo.get('description') or ''}"[:600],
                ))
        except Exception as e:
            errors.append(f"topic:{topic} -> {e}")
    error = "; ".join(errors) if errors and not items else None
    return items[: source_cfg.get("max_results", 8)], error


FETCHERS = {
    "rss": fetch_rss,
    "arxiv": fetch_arxiv,
    "hackernews": fetch_hackernews,
    "github": fetch_github,
}


def fetch_all(sources):
    """Fetch every configured source. Returns (all_items, status) where status
    is a list of {source, count, error} for surfacing in the UI."""
    all_items = []
    status = []
    for cfg in sources:
        fetcher = FETCHERS.get(cfg["kind"])
        if fetcher is None:
            status.append(dict(source=cfg["name"], count=0, error=f"unknown source kind '{cfg['kind']}'"))
            continue
        items, error = fetcher(cfg)
        all_items.extend(items)
        status.append(dict(source=cfg["name"], count=len(items), error=error))
    return all_items, status
