"""
social_ui.py — Streamlit UI for the AI Social Media Platform
Live post streaming, agent roster, transcript viewer, and simulation settings.

Run:
    streamlit run social_ui.py
    # or via Docker:
    docker compose --profile social-ui up
"""
from __future__ import annotations

import queue
import re
import threading
from pathlib import Path
from typing import Optional

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Page config (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Social Platform",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Agent display metadata
# ─────────────────────────────────────────────────────────────────────────────

AGENT_META = [
    {"name": "Alex",   "handle": "@alex_the_optimist",  "avatar": "☀️",  "color": "#f0c040", "style": "Optimist — silver linings, upbeat, exclamation points"},
    {"name": "Morgan", "handle": "@morgan_skeptic",      "avatar": "🔍",  "color": "#999999", "style": "Skeptic — demands sources, citation needed"},
    {"name": "Jordan", "handle": "@jordan_philosopher",  "avatar": "🦉",  "color": "#40d0e0", "style": "Philosopher — big ideas, Plato/Nietzsche, paradoxes"},
    {"name": "Sam",    "handle": "@sam_pragmatist",      "avatar": "🔧",  "color": "#50c060", "style": "Pragmatist — actionable steps, no fluff"},
    {"name": "Riley",  "handle": "@riley_empath",        "avatar": "💙",  "color": "#5090d0", "style": "Empath — human emotional cost, compassion"},
    {"name": "Casey",  "handle": "@casey_contrarian",    "avatar": "😈",  "color": "#e05050", "style": "Contrarian — devil's advocate, flips consensus"},
    {"name": "Taylor", "handle": "@taylor_expert",       "avatar": "📊",  "color": "#c050c0", "style": "Expert — data, statistics, research"},
    {"name": "Blake",  "handle": "@blake_humorist",      "avatar": "😂",  "color": "#d0a030", "style": "Humorist — wit, sarcasm, absurd analogies"},
    {"name": "Quinn",  "handle": "@quinn_activist",      "avatar": "✊",  "color": "#70e070", "style": "Activist — systemic justice, calls to action"},
    {"name": "Drew",   "handle": "@drew_analyst",        "avatar": "⚖️",  "color": "#e0e0e0", "style": "Analyst — balanced, pros/cons, synthesis"},
]

AGENT_COLOR  = {a["handle"]: a["color"]  for a in AGENT_META}
AGENT_AVATAR = {a["handle"]: a["avatar"] for a in AGENT_META}

# ─────────────────────────────────────────────────────────────────────────────
# Settings defaults & session state initialization
# ─────────────────────────────────────────────────────────────────────────────

SETTINGS_DEFAULTS: dict = {
    "cfg_turns":           5,
    "cfg_max_tokens":      5000,
    "cfg_word_limit":      80,
    "cfg_reply_threading": True,
    "cfg_auto_save":       False,
    "cfg_transcript_dir":  "./transcripts",
    "cfg_deployment":      "",
    "cfg_api_version":     "2024-12-01-preview",
}
for _a in AGENT_META:
    SETTINGS_DEFAULTS[f"cfg_agent_{_a['handle']}"] = True

for _k, _v in SETTINGS_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .post-card {
        border-radius: 10px;
        padding: 12px 15px;
        margin-bottom: 10px;
        background: #131826;
        font-size: 0.87rem;
        line-height: 1.65;
        color: #c8cce0;
    }
    .post-header {
        font-weight: 600;
        margin-bottom: 6px;
        font-size: 0.9rem;
    }
    .post-meta {
        color: #505878;
        font-size: 0.73rem;
    }
    .agent-card {
        background: #151a2e;
        border-radius: 10px;
        padding: 13px 15px;
        margin-bottom: 6px;
        font-size: 0.83rem;
        line-height: 1.6;
    }
    .round-header {
        background: #1a1d30;
        border-radius: 6px;
        padding: 8px 14px;
        margin: 18px 0 10px 0;
        color: #8899cc;
        font-size: 0.82rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-align: center;
    }
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
    .cfg-badge {
        display: inline-block;
        background: #1a2540;
        border: 1px solid #2a3a60;
        border-radius: 5px;
        padding: 3px 9px;
        margin: 2px 3px;
        font-size: 0.75rem;
        color: #8899cc;
    }
    .settings-section {
        background: #0e1422;
        border: 1px solid #1e2840;
        border-radius: 10px;
        padding: 18px 20px;
        margin-bottom: 18px;
    }
    .settings-label {
        font-size: 0.78rem;
        color: #607898;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner="Loading Azure OpenAI client…")
def _load_sim():
    """Import social_platform once; caches the Azure client across reruns."""
    try:
        import social_platform as sp
        return sp
    except SystemExit:
        return None


def _list_transcripts() -> list[Path]:
    d = Path(st.session_state.get("cfg_transcript_dir", "./transcripts"))
    if not d.exists():
        return []
    return sorted(d.glob("transcript_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)


def _active_agent_count() -> int:
    return sum(1 for a in AGENT_META if st.session_state.get(f"cfg_agent_{a['handle']}", True))


def _render_post_card(
    avatar: str,
    name: str,
    handle: str,
    color: str,
    turn: str,
    turns_total: str,
    post_num: str,
    reply_to: Optional[str],
    content: str,
) -> None:
    reply_line = (
        f"<br><span class='post-meta'>↳ replying to {reply_to}</span>"
        if reply_to else ""
    )
    st.markdown(
        f"<div class='post-card' style='border-left: 3px solid {color}'>"
        f"<div class='post-header'>{avatar} "
        f"<span style='color:{color}'>{name}</span>&nbsp;"
        f"<span class='post-meta'>{handle} · Turn {turn}/{turns_total}"
        f"{(' · Post #' + post_num) if post_num else ''}"
        f"</span>{reply_line}</div>"
        f"{content}"
        f"</div>",
        unsafe_allow_html=True,
    )


def _build_transcript_text(topic: str, posts: list, turns_total: int = 5) -> str:
    lines = [
        "AI Social Media Platform — Transcript\n",
        f"Topic: {topic}\n",
        "=" * 60 + "\n\n",
    ]
    for i, p in enumerate(posts, 1):
        reply = f" (replying to {p.reply_to})" if p.reply_to else ""
        lines.append(
            f"[Post #{i}] {p.agent.name} {p.agent.handle} — Turn {p.turn}/{turns_total}{reply}\n"
        )
        lines.append(p.content + "\n\n")
    return "".join(lines)


def _settings_badges_html() -> str:
    n_agents = _active_agent_count()
    turns    = st.session_state.cfg_turns
    deploy   = st.session_state.cfg_deployment or "env default"
    reply    = "on" if st.session_state.cfg_reply_threading else "off"
    wlimit   = st.session_state.cfg_word_limit
    maxtok   = st.session_state.cfg_max_tokens
    badges = [
        f"<span class='cfg-badge'>🤖 {n_agents} agents</span>",
        f"<span class='cfg-badge'>🔄 {turns} rounds</span>",
        f"<span class='cfg-badge'>💬 {n_agents * turns} total posts</span>",
        f"<span class='cfg-badge'>✏️ {wlimit}w limit</span>",
        f"<span class='cfg-badge'>🔢 {maxtok} max tokens</span>",
        f"<span class='cfg-badge'>↩️ replies {reply}</span>",
        f"<span class='cfg-badge'>🚀 {deploy}</span>",
    ]
    return "".join(badges)


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🌐 AI Social Platform")
    st.caption("10-agent AI discussion simulator")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        options=["Platform", "Start Discussion", "Transcript Viewer", "Settings"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    n_tx = len(_list_transcripts())
    st.markdown(
        f"<div style='font-size:0.8rem; color:#666; line-height:2.2'>"
        f"💬 &nbsp;Saved discussions: <b style='color:#999'>{n_tx}</b><br>"
        f"🤖 &nbsp;Active agents: <b style='color:#999'>{_active_agent_count()}/10</b><br>"
        f"🔄 &nbsp;Rounds per run: <b style='color:#999'>{st.session_state.cfg_turns}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.markdown(
        """
        <div style='font-size:0.74rem; color:#555; line-height:1.9'>
        <b>Quick start</b><br>
        1️⃣ &nbsp;<em>Start Discussion</em> → enter topic<br>
        2️⃣ &nbsp;Watch agents debate live<br>
        3️⃣ &nbsp;Download or save transcript<br>
        4️⃣ &nbsp;<em>Transcript Viewer</em> → replay<br>
        ⚙️ &nbsp;<em>Settings</em> → configure simulation
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")
    st.caption("Powered by Azure OpenAI")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Platform (Overview)
# ─────────────────────────────────────────────────────────────────────────────

if page == "Platform":
    st.title("AI Social Media Platform")
    st.markdown(
        "**AI agents** with distinct personalities debate any topic you provide. "
        "Each agent reads the full conversation history before responding. "
        "Watch the discussion evolve in real-time as each model call completes."
    )

    n_active = _active_agent_count()
    turns    = st.session_state.cfg_turns
    c1, c2, c3 = st.columns(3)
    c1.metric("Active Agents", str(n_active), f"of 10 configured")
    c2.metric("Turns / agent", str(turns), f"{n_active * turns} total posts")
    c3.metric("LLM rounds", str(turns), "Round-robin across agents")

    st.markdown("---")
    st.subheader("The 10 Agents")

    for row_start in range(0, len(AGENT_META), 2):
        col1, col2 = st.columns(2)
        for col, a in zip([col1, col2], AGENT_META[row_start: row_start + 2]):
            active = st.session_state.get(f"cfg_agent_{a['handle']}", True)
            opacity = "1.0" if active else "0.35"
            badge = "" if active else "&nbsp;<span style='font-size:0.7rem;color:#666'>(disabled)</span>"
            with col:
                st.markdown(
                    f"<div class='agent-card' style='border-left: 4px solid {a['color']}; opacity:{opacity}'>"
                    f"<span style='font-size:1.25rem'>{a['avatar']}</span>&nbsp;"
                    f"<b style='color:{a['color']}'>{a['name']}</b>{badge}"
                    f"&nbsp;<span style='color:#505878; font-size:0.78rem'>{a['handle']}</span><br>"
                    f"<span style='color:#8899aa; font-size:0.8rem'>{a['style']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    st.subheader("How It Works")
    st.code(
        """
  ┌──────────────────────────────────────────────────────────────────┐
  │                      Platform Flow                               │
  │                                                                  │
  │  1.  You enter any topic (news, ethics, policy, current events)  │
  │  2.  Round 1: all active agents give their opening take          │
  │  3.  Rounds 2–N: each agent reads the full history and replies   │
  │      — positions evolve, debates form, alliances shift           │
  │  4.  Posts stream live as each model call completes              │
  │  5.  Save or download the transcript when done                   │
  └──────────────────────────────────────────────────────────────────┘
        """,
        language="text",
    )

    with st.expander("Suggested topics"):
        st.markdown(
            """
- `the ethics of artificial intelligence`
- `universal basic income`
- `should social media be regulated?`
- `climate change policy`
- `the role of religion in modern society`
- `cryptocurrency and the future of money`
- any current news event or geopolitical situation
            """
        )

    st.markdown("---")
    st.subheader("Personality Guide")
    import pandas as pd
    st.dataframe(
        pd.DataFrame([
            {
                "Agent": f"{a['avatar']} {a['name']}",
                "Handle": a["handle"],
                "Personality": a["style"],
                "Active": "✅" if st.session_state.get(f"cfg_agent_{a['handle']}", True) else "⬜",
            }
            for a in AGENT_META
        ]),
        width='stretch',
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Start Discussion
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Start Discussion":
    st.title("Start a Discussion")

    n_active = _active_agent_count()
    if n_active < 2:
        st.error(
            "At least 2 agents must be active. "
            "Go to **Settings → Agent Roster** to enable more agents."
        )
        st.stop()

    # Settings summary banner
    st.markdown(
        '<div class="info-box">'
        "<b>Current configuration</b>&nbsp;&nbsp;"
        + _settings_badges_html()
        + "<br><span style='font-size:0.77rem; color:#607898; margin-top:4px; display:block'>"
        "Change these in ⚙️ Settings</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    topic = st.text_input(
        "Discussion topic",
        placeholder="e.g. 'universal basic income', 'the ethics of AI', 'war in Iran'",
        key="discussion_topic",
    )

    col_btn, col_note = st.columns([1, 3])
    with col_btn:
        run_btn = st.button(
            "▶  Start Discussion",
            type="primary",
            width='stretch',
            disabled=not bool(topic.strip()),
        )
    with col_note:
        st.markdown(
            "<div style='color:#556; font-size:0.82rem; padding-top:8px'>"
            "Requires Azure OpenAI credentials in <code>.env</code>. "
            f"~{n_active * st.session_state.cfg_turns} API calls per discussion "
            f"({n_active} agents × {st.session_state.cfg_turns} rounds)."
            "</div>",
            unsafe_allow_html=True,
        )

    if run_btn and topic.strip():
        sp = _load_sim()
        if sp is None:
            st.error(
                "Failed to load simulation. "
                "Check that AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are set in .env."
            )
            st.stop()

        # Snapshot settings at run time (thread-safe)
        sim_cfg = {
            "turns":           st.session_state.cfg_turns,
            "max_tokens":      st.session_state.cfg_max_tokens,
            "word_limit":      st.session_state.cfg_word_limit,
            "reply_threading": st.session_state.cfg_reply_threading,
            "deployment":      st.session_state.cfg_deployment or None,
            "auto_save":       st.session_state.cfg_auto_save,
            "transcript_dir":  Path(st.session_state.cfg_transcript_dir),
            "active_handles":  [
                a["handle"] for a in AGENT_META
                if st.session_state.get(f"cfg_agent_{a['handle']}", True)
            ],
        }

        post_queue: queue.Queue = queue.Queue()

        def _run_discussion() -> None:
            try:
                agents = [a for a in sp.AGENTS if a.handle in sim_cfg["active_handles"]]
                turns  = sim_cfg["turns"]
                agent_turns: dict = {a.handle: 0 for a in agents}
                all_posts: list = []

                for rnd in range(1, turns + 1):
                    post_queue.put(("round", (rnd, turns)))
                    for agent in agents:
                        agent_turns[agent.handle] += 1
                        t = agent_turns[agent.handle]
                        try:
                            p = sp.generate_post(
                                agent, topic.strip(), all_posts, t,
                                max_tokens=sim_cfg["max_tokens"],
                                deployment=sim_cfg["deployment"],
                                word_limit=sim_cfg["word_limit"],
                                reply_threading=sim_cfg["reply_threading"],
                                active_agents=agents,
                            )
                            all_posts.append(p)
                            post_queue.put(("post", p))
                        except Exception as exc:
                            post_queue.put(("warn", f"{agent.name}: {exc}"))
                post_queue.put(("done", all_posts))
            except Exception as exc:
                post_queue.put(("error", str(exc)))

        thread = threading.Thread(target=_run_discussion, daemon=True)
        thread.start()

        st.markdown(f"### 🌐 *{topic}*")
        status_slot = st.empty()
        feed        = st.container()
        collected: list = []
        _turns_total = str(sim_cfg["turns"])

        with st.spinner("Discussion running…"):
            while thread.is_alive() or not post_queue.empty():
                try:
                    kind, val = post_queue.get(timeout=0.3)
                except queue.Empty:
                    continue

                if kind == "round":
                    rnd, total = val
                    with feed:
                        st.markdown(
                            f"<div class='round-header'>── Round {rnd} of {total} ──</div>",
                            unsafe_allow_html=True,
                        )

                elif kind == "post":
                    p = val
                    collected.append(p)
                    color  = AGENT_COLOR.get(p.agent.handle, "#888")
                    avatar = AGENT_AVATAR.get(p.agent.handle, "💬")
                    status_slot.info(
                        f"{avatar} {p.agent.name} posted · "
                        f"Turn {p.turn}/{_turns_total} · Post #{len(collected)}"
                    )
                    with feed:
                        _render_post_card(
                            avatar, p.agent.name, p.agent.handle, color,
                            str(p.turn), _turns_total, str(len(collected)),
                            p.reply_to, p.content,
                        )

                elif kind == "warn":
                    with feed:
                        st.warning(f"⚠️ {val}")

                elif kind == "done":
                    collected = val
                    status_slot.success(
                        f"✅ Discussion complete — {len(collected)} posts across "
                        f"{sim_cfg['turns']} rounds"
                    )
                    break

                elif kind == "error":
                    status_slot.error(f"Error: {val}")
                    break

        thread.join()

        if collected:
            st.markdown("---")
            transcript_text = _build_transcript_text(
                topic.strip(), collected, turns_total=sim_cfg["turns"]
            )
            fname = f"transcript_{topic.strip()[:30].replace(' ', '_')}.txt"

            # Auto-save if enabled
            if sim_cfg["auto_save"]:
                sim_cfg["transcript_dir"].mkdir(parents=True, exist_ok=True)
                (sim_cfg["transcript_dir"] / fname).write_text(transcript_text, encoding="utf-8")
                st.success(f"Auto-saved: {sim_cfg['transcript_dir'] / fname}")

            dl_col, save_col = st.columns(2)
            with dl_col:
                st.download_button(
                    "⬇ Download transcript",
                    data=transcript_text.encode("utf-8"),
                    file_name=fname,
                    mime="text/plain",
                    width='stretch',
                )
            with save_col:
                if not sim_cfg["auto_save"]:
                    if st.button(
                        f"💾 Save to {sim_cfg['transcript_dir']}/",
                        width='stretch',
                    ):
                        sim_cfg["transcript_dir"].mkdir(parents=True, exist_ok=True)
                        (sim_cfg["transcript_dir"] / fname).write_text(
                            transcript_text, encoding="utf-8"
                        )
                        st.success(f"Saved: {fname}")
                else:
                    st.info("Auto-save is enabled — transcript was saved automatically.")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Transcript Viewer
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Transcript Viewer":
    st.title("Transcript Viewer")

    txs = _list_transcripts()
    if not txs:
        st.info(
            "No saved transcripts yet. "
            "Start a discussion and save it, or run `social_platform.py` via Docker."
        )
        st.stop()

    names    = [p.name for p in txs]
    sel_name = st.selectbox("Select transcript", names, help="Sorted newest-first")
    sel_path = txs[names.index(sel_name)]
    raw      = sel_path.read_text(encoding="utf-8")

    topic_display = ""
    for line in raw.splitlines():
        if line.startswith("Topic:"):
            topic_display = line[6:].strip()
            break

    st.markdown(f"**Topic:** {topic_display}")
    st.caption(f"File: {sel_path.name}")
    st.markdown("---")

    # Dynamic turn count — handle both "/5" and "/N" formats
    POST_RE = re.compile(
        r"^\[Post #(\d+)\] (\w+) (@\S+) — Turn (\d+)/(\d+)(?: \(replying to (@\S+)\))?$"
    )

    parsed: list[dict] = []
    cur_match: Optional[re.Match] = None
    cur_lines: list[str] = []

    SKIP_PREFIXES = ("AI Social Media", "Topic:", "=====")

    for line in raw.splitlines():
        m = POST_RE.match(line)
        if m:
            if cur_match is not None:
                parsed.append({"m": cur_match, "content": "\n".join(cur_lines).strip()})
            cur_match = m
            cur_lines = []
        elif cur_match is not None:
            if not any(line.startswith(pfx) for pfx in SKIP_PREFIXES):
                cur_lines.append(line)

    if cur_match is not None:
        parsed.append({"m": cur_match, "content": "\n".join(cur_lines).strip()})

    if not parsed:
        st.warning("Could not parse posts from this transcript — showing raw text.")
        st.text(raw)
        st.stop()

    prev_turn: Optional[str] = None
    for item in parsed:
        m          = item["m"]
        post_num   = m.group(1)
        name       = m.group(2)
        handle     = m.group(3)
        turn       = m.group(4)
        turns_tot  = m.group(5)
        reply_to   = m.group(6)
        content    = item["content"]

        if turn != prev_turn:
            prev_turn = turn
            st.markdown(
                f"<div class='round-header'>── Round {turn} of {turns_tot} ──</div>",
                unsafe_allow_html=True,
            )

        color  = AGENT_COLOR.get(handle, "#888888")
        avatar = AGENT_AVATAR.get(handle, "💬")
        _render_post_card(avatar, name, handle, color, turn, turns_tot, post_num, reply_to, content)

    st.markdown("---")
    st.download_button(
        "⬇ Download transcript",
        data=raw.encode("utf-8"),
        file_name=sel_path.name,
        mime="text/plain",
    )


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Settings
# ─────────────────────────────────────────────────────────────────────────────

elif page == "Settings":
    st.title("⚙️ Settings")
    st.markdown(
        "All settings apply to the **next discussion run**. "
        "They persist for this browser session and reset on page refresh."
    )
    st.markdown("---")

    # ── Simulation ─────────────────────────────────────────────────────────────
    st.subheader("Simulation")
    sim_c1, sim_c2 = st.columns(2)
    with sim_c1:
        st.slider(
            "Turns per Agent",
            min_value=1,
            max_value=10,
            step=1,
            key="cfg_turns",
            help=(
                "How many rounds each agent participates. "
                "Default: 5. Total posts = active agents × turns."
            ),
        )
    with sim_c2:
        st.slider(
            "Word Limit per Reply",
            min_value=20,
            max_value=300,
            step=10,
            key="cfg_word_limit",
            help=(
                "Maximum words each agent is instructed to write per post. "
                "Default: 80. Higher values produce richer but slower discussions."
            ),
        )

    tog_c1, tog_c2 = st.columns(2)
    with tog_c1:
        st.toggle(
            "Reply Threading",
            key="cfg_reply_threading",
            help=(
                "When on, agents tag and directly reply to the most recent other agent. "
                "Turn off for independent, parallel takes without cross-replies."
            ),
        )
    with tog_c2:
        st.toggle(
            "Auto-save Transcripts",
            key="cfg_auto_save",
            help=(
                "Automatically save the transcript to disk when a discussion completes. "
                "Saves to the configured Transcript Directory."
            ),
        )

    n_active = _active_agent_count()
    turns    = st.session_state.cfg_turns
    st.markdown(
        f"<div class='settings-label'>"
        f"With current settings: <b>{n_active} agents</b> × <b>{turns} turns</b> = "
        f"<b>{n_active * turns} API calls</b> per discussion"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Model ─────────────────────────────────────────────────────────────────
    st.subheader("Model")

    mod_c1, mod_c2 = st.columns(2)
    with mod_c1:
        st.text_input(
            "Deployment Override",
            key="cfg_deployment",
            placeholder="leave blank to use AZURE_DEPLOYMENT_NAME from .env",
            help=(
                "Azure OpenAI deployment name. "
                "Overrides the AZURE_DEPLOYMENT_NAME / AZURE_OPENAI_DEPLOYMENT_NAME "
                "environment variable. Leave blank to use the .env value."
            ),
        )
    with mod_c2:
        st.text_input(
            "API Version",
            key="cfg_api_version",
            help=(
                "Azure OpenAI REST API version string. "
                "Default: 2024-12-01-preview. "
                "Note: changing this requires a page refresh to take effect "
                "(the client is initialized once per session)."
            ),
        )

    st.slider(
        "Max Tokens per Response",
        min_value=100,
        max_value=32000,
        step=100,
        key="cfg_max_tokens",
        help=(
            "Maximum completion tokens allowed per agent response. "
            "Default: 5000. Reasoning models (o1/o3) use these for chain-of-thought, "
            "so higher values are needed. For gpt-4o/gpt-4.1, 500 is usually sufficient."
        ),
    )

    st.markdown("---")

    # ── Agent Roster ──────────────────────────────────────────────────────────
    st.subheader("Agent Roster")

    n_active = _active_agent_count()
    if n_active < 2:
        st.error("At least 2 agents must be active for a discussion to run.")
    else:
        st.markdown(
            f"<div class='settings-label'>"
            f"{n_active} of {len(AGENT_META)} agents active</div>",
            unsafe_allow_html=True,
        )

    for row_start in range(0, len(AGENT_META), 2):
        cols = st.columns(2)
        for col, a in zip(cols, AGENT_META[row_start: row_start + 2]):
            with col:
                st.checkbox(
                    f"{a['avatar']} **{a['name']}**  `{a['handle']}`",
                    key=f"cfg_agent_{a['handle']}",
                    help=a["style"],
                )

    st.markdown("---")

    # ── Export ────────────────────────────────────────────────────────────────
    st.subheader("Export")

    st.text_input(
        "Transcript Directory",
        key="cfg_transcript_dir",
        help=(
            "Directory where transcripts are saved. "
            "Relative paths are resolved from the working directory "
            "(/app inside Docker). Default: ./transcripts"
        ),
    )
    st.markdown(
        f"<div class='settings-label'>"
        f"Currently: <code>{Path(st.session_state.cfg_transcript_dir).resolve()}</code>"
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ── Reset ─────────────────────────────────────────────────────────────────
    rst_col, info_col = st.columns([1, 3])
    with rst_col:
        if st.button("↩ Reset to Defaults", type="secondary", width='stretch'):
            for k, v in SETTINGS_DEFAULTS.items():
                st.session_state[k] = v
            st.success("All settings reset to defaults.")
            st.rerun()
    with info_col:
        st.markdown(
            "<div style='color:#556; font-size:0.82rem; padding-top:8px'>"
            "Resets all simulation, model, agent, and export settings to their default values."
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("Current Configuration Summary")
    st.markdown(_settings_badges_html(), unsafe_allow_html=True)
