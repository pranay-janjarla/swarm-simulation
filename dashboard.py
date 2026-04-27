# dashboard.py — Streamlit interactive dashboard for the swarm simulation
from __future__ import annotations

import json
import io
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx
import numpy as np
import pandas as pd
import streamlit as st

from config import (
    BEHAVIOR_STATES, NARRATIVE_TYPES,
    STATE_COLORS, NARRATIVE_COLORS,
    STANCE_TYPES, STANCE_COLORS,
    EVENT_PRESETS, NUM_AGENTS,
)
from event import Event
from model import SwarmModel

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Swarm AI Simulation",
    page_icon="🧠",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Sidebar — controls
# ---------------------------------------------------------------------------

st.sidebar.title("🧠 Swarm AI Simulation")
st.sidebar.markdown("Configure the triggering event and run 1 000 agents.")

# --- Preset selector ---
preset_choice = st.sidebar.selectbox(
    "Event Preset",
    options=["Custom"] + list(EVENT_PRESETS.keys()),
)
preset_vals = EVENT_PRESETS.get(preset_choice, {})

# --- Event sliders ---
st.sidebar.markdown("---")
st.sidebar.markdown("**Event Parameters**")

severity = st.sidebar.slider(
    "Severity", 0.0, 1.0,
    float(preset_vals.get("severity", 0.6)), 0.05,
    help="How catastrophic is the event? (0 = trivial, 1 = catastrophic)",
)
believability = st.sidebar.slider(
    "Believability", 0.0, 1.0,
    float(preset_vals.get("believability", 0.7)), 0.05,
    help="How credible is the information? (0 = rumor, 1 = confirmed fact)",
)
spread_speed = st.sidebar.slider(
    "Spread Speed", 0.0, 1.0,
    float(preset_vals.get("spread_speed", 0.5)), 0.05,
    help="How fast does information reach agents?",
)
authority_response = st.sidebar.slider(
    "Authority Response", 0.0, 1.0,
    float(preset_vals.get("authority_response", 0.4)), 0.05,
    help="Strength of official / authoritative response",
)
event_type = st.sidebar.selectbox(
    "Event Type",
    ["social", "disaster", "economic", "political"],
    index=["social", "disaster", "economic", "political"].index(
        preset_vals.get("event_type", "social")
    ),
)
event_name = st.sidebar.text_input(
    "Event Name", preset_choice if preset_choice != "Custom" else "Custom Event"
)

# --- Simulation settings ---
st.sidebar.markdown("---")
st.sidebar.markdown("**Simulation Settings**")

num_ticks  = st.sidebar.slider("Ticks", 10, 300, 100, 10)
num_agents = st.sidebar.slider("Agents", 100, NUM_AGENTS, NUM_AGENTS, 100)
seed       = st.sidebar.number_input("Random Seed", value=42, step=1)

run_button = st.sidebar.button("▶  Run Simulation", type="primary", width='stretch')

# ---------------------------------------------------------------------------
# Run simulation
# ---------------------------------------------------------------------------

if run_button:
    event = Event(
        name               = event_name,
        severity           = severity,
        believability      = believability,
        spread_speed       = spread_speed,
        authority_response = authority_response,
        event_type         = event_type,
        tick_of_onset      = 0,
    )

    progress_bar = st.progress(0, text="Initialising model…")

    model = SwarmModel(event=event, num_agents=num_agents, seed=int(seed))

    for tick in range(num_ticks):
        model.step()
        if tick % max(1, num_ticks // 50) == 0:
            progress_bar.progress(
                (tick + 1) / num_ticks,
                text=f"Tick {tick+1}/{num_ticks}",
            )

    progress_bar.progress(1.0, text="Done!")

    # Store results in session_state
    st.session_state["model_df"]    = model.get_model_dataframe()
    st.session_state["agent_df"]    = model.get_agent_dataframe()
    st.session_state["state_counts"]  = model.state_counts()
    st.session_state["narr_counts"]   = model.narrative_counts()
    st.session_state["stance_counts"] = model.stance_counts()
    st.session_state["graph"]        = model.graph
    st.session_state["agents"]      = list(model.schedule.agents)
    st.session_state["event"]       = event
    st.session_state["num_agents"]  = num_agents
    st.session_state["num_ticks"]   = num_ticks


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------

if "model_df" not in st.session_state:
    st.info("Configure the event in the sidebar and press **Run Simulation** to begin.")
    st.stop()

model_df      = st.session_state["model_df"]
agent_df      = st.session_state["agent_df"]
state_counts  = st.session_state["state_counts"]
narr_counts   = st.session_state["narr_counts"]
stance_counts = st.session_state["stance_counts"]
graph         = st.session_state["graph"]
agents        = st.session_state["agents"]
event         = st.session_state["event"]
n_agents      = st.session_state["num_agents"]
n_ticks       = st.session_state["num_ticks"]

st.title(f"Results — {event.name}")
st.markdown(
    f"**{n_agents} agents** · **{n_ticks} ticks** · "
    f"severity `{event.severity}` · believability `{event.believability}` · "
    f"spread `{event.spread_speed}` · authority `{event.authority_response}`"
)

# ---------------------------------------------------------------------------
# PRIMARY: Public Stance Distribution
# ---------------------------------------------------------------------------

st.subheader("Public Stance — How agents feel about the event")

# Three big KPI cards: positive / neutral / negative
sc1, sc2, sc3 = st.columns(3)
stance_cols_map = {"positive": sc1, "neutral": sc2, "negative": sc3}
for stance, col in stance_cols_map.items():
    n   = stance_counts.get(stance, 0)
    pct = n / n_agents * 100
    col.metric(
        label=stance.capitalize(),
        value=f"{n} agents",
        delta=f"{pct:.1f}%",
        delta_color="normal" if stance == "positive" else ("off" if stance == "neutral" else "inverse"),
    )

# Stance over time — primary line chart
stance_time_cols = [f"frac_stance_{s}" for s in STANCE_TYPES]
stance_df = model_df[stance_time_cols].copy()
stance_df.columns = STANCE_TYPES
stance_df.index.name = "Tick"

fig_s, ax_s = plt.subplots(figsize=(12, 3))
for stance in STANCE_TYPES:
    ax_s.fill_between(
        stance_df.index,
        stance_df[stance] * 100,
        alpha=0.25,
        color=STANCE_COLORS[stance],
    )
    ax_s.plot(
        stance_df.index,
        stance_df[stance] * 100,
        label=stance,
        color=STANCE_COLORS[stance],
        linewidth=2.5,
    )
ax_s.set_xlabel("Tick")
ax_s.set_ylabel("% of Agents")
ax_s.set_ylim(0, 100)
ax_s.set_facecolor("#0e1117")
fig_s.patch.set_facecolor("#0e1117")
ax_s.tick_params(colors="white")
ax_s.xaxis.label.set_color("white")
ax_s.yaxis.label.set_color("white")
for spine in ax_s.spines.values():
    spine.set_edgecolor("#444")
ax_s.legend(loc="upper right", fontsize=10,
            facecolor="#1e2130", labelcolor="white", edgecolor="#444")
st.pyplot(fig_s)
plt.close(fig_s)

st.markdown("---")

# ---------------------------------------------------------------------------
# Row 1: KPI cards (behavior states — secondary)
# ---------------------------------------------------------------------------

cols = st.columns(5)
key_states = ["calm", "panic", "conspiratorial", "comply", "adapt"]
for col, s in zip(cols, key_states):
    n   = state_counts.get(s, 0)
    pct = n / n_agents * 100
    col.metric(s.capitalize(), f"{n}", f"{pct:.1f}%")

# ---------------------------------------------------------------------------
# Row 2: Behavior state line chart + Narrative stacked bar
# ---------------------------------------------------------------------------

col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("Behavior State Proportions Over Time")

    # Build DataFrame of state fractions per tick
    state_cols = [f"frac_{s}" for s in BEHAVIOR_STATES]
    plot_df    = model_df[state_cols].copy()
    plot_df.columns = BEHAVIOR_STATES
    plot_df.index.name = "Tick"

    fig, ax = plt.subplots(figsize=(9, 4))
    for state in BEHAVIOR_STATES:
        ax.plot(
            plot_df.index,
            plot_df[state] * 100,
            label=state,
            color=STATE_COLORS[state],
            linewidth=1.8,
        )
    ax.set_xlabel("Tick")
    ax.set_ylabel("% of Agents")
    ax.set_ylim(0, 100)
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.set_facecolor("#0e1117")
    fig.patch.set_facecolor("#0e1117")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.legend(loc="upper right", fontsize=7, ncol=2,
              facecolor="#1e2130", labelcolor="white", edgecolor="#444")
    st.pyplot(fig)
    plt.close(fig)

with col_right:
    st.subheader("Narrative Sentiment at Final Tick")

    narr_labels = NARRATIVE_TYPES
    narr_values = [narr_counts.get(n, 0) for n in narr_labels]
    narr_colors = [NARRATIVE_COLORS[n] for n in narr_labels]

    fig2, ax2 = plt.subplots(figsize=(5, 4))
    bars = ax2.bar(narr_labels, narr_values, color=narr_colors, edgecolor="#333")
    ax2.set_ylabel("Agent Count")
    ax2.set_facecolor("#0e1117")
    fig2.patch.set_facecolor("#0e1117")
    ax2.tick_params(colors="white")
    ax2.yaxis.label.set_color("white")
    for spine in ax2.spines.values():
        spine.set_edgecolor("#444")
    for bar, v in zip(bars, narr_values):
        ax2.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(narr_values) * 0.01,
            str(v), ha="center", va="bottom", color="white", fontsize=9,
        )
    st.pyplot(fig2)
    plt.close(fig2)

# ---------------------------------------------------------------------------
# Row 3: Final state bar chart + Network graph
# ---------------------------------------------------------------------------

col3, col4 = st.columns([2, 3])

with col3:
    st.subheader("Final Behavior State Distribution")

    state_labels = BEHAVIOR_STATES
    state_values = [state_counts.get(s, 0) for s in state_labels]
    state_clrs   = [STATE_COLORS[s] for s in state_labels]

    fig3, ax3 = plt.subplots(figsize=(5, 5))
    ax3.barh(state_labels[::-1], state_values[::-1], color=state_clrs[::-1])
    ax3.set_xlabel("Agent Count")
    ax3.set_facecolor("#0e1117")
    fig3.patch.set_facecolor("#0e1117")
    ax3.tick_params(colors="white")
    ax3.xaxis.label.set_color("white")
    for spine in ax3.spines.values():
        spine.set_edgecolor("#444")
    st.pyplot(fig3)
    plt.close(fig3)

with col4:
    st.subheader("Social Network Snapshot (200 nodes)")

    # Subgraph: pick top-200 nodes by degree for a readable graph
    degrees   = sorted(graph.degree, key=lambda x: x[1], reverse=True)
    top_nodes = [n for n, _ in degrees[:200]]
    sub_g     = graph.subgraph(top_nodes)

    node_colors = [
        STATE_COLORS[agents[n].behavior_state]
        for n in sub_g.nodes()
    ]

    fig4, ax4 = plt.subplots(figsize=(7, 5))
    pos = nx.spring_layout(sub_g, seed=42, k=0.6)
    nx.draw_networkx(
        sub_g, pos=pos, ax=ax4,
        node_color=node_colors, node_size=25,
        edge_color="#333", width=0.4,
        with_labels=False,
    )
    ax4.set_facecolor("#0e1117")
    fig4.patch.set_facecolor("#0e1117")
    # Legend
    legend_patches = [
        mpatches.Patch(color=STATE_COLORS[s], label=s)
        for s in BEHAVIOR_STATES
    ]
    ax4.legend(
        handles=legend_patches, loc="upper left", fontsize=6,
        facecolor="#1e2130", labelcolor="white", edgecolor="#444",
        ncol=2,
    )
    st.pyplot(fig4)
    plt.close(fig4)

# ---------------------------------------------------------------------------
# Download exports
# ---------------------------------------------------------------------------

st.markdown("---")
st.subheader("Export Data")

dcol1, dcol2 = st.columns(2)

with dcol1:
    # CSV — model-level tick data
    csv_buf = io.StringIO()
    model_df.index.name = "tick"
    model_df.to_csv(csv_buf)
    st.download_button(
        "⬇ Download tick-level CSV",
        data=csv_buf.getvalue().encode("utf-8"),
        file_name=f"swarm_{event.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
        width='stretch',
    )

with dcol2:
    # JSON — agent snapshot at final tick
    last_tick = agent_df.index.get_level_values("Step").max()
    final_df  = agent_df.xs(last_tick, level="Step")
    payload = {
        "meta": {
            "ticks":      n_ticks,
            "num_agents": n_agents,
            "event": {
                "name":               event.name,
                "severity":           event.severity,
                "believability":      event.believability,
                "spread_speed":       event.spread_speed,
                "authority_response": event.authority_response,
                "event_type":         event.event_type,
            },
        },
        "final_stance_counts":    stance_counts,
        "final_state_counts":     state_counts,
        "final_narrative_counts": narr_counts,
        "agents": final_df.reset_index().to_dict(orient="records"),
    }
    json_str = json.dumps(payload, indent=2)
    st.download_button(
        "⬇ Download agent JSON",
        data=json_str.encode("utf-8"),
        file_name=f"swarm_{event.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        width='stretch',
    )

# ---------------------------------------------------------------------------
# Raw data table (collapsible)
# ---------------------------------------------------------------------------

with st.expander("Show raw tick-level data"):
    display_df = model_df.copy()
    display_df.index.name = "Tick"
    # Rename columns for readability
    display_df.columns = [c.replace("frac_narr_", "narr_").replace("frac_", "") for c in display_df.columns]
    st.dataframe(display_df.style.format("{:.3f}"), height=300)
