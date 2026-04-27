# Dubai Real Estate OASIS Simulation — Agent Design Guide

A reference document covering how the 15-agent CAMEL-AI OASIS simulation is configured,
how personality and context work, and how to extend the system.

---

## 1. Why Were Some Agents Configured as Emirati?

### Short answer
The simulation is modelling the **Dubai real estate market**, where UAE nationals (Emiratis)
are a distinct and important participant group — they have different legal rights, financial
access, cultural motivations, and regulatory protections from expat buyers. Leaving them out
would produce a skewed picture of market sentiment.

### Which agents are Emirati in this simulation

| Agent | Role | Why Emirati matters |
|---|---|---|
| Ayesha Al-Mansouri | First-time buyer | UAE nationals get Emirati Housing Authority loans and preferential mortgage rates — her anxiety is different from an expat buyer's |
| Omar Al-Rashid | RERA Compliance Officer | RERA (Real Estate Regulatory Agency) staff are typically Emiratis; he has genuine regulatory authority |
| Hassan Al-Farsi | Developer CEO | Mid-size Emirati developers are a real power bloc in the Dubai off-plan market |
| Khalid Al-Zaabi | Landlord | UAE nationals can hold property in all areas (not just freehold zones), giving different perspective |
| Layla Mohammed | Urban Planner (Dubai Municipality) | Dubai Municipality planners are overwhelmingly Emirati; their concern for affordability of nationals is a real policy tension |

### Where the Emirati identity comes from in the code

The profile JSON uses three fields together to establish nationality-based persona:

```json
{
  "realname": "Ayesha Al-Mansouri",
  "country": "UAE",
  "profession": "Marketing Executive",
  "persona": "First-time buyer, Emirati woman saving for her first apartment.
              Anxious about affordability and whether now is a good time to buy.
              Easily swayed by market sentiment..."
}
```

When OASIS passes this profile to the LLM, it constructs a system prompt that includes all
fields. The LLM uses `country`, name, and `persona` together to generate nationality-consistent
responses (e.g., referencing Emirati Housing Authority, MBZ City, or Tanween developments
rather than generic property content).

**The `persona` field is the most important** — the `country` field alone would not be enough.
A bare `"country": "UAE"` entry produces generic responses. The `persona` narrative is what
makes the agent argue, question, and reason from the Emirati perspective.

---

## 2. Why Did Agents Produce Specific Values, Districts, and Numbers in Their Posts?

### Three sources of specificity

**Source A — The seed event itself**
Agent 0 (`UAE Property News`) posts the event description verbatim as the seed post.
If the event contains numbers like "15% YoY" or mentions "Palm Jumeirah", those values
propagate into all subsequent agent responses because every agent reads the seed post
in Round 1.

Default event used in the simulation:
```
Dubai residential property prices surge 15% year-on-year, driven by record
Golden Visa applications and constrained supply in prime districts
(Palm Jumeirah, Downtown, Dubai Marina).
```
This single sentence injects: `15%`, `Golden Visa`, `Palm Jumeirah`, `Downtown`,
`Dubai Marina` into the shared platform context.

**Source B — LLM pre-training knowledge**
GPT-4 / GPT-5 was trained on vast amounts of Dubai property content — news articles,
forum posts, DLD reports, RERA announcements. The model has genuine factual knowledge
about typical Dubai price ranges, popular districts, developer names (EMAAR, NAKHEEL,
DAMAC), typical rental yields (5–7%), and Golden Visa thresholds (AED 2M). When an
agent is told to play a property investor, the LLM draws on this real-world knowledge
to produce realistic-sounding figures.

**Source C — The persona field primes domain-specific language**
Each agent's `persona` contains specific terms that the LLM latches onto:

- Raj's persona mentions `"JVC, Dubai South, Business Bay"` → he references these
  districts in posts
- Marcus's persona mentions `"$800M GCC portfolio"`, `"basis points"` → he uses
  institutional finance language
- Zara's persona mentions `"bought 2019, selling 2024, 40% up"` → she references
  her personal capital gain story

The combination of seed event numbers + LLM market knowledge + persona priming produces
responses that look like they were written by actual market participants.

---

## 3. How to Develop Unique Personality Parameters for Each Agent

OASIS reads the profile JSON and converts each object into a system prompt for the LLM.
The fields that matter most, in order of impact:

### Field reference table

| Field | Type | Impact | Design guidance |
|---|---|---|---|
| `persona` | string | **Highest** | Multi-sentence narrative describing worldview, biases, speaking style, and stakes in the market. This is what most shapes LLM output. |
| `profession` | string | High | Determines domain vocabulary and what the agent focuses on |
| `interested_topics` | string[] | High | OASIS uses these to decide what content the agent surfaces when searching or trending |
| `mbti` | string | Medium | Affects tone: INTJ = analytical/cold, ESFP = emotional/enthusiastic, ISFJ = cautious/helpful |
| `country` | string | Medium | Sets cultural and legal frame of reference |
| `bio` | string | Medium | The Twitter/Reddit-style self-description — shapes first-person voice |
| `age` | int | Low | Minor effect on risk tolerance phrasing |
| `gender` | string | Low | Minor effect on pronoun use |

### How to write a strong `persona` field

A good persona answers five questions:

1. **What is their stake in the market?** (buyer/seller/investor/regulator)
2. **What do they fear?** (losing money, regulatory risk, missing the boat)
3. **What do they champion?** (yields, affordability, data, long-term vision)
4. **How do they speak?** (numbers-only, emotional, policy language, hashtag-heavy)
5. **What biases do they have?** (bullish by necessity, cynical by experience)

**Weak persona (produces generic output):**
```json
"persona": "Real estate investor who likes Dubai property."
```

**Strong persona (produces specific, distinctive output):**
```json
"persona": "Seasoned Indian expat property investor with 8 units across JVC, Dubai South,
and Business Bay. Calculates yield obsessively. Bullish on Dubai long-term but always
looking for the right entry price. Dismisses panic sellers as short-sighted.
Speaks in numbers and ROI. Never emotional."
```

### MBTI as a communication style dial

| MBTI type | Resulting LLM communication style |
|---|---|
| ENTJ | Decisive, numbers-first, dismissive of emotion |
| ISFJ | Cautious, helpful, asks clarifying questions |
| ENTP | Contrarian, challenges assumptions, sees opportunity in chaos |
| INFP | Emotionally driven, asks others for reassurance, torn |
| INTJ | Strategic, data-only, distrusts hype |
| ESFP | Enthusiastic, shares personal story, uses exclamation marks |

### Ensuring agents disagree

For a productive simulation, design agents so their **stakes conflict**:

- Price rise = good for: sellers, developers, landlords, investors already in
- Price rise = bad for: first-time buyers, renters, urban planners, compliance officers
- Neutral/analytical: brokers, fund managers, REIT analysts

This structural conflict means agents will naturally produce opposing stances without
you having to hardcode disagreement.

---

## 4. How to Add Dynamic Context to Each Agent

"Dynamic context" means runtime information that changes per simulation run — live market
data, today's news, a specific scenario parameter. Currently each agent only knows:
(a) their static profile and (b) what other agents post during the simulation.

### Method A — Enrich the seed event (simplest, no code change needed)

Instead of a bare event description, inject live data into the seed post content in
`run_simulation()`:

```python
# real_estate_oasis.py — run_simulation()

# Fetch live data before simulation
live_data = fetch_live_market_data()   # your own function

seed_content = (
    f"🚨 BREAKING — Dubai Real Estate Market Update:\n"
    f"{event_description}\n\n"
    f"📊 Today's market snapshot:\n"
    f"  • DLD transactions (last 7 days): {live_data['weekly_transactions']:,}\n"
    f"  • Median price/sqft (Downtown): AED {live_data['downtown_psf']:,.0f}\n"
    f"  • Average mortgage rate: {live_data['avg_rate']:.2f}%\n\n"
    f"#DubaiRealEstate #UAEProperty #PropertyMarket"
)
```

Every agent reads this seed post in Round 1, so the live figures propagate into all
agent responses automatically.

### Method B — Per-agent context injection (adds a `context` field to profiles)

Extend `_build_oasis_model()` or the profile loading to prepend a dynamic briefing
into each agent's system prompt. One way: add a `"context"` field to the JSON profile
at runtime before loading it.

```python
# Before calling generate_reddit_agent_graph():

with open(PROFILE_PATH, encoding="utf-8") as f:
    profiles = json.load(f)

market_snapshot = fetch_market_snapshot()  # dict with current stats

for profile in profiles:
    # Prepend dynamic context to the persona field
    profile["persona"] = (
        f"[MARKET CONTEXT — {datetime.now().strftime('%d %b %Y')}]\n"
        f"Dubai average villa price: AED {market_snapshot['villa_avg']:,.0f}\n"
        f"Rental yield (JVC): {market_snapshot['jvc_yield']:.1f}%\n"
        f"Active listings (DLD portal): {market_snapshot['listings']:,}\n\n"
        + profile["persona"]
    )

# Write the enriched profiles to a temp file
enriched_path = "./data/user_data_realestate_enriched.json"
with open(enriched_path, "w") as f:
    json.dump(profiles, f)

agent_graph = await generate_reddit_agent_graph(
    enriched_path,   # use enriched version
    model=model,
    available_actions=AVAILABLE_ACTIONS,
)
```

### Method C — Mid-simulation event injection (breaking news effect)

Inject a second manual post mid-simulation to simulate a breaking news event partway
through the conversation:

```python
# After Round 1 completes, inject a second event
if round_num == 1:
    breaking_post = "⚠️ URGENT: UAE Central Bank just raised interest rates 50bps..."
    await env.step({
        seed_agent: ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": breaking_post},
        )
    })
```

Agents in Round 2 and 3 will now react to both the original event AND the mid-game
breaking news, producing a more dynamic conversation arc.

### Method D — Agent-specific knowledge (different agents get different private info)

Some agents should know things others don't (e.g., the developer knows his units are
near sold out; the fund manager knows about a large institutional exit). Add a
`"private_briefing"` field per profile:

```json
{
  "realname": "Hassan Al-Farsi",
  "persona": "...",
  "private_briefing": "Your Creek Harbour project Phase 2 is 85% sold off-plan.
                       You are quietly preparing to launch Phase 3 at 20% higher prices."
}
```

Then in the profile loading step, merge `private_briefing` into `persona` only for
that agent.

---

## 5. Basic UI to View Agent Conversations

The OASIS simulation produces two data sources you can visualise:

1. **SQLite DB** (`./transcripts/oasis_realestate.db`) — all posts, comments, likes,
   follows in real time
2. **JSON transcript** (`./transcripts/realestate_stance_*.json`) — post-simulation,
   per-agent posts + stance classification

### Build a Streamlit viewer

Create `conversation_viewer.py` in the project root:

```python
"""
conversation_viewer.py — Browse OASIS simulation results in a web UI
Run: streamlit run conversation_viewer.py
"""
import json
import sqlite3
from pathlib import Path
import streamlit as st

TRANSCRIPT_DIR = Path("./transcripts")
DB_PATH        = "./transcripts/oasis_realestate.db"

STANCE_COLORS = {
    "positive": "#2ecc71",
    "neutral":  "#f39c12",
    "negative": "#e74c3c",
}

st.set_page_config(page_title="Dubai RE Swarm Viewer", layout="wide")
st.title("🏙 Dubai Real Estate — Swarm Conversation Viewer")

# ── Sidebar: pick a transcript ────────────────────────────────────────────────
json_files = sorted(TRANSCRIPT_DIR.glob("realestate_stance_*.json"), reverse=True)
if not json_files:
    st.warning("No transcripts found. Run the simulation first.")
    st.stop()

selected = st.sidebar.selectbox(
    "Transcript",
    options=json_files,
    format_func=lambda p: p.name,
)

with open(selected, encoding="utf-8") as f:
    data = json.load(f)

# ── Overview bar ──────────────────────────────────────────────────────────────
st.subheader("Event")
st.info(data["event"])

col1, col2, col3 = st.columns(3)
tally = data["tally"]
col1.metric("Positive", tally["positive"])
col2.metric("Neutral",  tally["neutral"])
col3.metric("Negative", tally["negative"])

# ── Stance breakdown ──────────────────────────────────────────────────────────
st.subheader("Agent Stances")
for agent in data["agents"]:
    stance = agent["stance"]
    color  = STANCE_COLORS.get(stance, "#888")
    with st.expander(
        f"**{agent['name']}** (@{agent['username']}) — "
        f":{stance}: `{stance.upper()}` ({agent['confidence']:.0%})"
    ):
        st.markdown(f"**Role:** {agent['role']}")
        st.markdown(f"**Reason:** {agent['reason']}")
        if agent.get("posts"):
            st.markdown("**Posts during simulation:**")
            for post in agent["posts"]:
                st.markdown(f"> {post}")

# ── Raw conversation thread (from SQLite) ─────────────────────────────────────
st.subheader("Raw Conversation Thread")

if Path(DB_PATH).exists():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    for table in tables:
        if "post" in table.lower() or "comment" in table.lower():
            cur.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cur.fetchall()]

            content_col = next((c for c in cols if c.lower() in
                                ("content","text","body","message")), None)
            user_col    = next((c for c in cols if c.lower() in
                                ("user_id","author_id","agent_id")), None)
            time_col    = next((c for c in cols if "time" in c.lower() or
                                "creat" in c.lower()), None)

            if not content_col or not user_col:
                continue

            order = f"ORDER BY {time_col}" if time_col else ""
            cur.execute(f"SELECT {user_col}, {content_col} FROM {table} "
                        f"WHERE {content_col} IS NOT NULL {order}")

            st.markdown(f"**Table: `{table}`**")
            for uid, text in cur.fetchall():
                # Find agent name from transcript
                agent_name = next(
                    (a["name"] for a in data["agents"] if a["agent_index"] == int(uid)),
                    f"Agent {uid}"
                )
                with st.chat_message("user"):
                    st.markdown(f"**{agent_name}** (ID {uid})")
                    st.markdown(text)

    conn.close()
else:
    st.info("SQLite DB not found — showing transcript data only.")
```

### Add to docker-compose.yml

```yaml
conversation_viewer:
  build: .
  container_name: convo_viewer
  ports:
    - "8502:8502"
  volumes:
    - ./transcripts:/app/transcripts
  environment:
    - PYTHONUNBUFFERED=1
  profiles:
    - viewer
  command:
    - streamlit
    - run
    - conversation_viewer.py
    - --server.port=8502
    - --server.address=0.0.0.0
```

Run with:
```bash
docker compose --profile viewer up conversation_viewer
```
Then open `http://localhost:8502` in a browser.

---

## 6. Is It Iterative, Evolving, or One-Shot? Do Agents See Each Other? Is There Memory?

### Conversation structure

The simulation runs in **rounds**, not in a round-robin loop:

```
Round 0  (seed)   : Agent 0 posts the market event manually
Round 1  (LLM)    : All 14 agents act simultaneously, reading the seed post
Round 2  (LLM)    : All 14 agents act simultaneously, reading posts from rounds 0+1
Round 3  (LLM)    : All 14 agents act simultaneously, reading posts from rounds 0+1+2
```

This is **an evolving conversation**, not a one-shot response. Each agent can:
- Respond to a specific post from a previous round
- Like, dislike, or repost other agents' content
- Search for posts on a topic
- Create a follow-up post that builds on what they said before
- Follow another agent

### Shared memory — the platform IS the memory

Agents do NOT have a private long-term memory store (no vector DB, no message history
that persists between rounds). Instead, **the OASIS platform database is their shared
memory**. When an agent takes its turn in Round 2, OASIS feeds it the current state
of the platform — visible posts, comments, like counts, trending topics — so each agent
is aware of everything that has been publicly posted.

This mirrors how Reddit actually works: you see the whole thread before you reply.

```
┌─────────────────────────────────────────────────────────────┐
│  What each agent sees when deciding their Round 2 action     │
│                                                              │
│  • The original seed post (Round 0)                         │
│  • All posts/comments from Round 1 (all 14 agents)          │
│  • Like/dislike counts on each post                         │
│  • Which posts are trending                                  │
│  • Their own profile/persona (system prompt)                 │
└─────────────────────────────────────────────────────────────┘
```

### What agents do NOT know

- What other agents will do in the **current round** (actions are simultaneous)
- Anything posted in a **future** round
- Any private information held by other agents (unless it was posted publicly)
- The simulation's own mechanics (they don't know they are in a swarm)

### Comparison: OASIS vs social_platform.py

| Property | `real_estate_oasis.py` (OASIS) | `social_platform.py` (Round-robin) |
|---|---|---|
| Turn order | All agents simultaneously per round | One agent at a time, in sequence |
| Can agent A reply to agent B? | Yes — via comment on B's post | Yes — sees B's previous message |
| Rounds | 3 parallel rounds | 50 sequential turns |
| Memory | Platform DB (shared, public) | Full message history injected into each prompt |
| Actions available | Post, comment, like, dislike, follow, repost, search, trend | Chat reply only |
| Scale | Designed for 100s–1000s of agents | Works best at <20 agents |

### Extending memory beyond the platform

If you want agents to carry **private reasoning** across rounds (e.g., "I decided in
Round 1 to remain cautious — let me maintain that position"), add a `"memory"` field
to the profile that is updated after each round:

```python
# After each round, update each agent's profile with a memory note
for agent_id, posts in round_posts.items():
    profiles[agent_id]["persona"] += (
        f"\n\n[ROUND {round_num} MEMORY] You previously said: {posts[-1][:200]}..."
    )
```

This simulates short-term memory by injecting a summary of the agent's last post back
into their persona for the next round.

---

*Generated: 2026-04-17 | Dubai Real Estate OASIS Simulation | CAMEL-AI v0.x*
