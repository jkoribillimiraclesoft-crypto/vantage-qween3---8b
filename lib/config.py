"""Shared configuration: priority tiers, scoring weights, default profile, and
the source registry. Adding a new source means adding one entry to SOURCES —
nothing else in the app needs to change (fulfills the 'modular sources' requirement).
"""

PRIORITY = {
    "must": {"label": "Must Learn", "emoji": "🔴", "color": "#45D6C6"},
    "important": {"label": "Important", "emoji": "🟠", "color": "#E8A23D"},
    "explore": {"label": "Worth Exploring", "emoji": "🟡", "color": "#D9C558"},
    "watch": {"label": "Watch", "emoji": "⚪", "color": "#5B6774"},
}
GCP_BLUE = "#4285F4"
GCP_GREEN = "#34A853"

DEFAULT_WEIGHTS = {"gcp": 25, "de": 25, "ai": 20, "career": 15, "adoption": 10, "future": 5}
WEIGHT_LABELS = {
    "gcp": "GCP Relevance", "de": "Data Engineering Relevance", "ai": "AI Relevance",
    "career": "Career Impact", "adoption": "Industry Adoption", "future": "Future Potential",
}

DEFAULT_PROFILE = dict(
    role="GCP Data Engineer",
    expertise="Data Engineering, Google Cloud Platform, Data pipelines, Data processing, Data platforms",
    ai_experience="Has experience working with AI models; interested in applying AI to data engineering",
)


def priority_for(score):
    if score >= 85:
        return "must"
    elif score >= 70:
        return "important"
    elif score >= 50:
        return "explore"
    return "watch"


# ---------------------------------------------------------------- SOURCE REGISTRY
#
# Each entry describes how to fetch raw candidate items. "kind" tells sources.py
# which fetcher function to use. RSS sources use best-known public feed URLs for
# each vendor; if a vendor changes their feed URL, that one source will simply
# return 0 items (logged, not fatal) until the "url" below is updated — nothing
# else breaks. GitHub, arXiv, and Hacker News use stable, documented public APIs.

SOURCES = [
    # --- Stable public APIs (no RSS URL to go stale) ---
    dict(name="arXiv", kind="arxiv",
         query="cat:cs.AI AND (abs:agent OR abs:retrieval OR abs:data engineering OR abs:LLM)",
         max_results=8),
    dict(name="Hacker News", kind="hackernews",
         keywords=["ai", "llm", "agent", "gcp", "bigquery", "data engineering", "rag", "mcp",
                    "vertex", "vector database", "dbt", "airflow"],
         max_results=10),
    dict(name="GitHub", kind="github",
         topics=["llm-agents", "data-engineering", "mcp", "rag"],
         max_results=8),

    # --- Vendor blog RSS feeds (best-effort; failures are handled gracefully) ---
    dict(name="Google Cloud Blog", kind="rss", url="https://cloud.google.com/blog/rss/", max_results=8),
    dict(name="Google Cloud Release Notes", kind="rss", url="https://cloud.google.com/feeds/gcp-release-notes.xml", max_results=8),
    dict(name="dbt Labs Blog", kind="rss", url="https://docs.getdbt.com/blog/rss.xml", max_results=6),
    dict(name="LangChain Blog", kind="rss", url="https://blog.langchain.dev/rss/", max_results=6),
    dict(name="Snowflake Blog", kind="rss", url="https://www.snowflake.com/blog/feed/", max_results=6),
    dict(name="Meta AI Blog", kind="rss", url="https://ai.meta.com/blog/rss/", max_results=6),

    # To add a new source: append another dict here with kind="rss" and a feed url,
    # or add a new kind + fetcher function in sources.py for a non-RSS API.
]
