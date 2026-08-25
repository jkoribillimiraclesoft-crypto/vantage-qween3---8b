"""Enrich raw items with AI-generated analysis, scored against the user's profile.

The Streamlit/GitHub deployment uses a hosted Qwen3 8B endpoint through
Hugging Face Inference Providers. The endpoint is OpenAI-compatible, so the
application only needs a Hugging Face token stored in Streamlit Secrets.
"""

import json
import os

import requests

DEFAULT_PROVIDER = "huggingface"
DEFAULT_MODEL = "Qwen/Qwen3-8B"
DEFAULT_HF_BASE_URL = "https://router.huggingface.co/v1"
BATCH_SIZE = 8

SCHEMA_INSTRUCTIONS = """For EACH item, return an object with exactly these fields:
{
  "index": <the item's index as given>,
  "tier": <1, 2, 3, or 4 — 1 = directly GCP/BigQuery/VertexAI/DataEngineering critical,
           2 = AI agents/RAG/MCP/LLM apps/data+AI, 3 = broader dev ecosystem (open models,
           LangGraph, MLOps, AI infra), 4 = general AI news with little data-engineering relevance>,
  "category": "<short category label, e.g. 'BigQuery', 'AI Agents', 'MCP', 'Data Quality + AI'>",
  "summary": "<3-5 sentence neutral summary of the actual content>",
  "whats_new": "<what specifically changed or was introduced>",
  "why_matters": "<practical importance and impact, grounded in the content, not generic>",
  "why_learn": "<personalized explanation connecting this SPECIFICALLY to GCP + Data Engineering + AI
                for this user's profile. Never generic like 'AI is growing fast'. If it has no real
                data-engineering angle, say so honestly rather than inventing a connection.>",
  "what_to_learn": ["<specific skill/technology 1>", "<...>"],
  "gcp_use": "Yes" | "Potentially" | "No",
  "gcp_use_case": "<if Yes/Potentially, one concrete GCP data-engineering use case; if No, say why not>",
  "is_gcp": true | false,
  "is_de": true | false,
  "scores": {
    "gcp": <0-100 GCP relevance>,
    "de": <0-100 Data Engineering relevance>,
    "ai": <0-100 general AI relevance>,
    "career": <0-100 career impact for this profile>,
    "adoption": <0-100 current industry adoption>,
    "future": <0-100 future potential>
  }
}
Be honest and specific — if an item genuinely has low GCP/data-engineering relevance, score it low
rather than inflating relevance to seem more useful. Return ONLY a JSON array of these objects,
no markdown fences, no commentary, and no reasoning before or after the JSON."""


def _secret(name, default=None):
    """Read configuration from environment first, then Streamlit secrets."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st
        value = st.secrets.get(name)
        return value if value else default
    except Exception:
        return default


def get_ai_config():
    """Return the active hosted AI provider configuration."""
    provider = _secret("AI_PROVIDER", DEFAULT_PROVIDER).lower().strip()
    model = _secret("AI_MODEL", DEFAULT_MODEL).strip()
    base_url = _secret("HF_BASE_URL", DEFAULT_HF_BASE_URL).rstrip("/")
    return {"provider": provider, "model": model, "base_url": base_url}


def get_api_key():
    """Return whether the configured hosted AI backend has credentials."""
    cfg = get_ai_config()
    if cfg["provider"] == "huggingface":
        return bool(_secret("HF_TOKEN") or _secret("HUGGINGFACE_API_KEY"))
    return False


def ai_backend_label():
    cfg = get_ai_config()
    if cfg["provider"] == "huggingface":
        return f"Hugging Face / {cfg['model']}"
    return cfg["provider"]


def _call_huggingface(prompt):
    """Call the Hugging Face OpenAI-compatible router."""
    cfg = get_ai_config()
    token = _secret("HF_TOKEN") or _secret("HUGGINGFACE_API_KEY")
    if not token:
        raise RuntimeError(
            "Hugging Face credentials are missing. Add HF_TOKEN to Streamlit Secrets "
            "with a token that has Inference Providers permission."
        )

    url = f"{cfg['base_url']}/chat/completions"
    payload = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 4000,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=180)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach Hugging Face Inference Router: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text[:1000]
        raise RuntimeError(
            f"Hugging Face API returned HTTP {response.status_code}. "
            f"Check HF_TOKEN, model availability, and provider access. Details: {detail}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError("Hugging Face returned a non-JSON response") from exc

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"Hugging Face returned no choices: {data}")

    message = choices[0].get("message") or {}
    text = (message.get("content") or "").strip()
    if not text:
        # Some OpenAI-compatible providers may expose output in a different field.
        text = (choices[0].get("text") or "").strip()
    if not text:
        raise RuntimeError("Hugging Face returned an empty model response")
    return text


def _call_ai(prompt):
    cfg = get_ai_config()
    if cfg["provider"] == "huggingface":
        return _call_huggingface(prompt)
    raise RuntimeError(
        f"Unsupported AI_PROVIDER '{cfg['provider']}'. "
        "Set AI_PROVIDER=huggingface for the hosted Qwen3 8B setup."
    )

def _chunk(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _parse_json_array(text):
    """Parse model output while tolerating fences or surrounding prose."""
    text = (text or "").strip()
    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as original_error:
        # Find a JSON array even if the provider adds a short preamble/postscript.
        start = text.find("[")
        if start < 0:
            raise original_error
        decoder = json.JSONDecoder()
        try:
            parsed, _ = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            end = text.rfind("]")
            if end <= start:
                raise original_error
            parsed = json.loads(text[start:end + 1])

    if not isinstance(parsed, list):
        raise ValueError("AI response was valid JSON but not a JSON array")
    return parsed


def enrich_batch(raw_items, profile):
    """raw_items: list of dicts with title, url, source, published, raw_summary.
    Returns (enriched_items, errors) where enriched_items merge the analysis
    fields back onto the original raw metadata.
    """
    if not raw_items:
        return [], []

    enriched = []
    errors = []

    for chunk in _chunk(raw_items, BATCH_SIZE):
        payload = [dict(index=i, title=it["title"], source=it["source"],
                        published=it["published"], raw_summary=it["raw_summary"])
                   for i, it in enumerate(chunk)]
        prompt = f"""You are a personal AI Career Intelligence Assistant and GCP Data Engineering Advisor.
Analyze each raw item below for this specific user profile:

Role: {profile['role']}
Primary expertise: {profile['expertise']}
AI experience: {profile['ai_experience']}

RAW ITEMS:
{json.dumps(payload, ensure_ascii=False)}

{SCHEMA_INSTRUCTIONS}"""
        try:
            text = _call_ai(prompt)
            analyses = _parse_json_array(text)
            for analysis in analyses:
                idx = analysis.get("index")
                if not isinstance(idx, int) or idx < 0 or idx >= len(chunk):
                    continue
                raw = chunk[idx]
                merged = dict(
                    title=raw["title"], source=raw["source"], source_url=raw["url"],
                    date=raw["published"],
                    tier=analysis.get("tier", 3),
                    category=analysis.get("category", "AI"),
                    is_gcp=bool(analysis.get("is_gcp", False)),
                    is_de=bool(analysis.get("is_de", False)),
                    summary=analysis.get("summary", ""),
                    whats_new=analysis.get("whats_new", ""),
                    why_matters=analysis.get("why_matters", ""),
                    why_learn=analysis.get("why_learn", ""),
                    what_to_learn=analysis.get("what_to_learn", []),
                    gcp_use=analysis.get("gcp_use", "No"),
                    gcp_use_case=analysis.get("gcp_use_case", ""),
                    scores=analysis.get("scores", {"gcp": 0, "de": 0, "ai": 0, "career": 0, "adoption": 0, "future": 0}),
                )
                enriched.append(merged)
        except Exception as e:
            errors.append(f"Enrichment batch failed ({len(chunk)} items): {e}")

    return enriched, errors
