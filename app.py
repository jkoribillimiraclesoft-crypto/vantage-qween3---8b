import os
import sys
import json
import datetime

import streamlit as st
import plotly.graph_objects as go

sys.path.insert(0, os.path.dirname(__file__))
from lib import config, db, pipeline
from lib.enrich import get_api_key, ai_backend_label

st.set_page_config(page_title="VANTAGE — GCP Data Engineering AI Intelligence", page_icon="☁️", layout="wide")

PRIORITY = config.PRIORITY
GCP_BLUE = config.GCP_BLUE
GCP_GREEN = config.GCP_GREEN
DEFAULT_WEIGHTS = config.DEFAULT_WEIGHTS
WEIGHT_LABELS = config.WEIGHT_LABELS
DEFAULT_PROFILE = config.DEFAULT_PROFILE
priority_for = config.priority_for

PROJECT_IDEAS = [
    dict(name="AI Data Quality Agent", icon="🩺",
         description="A GCP-based agent that continuously watches your BigQuery tables and flags problems before they hit downstream dashboards.",
         bullets=["Profiles new data and detects anomalies against historical patterns",
                  "Generates SQL data-quality checks automatically (nulls, ranges, freshness)",
                  "Explains failures in plain language, not just a stack trace",
                  "Suggests concrete fixes or a corrected dbt test"]),
    dict(name="AI Pipeline Assistant", icon="🛠️",
         description="An assistant that reads Airflow/Cloud Composer logs so you don't have to dig through them during an incident.",
         bullets=["Reads pipeline logs on failure", "Identifies the likely root cause across retries",
                  "Explains the error in plain language",
                  "Generates a troubleshooting checklist and a suggested fix"]),
    dict(name="Natural Language → BigQuery", icon="💬",
         description="Let stakeholders ask business questions in plain English and get back a reviewed BigQuery query and result.",
         bullets=["Accepts a question like 'customers whose revenue dropped over 20%'",
                  "Generates BigQuery SQL scoped to your actual schema",
                  "Shows the SQL for review before executing",
                  "Returns results plus a plain-language summary"]),
]

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
.stApp { background-color: #0A0E13; color: #E7EDF4; }
section[data-testid="stSidebar"] { background-color: #0D1218; border-right: 1px solid #232C38; }
h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif !important; }
.mono { font-family: 'IBM Plex Mono', monospace; }
.card { background: #121821; border: 1px solid #232C38; border-radius: 12px; padding: 18px; margin-bottom: 14px; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 600;
  font-family: 'IBM Plex Mono', monospace; letter-spacing: 0.3px; margin-right: 6px; }
.tag { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 12px; border: 1px solid #232C38;
  color: #E7EDF4; margin: 2px 4px 2px 0; }
.muted { color: #8B97A6; }
.faint { color: #5B6774; font-size: 12px; font-family: 'IBM Plex Mono', monospace; }
.stat-box { background: #121821; border: 1px solid #232C38; border-radius: 10px; padding: 14px 16px; }
.stat-label { font-family: 'IBM Plex Mono', monospace; font-size: 11px; color: #5B6774; letter-spacing: 0.5px; text-transform: uppercase; }
.stat-value { font-family: 'Space Grotesk', sans-serif; font-size: 26px; font-weight: 700; margin-top: 4px; }
.rank { font-family: 'Space Grotesk', sans-serif; font-size: 22px; font-weight: 700; color: #4285F4; width: 34px; display: inline-block; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ============================================================== STATE

db.init_db()

if "weights" not in st.session_state:
    st.session_state.weights = dict(DEFAULT_WEIGHTS)
if "profile" not in st.session_state:
    st.session_state.profile = dict(DEFAULT_PROFILE)
if "last_refresh_result" not in st.session_state:
    st.session_state.last_refresh_result = None
if "auto_refresh_attempted" not in st.session_state:
    st.session_state.auto_refresh_attempted = False


def weighted_score(item):
    w = st.session_state.weights
    total_w = sum(w.values()) or 1
    s = item["scores"]
    raw = sum(s.get(k, 0) * w[k] for k in w)
    return round(raw / total_w, 1)


def badge(priority_key):
    p = PRIORITY[priority_key]
    return f'<span class="badge" style="background:{p["color"]}; color:#06231F;">{p["emoji"]} {p["label"]}</span>'


def gcp_use_badge(val):
    color = {"Yes": GCP_GREEN, "Potentially": "#E8A23D", "No": "#5B6774"}.get(val, "#5B6774")
    return f'<span class="badge" style="background:{color}; color:#06231F;">{val}</span>'


def run_refresh():
    api_key = get_api_key()
    if not api_key:
        st.session_state.last_refresh_result = {"errors": [f"AI backend is not available: {ai_backend_label()} — check the hosted Qwen configuration and HF_TOKEN in Streamlit Secrets."]}
        return
    with st.spinner("Pulling live sources and running AI analysis… this can take 30-90 seconds."):
        result = pipeline.refresh(st.session_state.profile, config.SOURCES)
        st.session_state.last_refresh_result = result


# ============================================================== SIDEBAR

with st.sidebar:
    st.markdown("### ☁️ VANTAGE")
    st.caption("GCP Data Engineering AI Intelligence — live data")
    page = st.radio("Navigate", ["🏠 Overview", "🔥 Top For You", "☁️ GCP + AI", "📰 AI Updates",
                                  "🎓 Learning Roadmap", "💡 Project Ideas", "📊 Weekly Report",
                                  "⚙️ Profile", "🔌 Source Status"],
                     label_visibility="collapsed")
    st.divider()
    if st.button("🔄 Refresh live data", use_container_width=True):
        run_refresh()
    last = db.get_last_refresh()
    if last:
        st.caption(f"Last refresh: {last['ran_at'][:16].replace('T', ' ')} UTC — {last['new_items']} new items")
    st.caption(f"AI: **{ai_backend_label()}**")
    st.caption(f"Profile: **{st.session_state.profile['role']}**")
    st.caption(f"{db.count()} updates stored")

page = page.split(" ", 1)[1] if " " in page else page

# Auto-refresh once on first load if the DB is empty and a key is present.
if db.count() == 0 and not st.session_state.auto_refresh_attempted:
    st.session_state.auto_refresh_attempted = True
    if get_api_key():
        run_refresh()

if st.session_state.last_refresh_result:
    r = st.session_state.last_refresh_result
    with st.expander("Last refresh details", expanded=bool(r.get("errors"))):
        if "fetch_status" in r:
            for s in r["fetch_status"]:
                icon = "✅" if not s["error"] else "⚠️"
                st.markdown(f"{icon} **{s['source']}** — {s['count']} items" + (f" ({s['error']})" if s["error"] else ""))
            st.markdown(f"Raw items: {r['raw_count']} → new after dedup: {r['deduped_count']} → enriched & stored: {r['enriched_count']}")
        for e in r.get("errors", []):
            st.error(e)

UPDATES = db.get_all_updates()
SCORED = [(u, weighted_score(u)) for u in UPDATES]
SCORED.sort(key=lambda t: -t[1])

# ============================================================== EMPTY STATE

if not UPDATES and page not in ("Profile", "Source Status"):
    st.markdown("## No live data yet")
    if not get_api_key():
        st.warning(f"AI backend unavailable: `{ai_backend_label()}`. add a valid HF_TOKEN in Streamlit Secrets, then click **🔄 Refresh live data**.")
    else:
        st.info("Click **🔄 Refresh live data** in the sidebar to pull real sources and run the AI analysis.")
    st.stop()

# ============================================================== CARD HELPERS

def render_score_breakdown(item):
    w = st.session_state.weights
    cols = st.columns(6)
    for col, key in zip(cols, w.keys()):
        with col:
            st.markdown(f'<div class="faint">{WEIGHT_LABELS[key]}</div>'
                        f'<div style="font-family:\'IBM Plex Mono\',monospace; font-size:15px; font-weight:600;">{item["scores"].get(key, 0)}</div>',
                        unsafe_allow_html=True)


def render_update_card(item, score, rank=None):
    pr = priority_for(score)
    st.markdown('<div class="card">', unsafe_allow_html=True)
    top_l, top_r = st.columns([5, 1])
    with top_l:
        rank_html = f'<span class="rank">#{rank}</span> ' if rank else ""
        st.markdown(f'{rank_html}{badge(pr)}<span class="faint">Tier {item["tier"]} · {item["category"]}</span>', unsafe_allow_html=True)
        st.markdown(f'#### {item["title"]}')
        st.markdown(f'<span class="muted">{item["summary"]}</span>', unsafe_allow_html=True)
        st.markdown(f'<span class="faint">{item["source"]} · {item["date"]}</span>', unsafe_allow_html=True)
    with top_r:
        st.metric("Personal Relevance", f'{score:.0f}/100')

    with st.expander("Why should I learn this? (full breakdown)"):
        st.markdown(f"**What's New?**  \n{item['whats_new']}")
        st.markdown(f"**Why Does It Matter?**  \n{item['why_matters']}")
        st.markdown(f"**Why Should I Learn This?**  \n{item['why_learn']}")
        st.markdown("**What Should I Learn?**")
        st.markdown("".join(f'<span class="tag">{t}</span>' for t in item["what_to_learn"]), unsafe_allow_html=True)
        st.markdown(f"**Can I use this in a GCP data engineering project?** {gcp_use_badge(item['gcp_use'])}", unsafe_allow_html=True)
        st.markdown(f"<span class='muted'>{item['gcp_use_case']}</span>", unsafe_allow_html=True)
        st.markdown("**Score breakdown**")
        render_score_breakdown(item)
        st.link_button(f"Read original on {item['source']} ↗", item["source_url"])
    st.markdown('</div>', unsafe_allow_html=True)


# ============================================================== OVERVIEW

if page == "Overview":
    st.markdown("## Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    must_count = sum(1 for u, s in SCORED if priority_for(s) == "must")
    avg_score = sum(s for _, s in SCORED) / len(SCORED) if SCORED else 0
    for col, label, value, color in [
        (c1, "AI Updates Tracked", len(UPDATES), "#E7EDF4"),
        (c2, "GCP Updates", sum(1 for u in UPDATES if u["is_gcp"]), GCP_BLUE),
        (c3, "Data Engineering Updates", sum(1 for u in UPDATES if u["is_de"]), "#E7EDF4"),
        (c4, "Must Learn Topics", must_count, PRIORITY["must"]["color"]),
        (c5, "Avg Personal Relevance", f"{avg_score:.0f}", GCP_GREEN),
    ]:
        with col:
            st.markdown(f'<div class="stat-box"><div class="stat-label">{label}</div>'
                        f'<div class="stat-value" style="color:{color};">{value}</div></div>', unsafe_allow_html=True)

    st.markdown("")
    col1, col2 = st.columns([1.3, 1])
    with col1:
        st.markdown("**Personal Relevance Score by Update**")
        titles = [u["title"][:38] + ("…" if len(u["title"]) > 38 else "") for u, s in SCORED]
        scores = [s for u, s in SCORED]
        colors = [PRIORITY[priority_for(s)]["color"] for s in scores]
        fig = go.Figure(go.Bar(x=scores, y=titles, orientation="h", marker_color=colors))
        fig.update_layout(height=max(300, 34 * len(titles)), margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font=dict(color="#8B97A6", size=11),
                           xaxis=dict(gridcolor="#232C38", range=[0, 100]), yaxis=dict(autorange="reversed"))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        st.markdown("**Learning Priority Distribution**")
        counts = {}
        for u, s in SCORED:
            pr = priority_for(s)
            counts[PRIORITY[pr]["label"]] = counts.get(PRIORITY[pr]["label"], 0) + 1
        fig = go.Figure(go.Pie(labels=list(counts.keys()), values=list(counts.values()), hole=0.55,
                                marker=dict(colors=[PRIORITY[k]["color"] for k, v in PRIORITY.items() if v["label"] in counts])))
        fig.update_layout(height=max(300, 34 * len(titles)), margin=dict(l=10, r=10, t=10, b=10),
                           paper_bgcolor="rgba(0,0,0,0)", font=dict(color="#8B97A6"), showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

elif page == "Top For You":
    st.markdown("## Top 5 Updates You Should Know Today")
    st.caption("Ranked from live sources, specifically for your profile.")
    for i, (u, s) in enumerate(SCORED[:5], start=1):
        render_update_card(u, s, rank=i)

elif page == "GCP + AI":
    st.markdown("## GCP + AI")
    st.caption("Live developments directly relevant to GCP data engineering.")
    gcp_items = [(u, s) for u, s in SCORED if u["is_gcp"] or u["tier"] == 1]
    for u, s in gcp_items:
        render_update_card(u, s)
    if not gcp_items:
        st.info("No GCP-tagged updates in the current data yet.")

elif page == "AI Updates":
    st.markdown("## AI Updates")
    st.caption("Broader AI developments, ranked by relevance to your profile rather than recency.")
    f1, f2 = st.columns(2)
    tier_filter = f1.selectbox("Tier", ["All tiers", "Tier 1", "Tier 2", "Tier 3", "Tier 4"])
    prio_filter = f2.selectbox("Priority", ["All priorities"] + [p["label"] for p in PRIORITY.values()])
    items = SCORED
    if tier_filter != "All tiers":
        t = int(tier_filter.split(" ")[1])
        items = [(u, s) for u, s in items if u["tier"] == t]
    if prio_filter != "All priorities":
        items = [(u, s) for u, s in items if PRIORITY[priority_for(s)]["label"] == prio_filter]
    st.caption(f"{len(items)} updates")
    for u, s in items:
        render_update_card(u, s)

elif page == "Learning Roadmap":
    st.markdown("## 🎓 My AI Learning Roadmap")
    buckets = {"Learn Now": [], "Learn Next": [], "Explore Later": [], "Watch": []}
    for u, s in SCORED:
        pr = priority_for(s)
        bucket = {"must": "Learn Now", "important": "Learn Next", "explore": "Explore Later", "watch": "Watch"}[pr]
        buckets[bucket].append((u, s))
    for label in ["Learn Now", "Learn Next", "Explore Later"]:
        st.markdown(f"### {label}")
        items = buckets[label]
        if not items:
            st.caption("Nothing here right now.")
            continue
        for u, s in items:
            st.markdown(f'<div class="card"><b>{u["title"]}</b> '
                        f'<span class="faint">{u["category"]}</span><br>'
                        f'<span class="muted" style="font-size:13px;">{u["why_learn"]}</span><br>'
                        f'<span class="mono" style="font-size:13px; color:#4285F4;">Personal Relevance: {s:.0f}/100</span>'
                        f'</div>', unsafe_allow_html=True)
    with st.expander(f"Watch list ({len(buckets['Watch'])} items — tracked but not prioritized)"):
        for u, s in buckets["Watch"]:
            st.markdown(f"- **{u['title']}** — {s:.0f}/100")

elif page == "Project Ideas":
    st.markdown("## 💡 Projects I Can Build")
    st.caption("Practical project ideas grounded in the live data above.")
    cols = st.columns(3)
    for col, proj in zip(cols, PROJECT_IDEAS):
        with col:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"### {proj['icon']} {proj['name']}")
            st.markdown(f'<span class="muted">{proj["description"]}</span>', unsafe_allow_html=True)
            for b in proj["bullets"]:
                st.markdown(f"- {b}")
            st.markdown('</div>', unsafe_allow_html=True)

elif page == "Weekly Report":
    st.markdown("## 📊 My AI & Data Engineering Weekly Report")
    st.caption("Generated live from currently stored updates, weighted by your profile.")
    if st.button("✨ Generate my weekly report"):
        api_key = get_api_key()
        if not api_key:
            st.error(f"AI backend unavailable: {ai_backend_label()}. check the hosted Qwen configuration and HF_TOKEN in Streamlit Secrets.")
        else:
            with st.spinner("Generating your report…"):
                try:
                    from lib.enrich import _call_ai
                    payload = [dict(title=u["title"], category=u["category"], tier=u["tier"], source=u["source"],
                                     summary=u["summary"], personal_relevance=s,
                                     priority=PRIORITY[priority_for(s)]["label"], gcp_use=u["gcp_use"])
                               for u, s in SCORED]
                    profile = st.session_state.profile
                    prompt = f"""You are a personal AI Career Intelligence Assistant and GCP Data Engineering Advisor.

USER PROFILE:
Role: {profile['role']}
Primary expertise: {profile['expertise']}
AI experience: {profile['ai_experience']}

THIS WEEK'S LIVE, SCORED UPDATES (JSON):
{json.dumps(payload, ensure_ascii=False)}

Write "My AI & Data Engineering Weekly Report" with these sections, plain text, no markdown headers:
1. Most Important Updates — top 5 with a one-line reason each.
2. What Changed in GCP?
3. What Changed in AI?
4. What Should I Learn? — top 3, ranked, one-line reason each.
5. What Should I Build? — top 2 project ideas grounded in this data.
6. Career Impact — short paragraph on how this affects a modern GCP Data Engineer's expected skills.
Every point must connect specifically to GCP + Data Engineering + AI — never generic filler."""
                    st.session_state.weekly_report = _call_ai(prompt)
                except Exception as e:
                    st.error(f"Couldn't generate the report: {e}")
    if st.session_state.get("weekly_report"):
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f'<div class="muted" style="white-space:pre-wrap; font-size:13.5px; line-height:1.65;">{st.session_state.weekly_report}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

elif page == "Profile":
    st.markdown("## ⚙️ Profile")
    st.caption("Your role and expertise personalize every AI analysis, including future refreshes.")
    p = st.session_state.profile
    p["role"] = st.text_input("Role", p["role"])
    p["expertise"] = st.text_area("Primary expertise", p["expertise"])
    p["ai_experience"] = st.text_area("AI experience", p["ai_experience"])
    st.caption("Changes here apply the next time you click **Refresh live data** — already-stored items keep their existing analysis until re-fetched.")

    st.markdown("### Personal Relevance Score weights")
    st.caption("These re-rank instantly — no refresh needed, since raw component scores are already stored.")
    w = st.session_state.weights
    cols = st.columns(3)
    keys = list(w.keys())
    for i, key in enumerate(keys):
        with cols[i % 3]:
            w[key] = st.slider(WEIGHT_LABELS[key], 0, 100, w[key], key=f"w_{key}")
    total = sum(w.values())
    if total != 100:
        st.warning(f"Weights currently sum to {total}%, not 100% — scores are normalized automatically.")
    if st.button("Reset weights to default"):
        st.session_state.weights = dict(DEFAULT_WEIGHTS)
        st.rerun()

elif page == "Source Status":
    st.markdown("## 🔌 Source Status")
    st.caption("Sources this pipeline pulls from, and what happened on the last refresh.")
    last = db.get_last_refresh()
    if not last:
        st.info("No refresh has run yet. Click **🔄 Refresh live data** in the sidebar.")
    else:
        st.caption(f"Last refresh: {last['ran_at'][:16].replace('T',' ')} UTC")
        for s in last["status"]:
            icon = "✅" if not s["error"] else "⚠️"
            st.markdown(f'<div class="card">{icon} <b>{s["source"]}</b> — {s["count"]} items fetched'
                        + (f'<br><span class="muted" style="font-size:12.5px;">{s["error"]}</span>' if s["error"] else "")
                        + '</div>', unsafe_allow_html=True)
    st.markdown("### Configured sources")
    for cfg in config.SOURCES:
        st.markdown(f"- **{cfg['name']}** ({cfg['kind']})")
