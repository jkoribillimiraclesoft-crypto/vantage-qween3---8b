# VANTAGE — GCP Data Engineering AI Intelligence (Live)

VANTAGE pulls live technical updates, deduplicates them, analyzes them against
your GCP Data Engineer profile, stores the results in SQLite, and serves them
through Streamlit.

## AI model

The Streamlit/GitHub deployment uses **Qwen3 8B** hosted through **Hugging Face Inference Providers**.
Hugging Face provides an OpenAI-compatible chat-completions endpoint, so VANTAGE
can call Qwen remotely without running Ollama on the Streamlit server.

Qwen3-8B is an Apache-2.0 licensed model and its model page documents hosted
inference providers as well as OpenAI-compatible serving options.

The AI analysis covers:

- summary and what's new
- practical importance
- personalized learning recommendations
- GCP use cases
- GCP / Data Engineering / AI / career / adoption / future scores

Titles, URLs, sources, and dates continue to come only from the live source
fetchers; the AI is used for interpretation rather than inventing source
metadata.

## Live sources

- arXiv (official Atom API)
- Hacker News (official Firebase API)
- GitHub (official search API)
- Google Cloud Blog
- Google Cloud Release Notes
- dbt Labs Blog
- LangChain Blog
- Snowflake Blog
- Meta AI Blog

## Streamlit Cloud deployment

### 1. Create a Hugging Face token

Create a Hugging Face access token with permission to use **Inference Providers**.
The hosted router is OpenAI-compatible and is documented at:
https://huggingface.co/docs/inference-providers/en/tasks/chat-completion

### 2. Push this project to GitHub

Do not commit your real `.streamlit/secrets.toml`. Only commit the example file.

### 3. Add Streamlit Cloud secrets

In your Streamlit app settings, open **Secrets** and add:

```toml
AI_PROVIDER = "huggingface"
AI_MODEL = "Qwen/Qwen3-8B"
HF_BASE_URL = "https://router.huggingface.co/v1"
HF_TOKEN = "hf_your_real_token"
```

Streamlit Community Cloud supports storing secrets in the app settings instead
of committing them to GitHub.

### 4. Deploy

Select the GitHub repository, branch, and `app.py` as the entrypoint in Streamlit
Community Cloud. After deployment, the sidebar should show:

```text
AI: Hugging Face / Qwen/Qwen3-8B
```

Then click **Refresh live data**.

## Local development

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml` locally (and keep it out of Git):

```toml
AI_PROVIDER = "huggingface"
AI_MODEL = "Qwen/Qwen3-8B"
HF_BASE_URL = "https://router.huggingface.co/v1"
HF_TOKEN = "hf_your_real_token"
```

Run:

```bash
streamlit run app.py
```

## Configuration

The following settings are configurable through environment variables or
Streamlit Secrets:

| Setting | Default | Purpose |
|---|---|---|
| `AI_PROVIDER` | `huggingface` | AI backend |
| `AI_MODEL` | `Qwen/Qwen3-8B` | Qwen model ID |
| `HF_BASE_URL` | `https://router.huggingface.co/v1` | Hosted OpenAI-compatible endpoint |
| `HF_TOKEN` | — | Hugging Face Inference Providers token |

## What changed from the Ollama version

- Removed the local Ollama dependency from the deployment path.
- Replaced Ollama `/api/chat` calls with Hugging Face's OpenAI-compatible `/v1/chat/completions` endpoint.
- Default model is `Qwen/Qwen3-8B`.
- Added `HF_TOKEN`-based authentication through Streamlit Secrets.
- Kept the existing live-source, deduplication, scoring, SQLite, and Streamlit UI architecture.
- Added more tolerant JSON parsing for hosted model responses.
- Weekly Report uses the same hosted Qwen backend.

## Project structure

```text
vantage_live/
├── app.py
├── requirements.txt
├── README.md
├── .streamlit/
│   └── secrets.toml.example
├── data/
│   └── .gitkeep
└── lib/
    ├── config.py
    ├── db.py
    ├── dedup.py
    ├── enrich.py
    ├── pipeline.py
    └── sources.py
```
