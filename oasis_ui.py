"""
oasis_ui.py — OASIS Dubai Real Estate Simulation Lab
=====================================================
Interactive Streamlit UI for configuring, running, and analysing the
CAMEL-AI OASIS 15-agent Dubai real estate market simulation.

Run:
    streamlit run oasis_ui.py
    # or via Docker:
    docker compose --profile oasis-ui up
"""
from __future__ import annotations

import json
import os
import queue
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# On Streamlit Cloud, secrets live in st.secrets (not env vars).
# On Railway/Docker, env vars are already set — st.secrets doesn't exist.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k, _v)
except Exception:
    pass

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

PROFILE_PATH   = Path("./data/user_data_realestate_15.json")
TRANSCRIPT_DIR = Path("./transcripts")
DB_PATH        = Path("./transcripts/oasis_realestate.db")

MBTI_DESCRIPTIONS: dict[str, str] = {
    "ENTJ": "Decisive, numbers-first, commands the room — dismisses emotion",
    "ISFJ": "Cautious, protective, helpful — asks lots of clarifying questions",
    "ENTP": "Contrarian, challenges assumptions, sees opportunity in chaos",
    "INFP": "Emotionally driven, seeks reassurance from others, torn",
    "INTJ": "Strategic, data-only, distrusts hype, cold and analytical",
    "ESFP": "Enthusiastic, shares personal stories, frequent exclamation marks",
    "ESTJ": "Professional, balanced, reputation-conscious, measured",
    "ESTP": "Action-oriented, opportunistic, charismatic, fast-moving",
    "INFJ": "Values-driven, long-term thinker, advocates for the vulnerable",
    "INTP": "Analytical, nuanced, data-focused, questioning",
    "ISTJ": "Methodical, fact-based, consistent, rule-following",
}

COUNTRY_FLAGS: dict[str, str] = {
    "UAE": "🇦🇪",
    "India": "🇮🇳",
    "Spain": "🇪🇸",
    "United Kingdom": "🇬🇧",
    "Singapore": "🇸🇬",
    "Pakistan": "🇵🇰",
}

# Market event presets — cover different scenarios for testing
EVENT_PRESETS: dict[str, str] = {
    "Price Surge + Golden Visa": (
        "Dubai residential property prices surge 15% year-on-year, "
        "driven by record Golden Visa applications and constrained supply "
        "in prime districts (Palm Jumeirah, Downtown, Dubai Marina)."
    ),
    "Interest Rate Hike": (
        "UAE Central Bank raises benchmark interest rate by 50 basis points, "
        "pushing average mortgage rates above 6.5%. RERA warns of potential "
        "affordability pressure on first-time buyers in mid-market segments."
    ),
    "Supply Glut Warning": (
        "DLD data reveals 35,000 new units scheduled for handover in 2026, "
        "raising concerns of oversupply in JVC, Dubai South and Business Bay. "
        "Developers defend pipeline as meeting genuine long-term demand."
    ),
    "Regulatory Crackdown": (
        "RERA launches audit of 50 off-plan projects for escrow compliance violations. "
        "Three mid-tier developers placed under DLD supervision. "
        "Investors urged to verify project registration before committing funds."
    ),
    "Market Correction": (
        "Dubai prime property prices dip 8% QoQ as global risk-off sentiment "
        "accelerates. DLD transaction volumes fall 22%. Analysts debate whether "
        "this is a healthy correction or the start of a broader downturn."
    ),
}

# Conflict structure — who benefits from price rises vs who is hurt
PRICE_RISE_BENEFICIARIES = [
    ("Hassan Al-Farsi", "Property Developer CEO", "Sells off-plan at higher prices"),
    ("Raj Kapoor", "Property Investor", "Portfolio paper gains, higher achievable rents"),
    ("Khalid Al-Zaabi", "Landlord / Property Owner", "Asset appreciation + rent increases"),
    ("Zara Williams", "Marketing Director (outgoing)", "Exiting with maximum profit"),
]
PRICE_RISE_LOSERS = [
    ("Ayesha Al-Mansouri", "Marketing Executive", "First-time buyer — affordability squeeze"),
    ("Priya Nair", "Graphic Designer", "Renter facing higher costs and FOMO"),
    ("Layla Mohammed", "Urban Planner", "Social housing gap widens"),
    ("Omar Al-Rashid", "RERA Compliance Officer", "Systemic risk and unsophisticated buyers at risk"),
]
PRICE_RISE_NEUTRAL = [
    ("Sofia Rodriguez", "Real Estate Broker", "Earns commission on both sides"),
    ("Marcus Sterling", "Institutional Fund Manager", "Macro cycle analysis"),
    ("Emma Clarke", "Mortgage Broker", "Advises caution regardless of direction"),
    ("David Chen", "Financial Analyst", "REIT/stock analyst — data-driven"),
    ("Nina Patel", "PropTech Founder / CEO", "Sees volatility as tech adoption opportunity"),
    ("Tariq Ahmad", "Senior IT Manager", "New expat evaluating first purchase"),
]


# ──────────────────────────────────────────────────────────────────────────────
# Page config & CSS
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="OASIS Agent Lab — Dubai RE",
    page_icon="🏙",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    /* ── Agent cards ─────────────────────────────────────────────────── */
    .agent-card {
        background: #151a2e;
        border-radius: 10px;
        padding: 14px 16px;
        border-left: 4px solid #3d6db5;
        margin-bottom: 4px;
    }
    .agent-card h4 { margin: 0 0 2px 0; color: #dde; font-size: 0.95rem; }
    .agent-card .agent-role { color: #7a8aaa; font-size: 0.78rem; margin-bottom: 8px; }
    .agent-card .agent-persona {
        color: #aab;
        font-size: 0.8rem;
        line-height: 1.55;
        border-top: 1px solid #252a45;
        padding-top: 8px;
        margin-top: 6px;
    }
    /* ── Info / warning boxes ────────────────────────────────────────── */
    .info-box {
        background: #0c1d35;
        border: 1px solid #1a4878;
        border-radius: 8px;
        padding: 13px 16px;
        margin: 8px 0 12px 0;
        font-size: 0.84rem;
        line-height: 1.65;
        color: #80bcf0;
    }
    .warn-box {
        background: #271a08;
        border: 1px solid #7a4e1a;
        border-radius: 8px;
        padding: 13px 16px;
        margin: 8px 0 12px 0;
        font-size: 0.84rem;
        line-height: 1.65;
        color: #e0b860;
    }
    .success-box {
        background: #0d2018;
        border: 1px solid #1a7a40;
        border-radius: 8px;
        padding: 13px 16px;
        margin: 8px 0 12px 0;
        font-size: 0.84rem;
        line-height: 1.65;
        color: #60d090;
    }
    /* ── Post bubbles ────────────────────────────────────────────────── */
    .post-bubble {
        background: #131826;
        border-radius: 10px;
        padding: 12px 15px;
        margin-bottom: 10px;
        border-left: 3px solid #3d6db5;
        font-size: 0.84rem;
        line-height: 1.6;
        color: #c8cce0;
    }
    .post-bubble .post-header {
        font-weight: 600;
        color: #d8ddf0;
        margin-bottom: 6px;
        font-size: 0.88rem;
    }
    .post-bubble .post-meta {
        color: #505878;
        font-size: 0.72rem;
    }
    /* ── Badges ──────────────────────────────────────────────────────── */
    .badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.68rem;
        font-weight: 700;
        margin: 1px 2px;
    }
    .badge-mbti     { background: #1a2850; color: #80aaee; }
    .badge-country  { background: #182818; color: #80cc80; }
    .badge-positive { background: #0c2018; color: #50d080; }
    .badge-neutral  { background: #282008; color: #e0a840; }
    .badge-negative { background: #280c0c; color: #e05050; }
    /* ── Conflict cards ──────────────────────────────────────────────── */
    .conflict-card {
        border-radius: 8px;
        padding: 14px;
        font-size: 0.83rem;
        line-height: 1.8;
    }
    .conflict-good { background: #0d2018; border-left: 3px solid #2ecc71; }
    .conflict-bad  { background: #200c0c; border-left: 3px solid #e74c3c; }
    .conflict-neut { background: #1a1810; border-left: 3px solid #f39c12; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

@st.cache_data
def load_profiles() -> list[dict]:
    if not PROFILE_PATH.exists():
        return []
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


def list_transcripts() -> list[Path]:
    if not TRANSCRIPT_DIR.exists():
        return []
    return sorted(
        TRANSCRIPT_DIR.glob("realestate_stance_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def load_transcript(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_simulation_subprocess(
    event: str,
    rounds: int,
    profile_path: str,
    output_queue: queue.Queue,
) -> None:
    """Launch real_estate_oasis.py as a subprocess with CLI args."""
    cmd = [
        sys.executable,
        "real_estate_oasis.py",
        "--event", event,
        "--rounds", str(rounds),
        "--profile-path", profile_path,
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(Path(__file__).parent),
        )
        for line in proc.stdout:
            output_queue.put(("line", line.rstrip()))
        proc.wait()
        output_queue.put(("done", proc.returncode))
    except Exception as exc:
        output_queue.put(("error", str(exc)))


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🏙 OASIS Agent Lab")
    st.caption("Dubai Real Estate · CAMEL-AI OASIS")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        options=["Overview", "Agent Roster", "Configure & Run", "Results Viewer"],
        label_visibility="collapsed",
    )

    st.markdown("---")

    n_transcripts = len(list_transcripts())
    n_profiles    = len(load_profiles())
    st.markdown(
        f"""
        <div style='font-size:0.8rem; color:#666; line-height:2.1'>
        📁 &nbsp;Transcripts saved: <b style='color:#999'>{n_transcripts}</b><br>
        👥 &nbsp;Agents loaded: <b style='color:#999'>{n_profiles}</b><br>
        🗄 &nbsp;SQLite DB: <b style='color:#999'>{"exists" if DB_PATH.exists() else "not found"}</b>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown(
        """
        <div style='font-size:0.74rem; color:#555; line-height:1.9'>
        <b>Quick start</b><br>
        1️⃣ &nbsp;Browse agents → <em>Agent Roster</em><br>
        2️⃣ &nbsp;Set event → <em>Configure &amp; Run</em><br>
        3️⃣ &nbsp;Copy command or click Run<br>
        4️⃣ &nbsp;Explore results → <em>Results Viewer</em>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.caption("Powered by CAMEL-AI OASIS · Azure OpenAI")


# ──────────────────────────────────────────────────────────────────────────────
# PAGE: Overview
# ──────────────────────────────────────────────────────────────────────────────

if page == "Overview":
    st.title("OASIS Agent Lab — Dubai Real Estate")
    st.markdown(
        "**15 AI-powered agents** with distinct Dubai real estate personas react to a market "
        "event across 3 autonomous LLM rounds on a simulated Reddit-style platform. "
        "This lab lets you configure events, tune personas, run simulations, and explore results."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Agents", "15", "1 seeder + 14 personas")
    c2.metric("LLM Rounds", "3", "All agents act simultaneously")
    c3.metric("Action Types", "9", "Post, comment, like, follow…")
    c4.metric("Output", "SQLite + JSON", "Per-agent stance + posts")

    st.markdown("---")
    st.subheader("How the Simulation Works")

    tab_flow, tab_rounds, tab_mem, tab_conflict = st.tabs(
        ["Simulation Flow", "Round Structure", "Memory & Visibility", "Conflict Design"]
    )

    with tab_flow:
        st.code(
            """
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        OASIS Simulation Flow                            │
  │                                                                         │
  │  1.  You supply a MARKET EVENT description                              │
  │  2.  Agent 0 (UAE Property News) posts it as the seed post              │
  │  3.  All 14 persona agents read the seed and take actions               │
  │      simultaneously — post, comment, like, follow, search…  (Round 1)  │
  │  4.  Rounds 2 and 3 repeat — agents see ALL previous posts each round   │
  │  5.  After 3 rounds, Azure OpenAI classifies each agent's stance        │
  │      (positive / neutral / negative) from their post history            │
  │  6.  Results saved to SQLite DB + JSON transcript in ./transcripts/     │
  └─────────────────────────────────────────────────────────────────────────┘
            """,
            language="text",
        )
        st.markdown("**Available agent actions each round:**")
        st.dataframe(
            pd.DataFrame({
                "Action": [
                    "CREATE_POST", "CREATE_COMMENT", "LIKE_POST", "DISLIKE_POST",
                    "FOLLOW", "REPOST", "SEARCH_POSTS", "TREND", "DO_NOTHING",
                ],
                "Description": [
                    "Write a new top-level post",
                    "Reply directly to another agent's post",
                    "Upvote a post (affects visibility)",
                    "Downvote a post",
                    "Follow another agent",
                    "Share another agent's post",
                    "Search for posts matching a topic",
                    "Surface currently trending topics",
                    "Stay silent this round",
                ],
            }),
            width='stretch',
            hide_index=True,
        )

    with tab_rounds:
        st.markdown(
            '<div class="info-box">'
            "The simulation is <b>evolving</b>, not one-shot. Each round, every agent reads the "
            "full current state of the platform (all previous posts + engagement counts) and "
            "independently decides what to do. This mirrors how Reddit actually works."
            "</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(
            pd.DataFrame({
                "Round": ["0 — Seed", "1 — Initial reactions", "2 — Engagement", "3 — Synthesis"],
                "Who acts": ["Agent 0 (manual)", "All 14 agents", "All 14 agents", "All 14 agents"],
                "Context visible to agents": [
                    "Nothing — event text only",
                    "Seed post",
                    "Seed + Round 1 posts",
                    "Seed + Round 1 + Round 2 posts",
                ],
                "Typical behaviour": [
                    "Neutral factual news post",
                    "Initial positions, questions, analysis",
                    "Replies, debates, agreement / pushback",
                    "Synthesis, summaries, final positions",
                ],
            }),
            width='stretch',
            hide_index=True,
        )

    with tab_mem:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(
                '<div class="success-box">'
                "<b>✅ Agents CAN see:</b><br>"
                "• All public posts and comments from <em>previous</em> rounds<br>"
                "• Like / dislike counts on each post<br>"
                "• Which posts are trending<br>"
                "• Their own persona (baked into their system prompt)<br>"
                "• Topics they searched for"
                "</div>",
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown(
                '<div class="warn-box">'
                "<b>❌ Agents CANNOT see:</b><br>"
                "• What other agents will do in the <em>current</em> round<br>"
                "• Posts from future rounds<br>"
                "• Other agents' private briefings (unless posted publicly)<br>"
                "• The simulation mechanics — they don't know they're in a swarm<br>"
                "• Any external data unless injected via the seed or persona"
                "</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div class="info-box">'
            "<b>The platform IS the memory.</b> There is no separate vector database. "
            "OASIS stores all posts in SQLite. When an agent takes their turn, OASIS feeds them "
            "the current platform state as context. Short-term memory can be extended by appending "
            "a summary of each agent's last post back into their persona between rounds."
            "</div>",
            unsafe_allow_html=True,
        )

    with tab_conflict:
        st.markdown(
            "Agents are designed so their **economic stakes conflict** naturally. "
            "No hardcoded disagreement is needed — the structural tension does the work."
        )
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            rows = "\n".join(f"• {n} ({r})<br>&nbsp;&nbsp;<em style='color:#3a8a5a'>{why}</em>" for n, r, why in PRICE_RISE_BENEFICIARIES)
            st.markdown(
                f'<div class="conflict-card conflict-good">'
                f'<b style="color:#2ecc71">📈 Price rise = GOOD for</b><br><br>{rows}</div>',
                unsafe_allow_html=True,
            )
        with cc2:
            rows = "\n".join(f"• {n} ({r})<br>&nbsp;&nbsp;<em style='color:#8a3a3a'>{why}</em>" for n, r, why in PRICE_RISE_LOSERS)
            st.markdown(
                f'<div class="conflict-card conflict-bad">'
                f'<b style="color:#e74c3c">📉 Price rise = BAD for</b><br><br>{rows}</div>',
                unsafe_allow_html=True,
            )
        with cc3:
            rows = "\n".join(f"• {n}<br>&nbsp;&nbsp;<em style='color:#7a6a30'>{why}</em>" for n, _, why in PRICE_RISE_NEUTRAL)
            st.markdown(
                f'<div class="conflict-card conflict-neut">'
                f'<b style="color:#f39c12">📊 Analytical / neutral</b><br><br>{rows}</div>',
                unsafe_allow_html=True,
            )

    st.markdown("---")
    st.subheader("What Drives Agent Specificity")
    st.markdown(
        "Three sources combine to produce responses that look like real market participants:"
    )
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown(
            '<div class="info-box">'
            "<b>1 — Seed event</b><br><br>"
            "Numbers and names in the event description propagate into all agent responses. "
            "\"15%\", \"Palm Jumeirah\", \"Golden Visa\" — these appear across every agent's posts "
            "because every agent reads the seed post in Round 1."
            "</div>",
            unsafe_allow_html=True,
        )
    with e2:
        st.markdown(
            '<div class="info-box">'
            "<b>2 — LLM pre-training</b><br><br>"
            "GPT-4 was trained on vast Dubai property content: DLD reports, RERA announcements, "
            "forum posts. It knows Golden Visa thresholds (AED 2M), EMAAR, NAKHEEL, typical "
            "rental yields (5–7%), mortgage rates — without you providing them."
            "</div>",
            unsafe_allow_html=True,
        )
    with e3:
        st.markdown(
            '<div class="info-box">'
            "<b>3 — Persona field</b><br><br>"
            "The most impactful parameter. Raj's persona mentions \"JVC, Dubai South, "
            "Business Bay\" → he references those districts. Marcus's mentions \"basis points\", "
            "\"$800M portfolio\" → he uses institutional finance language. "
            "The persona primes domain-specific vocabulary."
            "</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Example: weak vs strong persona"):
        col_w, col_s = st.columns(2)
        with col_w:
            st.markdown("**Weak** — produces generic output:")
            st.code('"persona": "Real estate investor who likes Dubai property."', language="json")
        with col_s:
            st.markdown("**Strong** — produces specific, distinctive output:")
            st.code(
                '"persona": "Seasoned Indian expat property investor with 8 units\n'
                'across JVC, Dubai South, and Business Bay. Calculates yield\n'
                'obsessively. Bullish on Dubai long-term but always looking for\n'
                'the right entry price. Dismisses panic sellers as short-sighted.\n'
                'Speaks in numbers and ROI. Never emotional."',
                language="json",
            )


# ──────────────────────────────────────────────────────────────────────────────
# PAGE: Agent Roster
# ──────────────────────────────────────────────────────────────────────────────

elif page == "Agent Roster":
    profiles = load_profiles()

    st.title("Agent Roster")
    st.markdown(
        f"**{len(profiles)} agents** — browse profiles, understand what makes each persona "
        "distinctive, and learn which fields have the most impact on LLM output."
    )

    if not profiles:
        st.error(f"Could not load profiles from `{PROFILE_PATH}`. Check the data directory.")
        st.stop()

    # ── Filters ──────────────────────────────────────────────────────────────
    fc1, fc2, fc3 = st.columns([2, 2, 1])
    with fc1:
        countries = sorted({p.get("country", "") for p in profiles if p.get("country") and p.get("country") != "N/A"})
        filter_country = st.multiselect("Filter by country", countries, default=[])
    with fc2:
        mbtis = sorted({p.get("mbti", "") for p in profiles if p.get("mbti")})
        filter_mbti = st.multiselect("Filter by MBTI", mbtis, default=[])
    with fc3:
        show_full = st.toggle("Show full personas", value=False)

    filtered = [
        p for p in profiles
        if (not filter_country or p.get("country") in filter_country)
        and (not filter_mbti or p.get("mbti") in filter_mbti)
    ]
    st.caption(f"Showing {len(filtered)} of {len(profiles)} agents")

    # ── MBTI reference ────────────────────────────────────────────────────────
    with st.expander("MBTI Communication Style Reference"):
        st.markdown(
            '<div class="info-box">'
            "The MBTI field acts as a <b>communication style dial</b>. "
            "An ENTJ agent writes decisive, numbers-first posts. An INFP agent asks others "
            "for reassurance and sounds emotionally torn. Same event, very different posts."
            "</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(
            pd.DataFrame([{"MBTI": k, "Communication Style": v} for k, v in MBTI_DESCRIPTIONS.items()]),
            width='stretch',
            hide_index=True,
        )

    st.markdown("---")

    # ── Agent cards in 3-col grid ─────────────────────────────────────────────
    for row_start in range(0, len(filtered), 3):
        row = filtered[row_start: row_start + 3]
        cols = st.columns(3)
        for col, p in zip(cols, row):
            name     = p.get("realname", "Unknown")
            uname    = p.get("username", "")
            role     = p.get("profession", "")
            country  = p.get("country", "")
            mbti     = p.get("mbti", "")
            age      = p.get("age", "")
            persona  = p.get("persona", "")
            bio      = p.get("bio", "")
            topics   = p.get("interested_topics", [])
            flag     = COUNTRY_FLAGS.get(country, "🌐")
            mbti_tip = MBTI_DESCRIPTIONS.get(mbti, "")
            persona_text = persona if show_full else (persona[:200] + ("…" if len(persona) > 200 else ""))

            with col:
                with st.expander(f"{flag} **{name}** — {role}", expanded=True):
                    # Header row
                    st.markdown(
                        f"<span class='badge badge-mbti' title='{mbti_tip}'>{mbti}</span>"
                        f"<span class='badge badge-country'>{flag} {country}</span>"
                        f"<span style='color:#556; font-size:0.75rem'>&nbsp;@{uname} · Age {age}</span>",
                        unsafe_allow_html=True,
                    )
                    # Bio
                    st.markdown(
                        f"<div style='color:#7a8aaa; font-size:0.8rem; font-style:italic; margin:6px 0'>{bio}</div>",
                        unsafe_allow_html=True,
                    )
                    # Persona box
                    st.markdown("**Persona:**")
                    st.markdown(
                        f"<div style='background:#0d1226; border-radius:6px; padding:10px 12px; "
                        f"font-size:0.8rem; line-height:1.55; color:#aab8cc; "
                        f"border-left:3px solid #2d5090'>{persona_text}</div>",
                        unsafe_allow_html=True,
                    )
                    # Topics
                    if topics:
                        st.markdown(
                            "<div style='margin-top:8px; font-size:0.75rem; color:#566'>"
                            + "  ".join(f"`{t}`" for t in topics[:4])
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                    # MBTI tip
                    if mbti_tip:
                        st.markdown(
                            f"<div style='font-size:0.73rem; color:#5a7aaa; margin-top:6px'>"
                            f"🧠 <b>{mbti}:</b> {mbti_tip}</div>",
                            unsafe_allow_html=True,
                        )

    st.markdown("---")
    st.subheader("Field Impact on LLM Output")
    st.dataframe(
        pd.DataFrame({
            "Field": ["persona", "profession", "interested_topics", "mbti", "country", "bio", "age", "gender"],
            "Impact": ["Highest", "High", "High", "Medium", "Medium", "Medium", "Low", "Low"],
            "What it controls": [
                "Worldview, biases, speaking style, stake in the market",
                "Domain vocabulary and what the agent focuses on",
                "Content surfaces when searching or checking trends",
                "Tone: analytical vs emotional, decisive vs cautious",
                "Cultural/legal frame — Emirati vs expat perspectives",
                "First-person voice and self-description style",
                "Minor effect on risk tolerance phrasing",
                "Minor effect on pronoun use",
            ],
        }),
        width='stretch',
        hide_index=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# PAGE: Configure & Run
# ──────────────────────────────────────────────────────────────────────────────

elif page == "Configure & Run":
    profiles = load_profiles()

    st.title("Configure & Run Simulation")
    st.markdown(
        "Build your simulation configuration: choose the market event, tune simulation "
        "settings, optionally inject dynamic context or edit agent personas, then run."
    )

    # ── STEP 1: Market Event ──────────────────────────────────────────────────
    st.subheader("Step 1 — Market Event")
    st.markdown(
        '<div class="info-box">'
        "The event description is the biggest driver of specificity in agent responses. "
        "It becomes Agent 0's seed post — the first thing all 14 agents read. "
        "<b>Include specific numbers, district names, and policy references</b> for richer outputs. "
        "Vague events produce vague discussions."
        "</div>",
        unsafe_allow_html=True,
    )

    preset_choice = st.selectbox(
        "Load a preset event",
        options=["(none)"] + list(EVENT_PRESETS.keys()),
        help="Presets cover different Dubai RE scenarios. You can edit the text after loading.",
    )

    # Keep event text in session state so edits survive re-renders
    if "event_text" not in st.session_state:
        st.session_state["event_text"] = ""
    if preset_choice != "(none)" and st.session_state.get("_last_preset") != preset_choice:
        st.session_state["event_text"] = EVENT_PRESETS[preset_choice]
        st.session_state["_last_preset"] = preset_choice

    event_text: str = st.text_area(
        "Event description",
        height=110,
        placeholder=(
            "Describe the market event in plain language. Include specific numbers, "
            "districts, or policy changes for richer agent responses.\n"
            "Example: 'Dubai property prices surge 15% YoY, new Golden Visa rules announced.'"
        ),
        help=(
            "This text is posted verbatim by 'UAE Property News' (Agent 0) as the seed post. "
            "All 14 persona agents read it in Round 1."
        ),
        key="event_text",
    )

    if event_text.strip():
        with st.expander("Preview: what Agent 0 will actually post"):
            st.markdown(
                f"<div class='post-bubble' style='border-color:#f39c12'>"
                f"<div class='post-header'>UAE Property News &nbsp;"
                f"<span class='post-meta'>@uae_property_news · Seed post (Round 0)</span></div>"
                f"🚨 BREAKING — Dubai Real Estate Market Update:<br>"
                f"{event_text}<br><br>"
                f"<span style='color:#556'>#DubaiRealEstate #UAEProperty #PropertyMarket</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── STEP 2: Simulation Settings ───────────────────────────────────────────
    st.subheader("Step 2 — Simulation Settings")

    col_rounds, col_help = st.columns([2, 3])
    with col_rounds:
        num_rounds = st.slider(
            "Number of LLM rounds",
            min_value=1, max_value=5, value=3, step=1,
            help=(
                "Each round: all 14 agents read the full platform state and each independently "
                "choose an action. Rounds stack — Round 2 agents see Round 1 posts, etc."
            ),
        )
    with col_help:
        round_guide = {
            1: ("Round 1 only", "Initial reactions to the seed post. No back-and-forth.", "#f39c12"),
            2: ("Rounds 1–2", "First reactions + first wave of replies and engagement.", "#f39c12"),
            3: ("Rounds 1–3", "Full debate arc — positions evolve, disagreements surface.", "#2ecc71"),
            4: ("Rounds 1–4", "Extended debate, more position shifting, ~56 API calls.", "#f39c12"),
            5: ("Rounds 1–5", "Maximum richness, strongest narrative arc, ~70 API calls.", "#e74c3c"),
        }
        label, desc, col = round_guide[num_rounds]
        st.markdown(
            f"<div class='info-box' style='margin-top:12px'>"
            f"<b style='color:{col}'>{label}</b> — {desc}<br>"
            f"<span style='color:#556; font-size:0.8rem'>"
            f"≈ {num_rounds * 14} Azure OpenAI calls total (14 agents × {num_rounds} rounds + stance extraction)"
            f"</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # ── STEP 3: Dynamic Context Injection ─────────────────────────────────────
    st.subheader("Step 3 — Dynamic Context Injection (optional)")
    st.markdown(
        '<div class="info-box">'
        "By default, agents only know their static profile and what gets posted during the "
        "simulation. Context injection lets you add live market data or breaking news to make "
        "responses more specific and time-sensitive. Choose a method or leave as None."
        "</div>",
        unsafe_allow_html=True,
    )

    context_method = st.radio(
        "Injection method",
        options=[
            "None — static profiles only",
            "Method A — Enrich seed post with live market data",
            "Method B — Inject market snapshot into every agent's persona",
            "Method C — Mid-simulation breaking news event",
            "Method D — Private briefings for specific agents",
        ],
        label_visibility="collapsed",
    )

    method_a_data: dict = {}
    method_b_data: dict = {}
    method_c_event: str = ""
    method_c_round: int = 1
    method_d_briefings: dict[str, str] = {}

    if "Method A" in context_method:
        st.markdown(
            '<div class="info-box">'
            "<b>Method A — Enrich seed post</b><br>"
            "Appends a live market snapshot to the seed post. Since every agent reads the "
            "seed post in Round 1, these figures propagate automatically into all their "
            "reasoning. <b>Simplest method — no code changes needed.</b>"
            "</div>",
            unsafe_allow_html=True,
        )
        ma1, ma2, ma3 = st.columns(3)
        with ma1:
            method_a_data["weekly_transactions"] = st.number_input(
                "DLD weekly transactions", value=2847, step=100,
                help="Number of property transactions registered with DLD in the last 7 days.",
            )
        with ma2:
            method_a_data["downtown_psf"] = st.number_input(
                "Downtown median price/sqft (AED)", value=2850, step=50,
                help="Median sale price per sq ft in Downtown Dubai from latest DLD data.",
            )
        with ma3:
            method_a_data["avg_rate"] = st.number_input(
                "Average mortgage rate (%)", value=6.25, step=0.05, format="%.2f",
                help="Current average all-in mortgage rate (EIBOR + bank margin) in UAE.",
            )
        if any(method_a_data.values()):
            with st.expander("Preview enriched seed post"):
                st.markdown(
                    f"<div class='post-bubble' style='border-color:#3d9'>"
                    f"<div class='post-header'>UAE Property News · Enriched with market data</div>"
                    f"{event_text}<br><br>"
                    f"📊 Today's market snapshot:<br>"
                    f"&nbsp;&nbsp;• DLD transactions (last 7 days): {method_a_data['weekly_transactions']:,}<br>"
                    f"&nbsp;&nbsp;• Median price/sqft (Downtown): AED {method_a_data['downtown_psf']:,.0f}<br>"
                    f"&nbsp;&nbsp;• Average mortgage rate: {method_a_data['avg_rate']:.2f}%"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    elif "Method B" in context_method:
        st.markdown(
            '<div class="info-box">'
            "<b>Method B — Per-agent persona injection</b><br>"
            "Prepends a market snapshot to <em>every agent's persona</em> before the simulation "
            "starts. Unlike Method A (seed post only), Method B embeds the data directly into each "
            "agent's system prompt — so even an agent who ignores the seed post will still have the "
            "figures in their instructions. Useful for ensuring all agents share a consistent baseline."
            "</div>",
            unsafe_allow_html=True,
        )
        mb1, mb2, mb3 = st.columns(3)
        with mb1:
            method_b_data["villa_avg"] = st.number_input(
                "Dubai avg villa price (AED)", value=4_200_000, step=50_000,
                help="Average villa transaction price across Dubai (all areas).",
            )
        with mb2:
            method_b_data["jvc_yield"] = st.number_input(
                "JVC rental yield (%)", value=7.2, step=0.1, format="%.1f",
                help="Current gross rental yield for JVC apartments.",
            )
        with mb3:
            method_b_data["listings"] = st.number_input(
                "Active DLD portal listings", value=48_320, step=1000,
                help="Number of active property listings on the DLD portal.",
            )
        with st.expander("Preview: what gets prepended to each agent's persona"):
            st.code(
                f"[MARKET CONTEXT — {datetime.now().strftime('%d %b %Y')}]\n"
                f"Dubai average villa price: AED {method_b_data.get('villa_avg', 4200000):,.0f}\n"
                f"Rental yield (JVC): {method_b_data.get('jvc_yield', 7.2):.1f}%\n"
                f"Active listings (DLD portal): {method_b_data.get('listings', 48320):,}\n\n"
                "...followed by the agent's original persona...",
                language="text",
            )

    elif "Method C" in context_method:
        st.markdown(
            '<div class="info-box">'
            "<b>Method C — Mid-simulation breaking news</b><br>"
            "Injects a second manual post mid-simulation. This simulates a breaking news event that "
            "forces agents to revise their initial positions. Agents in subsequent rounds will react "
            "to both the original seed AND this breaking news, producing a richer, more dynamic arc. "
            "Works best injected after Round 1 so agents have already formed initial positions."
            "</div>",
            unsafe_allow_html=True,
        )
        method_c_event = st.text_area(
            "Breaking news text",
            placeholder="⚠️ URGENT: UAE Central Bank just raised interest rates 50bps. Mortgage rates now expected to exceed 7%.",
            height=90,
            help="Posted by Agent 0 (UAE Property News) after the chosen round.",
        )
        method_c_round = st.selectbox(
            "Inject after Round",
            options=[1, 2],
            index=0,
            format_func=lambda x: f"Round {x} — {'most impact (agents just formed initial positions)' if x == 1 else 'later impact (agents are mid-debate)'}",
            help="When to inject the breaking news. After Round 1 is the most common choice.",
        )
        st.markdown(
            '<div class="warn-box">'
            "⚠️ <b>Note:</b> Method C requires modifying <code>real_estate_oasis.py</code> directly "
            "to add the mid-sim injection. The code snippet from the design guide needs to be inserted "
            "in the round loop. This UI will show you the code to add."
            "</div>",
            unsafe_allow_html=True,
        )
        if method_c_event.strip():
            with st.expander("Code to add to real_estate_oasis.py"):
                st.code(
                    f"""# Inside run_simulation(), in the round loop:
for round_num in range(1, NUM_ROUNDS + 1):
    # ... existing round code ...
    await env.step(all_actions)

    # Mid-simulation event injection (Method C)
    if round_num == {method_c_round}:
        breaking_post = {repr(method_c_event)}
        await env.step({{
            seed_agent: ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={{"content": breaking_post}},
            )
        }})
        print(f"  Injected breaking news after Round {method_c_round}.")
""",
                    language="python",
                )

    elif "Method D" in context_method:
        st.markdown(
            '<div class="info-box">'
            "<b>Method D — Private briefings</b><br>"
            "Gives specific agents <em>private</em> information not visible to others. "
            "For example: the developer knows his units are 85% sold; the fund manager has heard "
            "of a large institutional exit. This creates information asymmetry and realistic "
            "strategic behaviour — agents with inside knowledge will argue more confidently "
            "without explicitly revealing their source."
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("**Add private briefings to specific agents (leave blank to skip):**")
        for profile in profiles[1:]:  # skip Agent 0 (seeder)
            name    = profile.get("realname", "")
            role    = profile.get("profession", "")
            country = profile.get("country", "")
            flag    = COUNTRY_FLAGS.get(country, "🌐")
            briefing = st.text_area(
                f"{flag} {name} — {role}",
                key=f"briefing_{name}",
                placeholder=f"Private briefing for {name}. Information only they know…",
                height=68,
            )
            if briefing.strip():
                method_d_briefings[name] = briefing.strip()

        if method_d_briefings:
            st.markdown(
                f'<div class="success-box">'
                f"✅ Private briefings set for: <b>{', '.join(method_d_briefings.keys())}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── STEP 4: Persona Editor ────────────────────────────────────────────────
    st.subheader("Step 4 — Agent Persona Editor (optional)")
    st.markdown(
        '<div class="info-box">'
        "Modify agent personas before running. Changes here are applied to a temporary "
        "profile file — the original <code>user_data_realestate_15.json</code> is not touched. "
        "Persona is the <b>highest-impact field</b>: it shapes worldview, biases, and speaking style."
        "</div>",
        unsafe_allow_html=True,
    )

    edited_personas: dict[str, str] = {}

    with st.expander("Edit agent personas", expanded=False):
        st.markdown(
            '<div class="warn-box">'
            "💡 <b>Writing strong personas:</b> Answer 5 questions — "
            "(1) What is their stake? &nbsp;"
            "(2) What do they fear? &nbsp;"
            "(3) What do they champion? &nbsp;"
            "(4) How do they speak? &nbsp;"
            "(5) What biases do they have?"
            "</div>",
            unsafe_allow_html=True,
        )
        for i, p in enumerate(profiles[1:], start=1):
            name    = p.get("realname", "")
            role    = p.get("profession", "")
            country = p.get("country", "")
            flag    = COUNTRY_FLAGS.get(country, "🌐")
            mbti    = p.get("mbti", "")
            current = p.get("persona", "")

            new_persona: str = st.text_area(
                f"{flag} {name} — {role}",
                value=current,
                height=100,
                key=f"persona_edit_{i}",
                help=f"MBTI {mbti}: {MBTI_DESCRIPTIONS.get(mbti, '')}",
            )
            if new_persona.strip() != current.strip():
                edited_personas[name] = new_persona.strip()

        if edited_personas:
            st.markdown(
                f'<div class="success-box">'
                f"✏️ {len(edited_personas)} persona(s) modified: <b>{', '.join(edited_personas.keys())}</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── STEP 5: Review & Run ──────────────────────────────────────────────────
    st.subheader("Step 5 — Review & Run")

    with st.expander("Configuration summary", expanded=True):
        summary_rows = [
            ("Event", (event_text[:100] + "…") if len(event_text) > 100 else event_text or "(not set)"),
            ("Rounds", str(num_rounds)),
            ("Context injection", context_method.split(" — ")[0]),
            ("Persona edits", ", ".join(edited_personas.keys()) if edited_personas else "None"),
            ("Private briefings", ", ".join(method_d_briefings.keys()) if method_d_briefings else "None"),
        ]
        for label, val in summary_rows:
            st.markdown(
                f"<div style='display:flex; gap:16px; margin:3px 0; font-size:0.86rem'>"
                f"<span style='color:#558; min-width:140px'>{label}</span>"
                f"<span style='color:#bbc'>{val}</span></div>",
                unsafe_allow_html=True,
            )

    st.markdown("**Run via Docker (recommended — full CAMEL-AI stack):**")
    st.code("docker compose run --rm realestate", language="bash")
    st.caption("When prompted, paste your event text. Transcripts save to ./transcripts/ on the host.")

    st.markdown("**Or run directly with Python (requires camel-oasis and .env configured):**")
    direct_cmd = f'python real_estate_oasis.py --rounds {num_rounds} --event "{event_text[:60]}{"..." if len(event_text) > 60 else ""}"'
    st.code(direct_cmd, language="bash")

    st.markdown("---")

    if not event_text.strip():
        st.warning("Enter an event description in Step 1 before running.")
    else:
        col_btn, col_req = st.columns([1, 2])
        with col_btn:
            run_btn = st.button(
                "▶  Run Simulation",
                type="primary",
                width='stretch',
                help="Runs real_estate_oasis.py directly from this UI.",
            )
        with col_req:
            st.markdown(
                '<div class="warn-box" style="margin:0">'
                "⚠️ <b>Requirements for direct run:</b> "
                "<code>.env</code> file with <code>AZURE_OPENAI_ENDPOINT</code>, "
                "<code>AZURE_OPENAI_API_KEY</code>, <code>AZURE_OPENAI_DEPLOYMENT_NAME</code>. "
                "<code>camel-oasis</code> installed. "
                "For Docker users, use the command above."
                "</div>",
                unsafe_allow_html=True,
            )

        if run_btn:
            # Build modified profiles (persona edits + Method B + Method D)
            run_profiles = [dict(p) for p in profiles]
            needs_temp = bool(edited_personas or method_d_briefings or "Method B" in context_method)

            if needs_temp:
                for p in run_profiles:
                    name = p.get("realname", "")
                    if "Method B" in context_method and method_b_data:
                        p["persona"] = (
                            f"[MARKET CONTEXT — {datetime.now().strftime('%d %b %Y')}]\n"
                            f"Dubai average villa price: AED {method_b_data['villa_avg']:,.0f}\n"
                            f"Rental yield (JVC): {method_b_data['jvc_yield']:.1f}%\n"
                            f"Active listings (DLD portal): {method_b_data['listings']:,}\n\n"
                            + p["persona"]
                        )
                    if name in edited_personas:
                        p["persona"] = edited_personas[name]
                    if name in method_d_briefings:
                        p["persona"] += (
                            f"\n\n[PRIVATE BRIEFING — CONFIDENTIAL]\n{method_d_briefings[name]}"
                        )
                temp_path = Path("./data/user_data_realestate_temp.json")
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(run_profiles, f, indent=2)
                profile_path_to_use = str(temp_path)
            else:
                profile_path_to_use = str(PROFILE_PATH)

            # Build event string (Method A enrichment)
            run_event = event_text
            if "Method A" in context_method and method_a_data:
                run_event = (
                    f"{event_text}\n\n"
                    f"📊 Today's market snapshot:\n"
                    f"  • DLD transactions (last 7 days): {method_a_data['weekly_transactions']:,}\n"
                    f"  • Median price/sqft (Downtown): AED {method_a_data['downtown_psf']:,.0f}\n"
                    f"  • Average mortgage rate: {method_a_data['avg_rate']:.2f}%"
                )

            # Launch subprocess in background thread
            out_queue: queue.Queue = queue.Queue()
            sim_thread = threading.Thread(
                target=run_simulation_subprocess,
                args=(run_event, num_rounds, profile_path_to_use, out_queue),
                daemon=True,
            )
            sim_thread.start()

            st.markdown("**Simulation output:**")
            output_area = st.empty()
            status_area = st.empty()
            output_lines: list[str] = []

            with st.spinner("Running simulation… (may take several minutes)"):
                while sim_thread.is_alive() or not out_queue.empty():
                    try:
                        kind, val = out_queue.get(timeout=0.3)
                        if kind == "line":
                            output_lines.append(val)
                            output_area.code("\n".join(output_lines[-60:]), language="text")
                        elif kind == "done":
                            if val == 0:
                                status_area.success("Simulation complete! Switch to Results Viewer to analyse.")
                            else:
                                status_area.error(f"Simulation exited with code {val}.")
                            break
                        elif kind == "error":
                            status_area.error(f"Launch error: {val}")
                            break
                    except queue.Empty:
                        continue

            sim_thread.join()

            # Clean up temp profile
            if needs_temp and temp_path.exists():
                temp_path.unlink()


# ──────────────────────────────────────────────────────────────────────────────
# PAGE: Results Viewer
# ──────────────────────────────────────────────────────────────────────────────

elif page == "Results Viewer":
    st.title("Results Viewer")

    transcripts = list_transcripts()
    if not transcripts:
        st.info(
            "No simulation transcripts found. "
            "Run a simulation via **Configure & Run** or via Docker, then return here."
        )
        st.stop()

    # Transcript selector
    transcript_names = [p.name for p in transcripts]
    selected_name    = st.selectbox(
        "Select transcript",
        options=transcript_names,
        help="Sorted newest-first. Each file is one full simulation run.",
    )
    selected_path = transcripts[transcript_names.index(selected_name)]
    data          = load_transcript(selected_path)

    # Header
    st.markdown(f"**Event:** {data.get('event', 'N/A')}")
    ts = data.get("timestamp", "")
    try:
        dt = datetime.strptime(ts, "%Y%m%d_%H%M%S")
        st.caption(f"Run: {dt.strftime('%d %b %Y %H:%M:%S')} · {data.get('num_agents', 0)} agents")
    except (ValueError, TypeError):
        st.caption(f"Timestamp: {ts}")

    st.markdown("---")

    # ── Stance tally ──────────────────────────────────────────────────────────
    st.subheader("Stance Distribution")
    tally   = data.get("tally", {})
    n_total = data.get("num_agents", 1) or 1

    sc1, sc2, sc3 = st.columns(3)
    for col, stance, d_color in [
        (sc1, "positive", "normal"),
        (sc2, "neutral",  "off"),
        (sc3, "negative", "inverse"),
    ]:
        n   = tally.get(stance, 0)
        pct = n / n_total * 100
        col.metric(stance.capitalize(), f"{n} agents", f"{pct:.0f}%", delta_color=d_color)

    # Stacked bar chart
    if any(tally.values()):
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches

            fig, ax = plt.subplots(figsize=(9, 1.3))
            clrs = {"positive": "#2ecc71", "neutral": "#f39c12", "negative": "#e74c3c"}
            left = 0
            for stance in ("positive", "neutral", "negative"):
                n = tally.get(stance, 0)
                if n > 0:
                    w = n / n_total * 100
                    ax.barh(0, w, left=left, color=clrs[stance], height=0.75)
                    if w > 5:
                        ax.text(left + w / 2, 0, str(n), ha="center", va="center",
                                color="white", fontsize=9, fontweight="bold")
                    left += w
            ax.set_xlim(0, 100)
            ax.set_yticks([])
            ax.set_xlabel("% of agents", color="white", fontsize=9)
            ax.set_facecolor("#0e1117")
            fig.patch.set_facecolor("#0e1117")
            ax.tick_params(colors="white")
            for sp in ax.spines.values():
                sp.set_edgecolor("#333")
            patches = [mpatches.Patch(color=clrs[s], label=s.capitalize()) for s in clrs]
            ax.legend(handles=patches, loc="upper right", fontsize=8,
                      facecolor="#1e2130", labelcolor="white", edgecolor="#444")
            st.pyplot(fig)
            plt.close(fig)
        except ImportError:
            pass

    st.markdown("---")

    # ── Three tabs: Stances | Conversation | Export ───────────────────────────
    tab_stances, tab_conv, tab_export = st.tabs(
        ["Agent Stances", "Conversation Thread", "Export / Raw Data"]
    )

    agents_list = data.get("agents", [])
    agent_map   = {a["agent_index"]: a for a in agents_list}

    with tab_stances:
        st.subheader("Per-Agent Stance Breakdown")

        col_sort, col_filter = st.columns([2, 2])
        with col_sort:
            sort_by = st.selectbox("Sort by", ["Stance", "Confidence (high→low)", "Agent index"])
        with col_filter:
            stance_filter = st.multiselect(
                "Filter by stance", ["positive", "neutral", "negative"],
                default=["positive", "neutral", "negative"],
            )

        display_agents = [a for a in agents_list if a.get("stance") in stance_filter]
        if sort_by == "Stance":
            order = {"positive": 0, "neutral": 1, "negative": 2}
            display_agents = sorted(display_agents, key=lambda a: order.get(a.get("stance", "neutral"), 1))
        elif sort_by == "Confidence (high→low)":
            display_agents = sorted(display_agents, key=lambda a: a.get("confidence", 0), reverse=True)

        for agent in display_agents:
            stance   = agent.get("stance", "neutral")
            name     = agent.get("name", "Unknown")
            username = agent.get("username", "")
            role     = agent.get("role", "")
            conf     = agent.get("confidence", 0)
            reason   = agent.get("reason", "")
            posts    = agent.get("posts", [])

            icon   = {"positive": "📈", "neutral": "📊", "negative": "📉"}.get(stance, "•")
            border = {"positive": "#2ecc71", "neutral": "#f39c12", "negative": "#e74c3c"}.get(stance, "#888")
            bg     = {"positive": "#0b1e14", "neutral": "#1e1804", "negative": "#1e0808"}.get(stance, "#111")

            with st.expander(
                f"{icon} **{name}** (@{username}) — {role} — {stance.upper()} ({conf:.0%})"
            ):
                info_col, reason_col = st.columns([1, 2])
                with info_col:
                    st.markdown(
                        f"<div style='font-size:0.85rem; line-height:2'>"
                        f"<b>Stance:</b> {stance.upper()}<br>"
                        f"<b>Confidence:</b> {conf:.0%}<br>"
                        f"<b>Posts:</b> {len(posts)}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with reason_col:
                    st.markdown(
                        f"<div style='background:{bg}; border-radius:6px; padding:10px 12px; "
                        f"border-left:3px solid {border}; font-size:0.84rem; color:#bbc'>"
                        f"<b>Reason:</b> {reason}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                if posts:
                    st.markdown(f"**Posts during simulation ({len(posts)}):**")
                    for i, post in enumerate(posts, 1):
                        st.markdown(
                            f"<div class='post-bubble' style='border-color:{border}'>"
                            f"<div class='post-meta'>Post {i}</div>"
                            f"{post}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("No posts recorded — agent may have taken DO_NOTHING actions.")

    with tab_conv:
        st.subheader("Conversation Thread")
        st.markdown(
            '<div class="info-box">'
            "Posts are shown in the order they appear in the SQLite database if available, "
            "otherwise in JSON transcript order. Posts from different rounds are interleaved "
            "by agent ID (not strict time order unless the DB stores timestamps)."
            "</div>",
            unsafe_allow_html=True,
        )

        if DB_PATH.exists():
            conn = sqlite3.connect(str(DB_PATH))
            cur  = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [r[0].lower() for r in cur.fetchall()]

            all_posts: list[tuple[int, str, str]] = []
            for table in tables:
                if "post" not in table and "comment" not in table:
                    continue
                cur.execute(f"PRAGMA table_info({table})")
                cols = {r[1].lower(): r[1] for r in cur.fetchall()}
                content_col = next((cols[c] for c in ("content", "text", "body", "message") if c in cols), None)
                user_col    = next((cols[c] for c in ("user_id", "author_id", "agent_id") if c in cols), None)
                if not content_col or not user_col:
                    continue
                time_col = next((v for k, v in cols.items() if "time" in k or "creat" in k), None)
                order_clause = f"ORDER BY {time_col}" if time_col else ""
                cur.execute(
                    f"SELECT {user_col}, {content_col} FROM {table} "
                    f"WHERE {content_col} IS NOT NULL {order_clause}"
                )
                for uid, text in cur.fetchall():
                    all_posts.append((int(uid), str(text), table))
            conn.close()

            if all_posts:
                for uid, text, table in all_posts:
                    a       = agent_map.get(uid, {})
                    name    = a.get("name", f"Agent {uid}")
                    uname   = a.get("username", str(uid))
                    stance  = a.get("stance", "neutral")
                    border  = {"positive": "#2ecc71", "neutral": "#f39c12", "negative": "#e74c3c"}.get(stance, "#4a90d9")
                    icon    = {"positive": "📈", "neutral": "📊", "negative": "📉"}.get(stance, "💬")
                    st.markdown(
                        f"<div class='post-bubble' style='border-color:{border}'>"
                        f"<div class='post-header'>{icon} {name} "
                        f"<span class='post-meta'>@{uname} · table: {table}</span></div>"
                        f"{text}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
            else:
                st.info("No posts found in the SQLite DB tables. The DB may be from a different run.")
        else:
            st.info("SQLite DB not found — showing posts from JSON transcript (not time-ordered).")
            for agent in agents_list:
                stance  = agent.get("stance", "neutral")
                border  = {"positive": "#2ecc71", "neutral": "#f39c12", "negative": "#e74c3c"}.get(stance, "#4a90d9")
                icon    = {"positive": "📈", "neutral": "📊", "negative": "📉"}.get(stance, "💬")
                for post in agent.get("posts", []):
                    st.markdown(
                        f"<div class='post-bubble' style='border-color:{border}'>"
                        f"<div class='post-header'>{icon} {agent.get('name', '')} "
                        f"<span class='post-meta'>@{agent.get('username', '')}</span></div>"
                        f"{post}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    with tab_export:
        st.subheader("Export & Raw Data")

        dl1, dl2 = st.columns(2)
        with dl1:
            st.download_button(
                "⬇ Download JSON transcript",
                data=json.dumps(data, indent=2).encode("utf-8"),
                file_name=selected_name,
                mime="application/json",
                width='stretch',
            )
        with dl2:
            # Build CSV from agent stances
            csv_rows = []
            for a in agents_list:
                csv_rows.append({
                    "agent_index": a.get("agent_index"),
                    "name": a.get("name"),
                    "username": a.get("username"),
                    "role": a.get("role"),
                    "stance": a.get("stance"),
                    "confidence": a.get("confidence"),
                    "reason": a.get("reason"),
                    "num_posts": len(a.get("posts", [])),
                })
            csv_df  = pd.DataFrame(csv_rows)
            csv_str = csv_df.to_csv(index=False)
            st.download_button(
                "⬇ Download stance CSV",
                data=csv_str.encode("utf-8"),
                file_name=selected_name.replace(".json", ".csv"),
                mime="text/csv",
                width='stretch',
            )

        with st.expander("Stance table"):
            st.dataframe(csv_df, width='stretch', hide_index=True)

        with st.expander("Raw JSON"):
            st.json(data, expanded=False)
