# Swarm AI Agent Simulation — Plan

## What This Builds

A simulation of **1000 rule-based AI agents** in Python that replicate realistic human behavioral responses when a configurable triggering event occurs. The event type is abstract and driven by parameters (severity, believability, spread speed) so any scenario — news event, disaster, market crash, political announcement — can be tested by changing sliders.

Each agent has varied personality and demographic parameters drawn from realistic statistical distributions, so the population behaves heterogeneously — like real humans — rather than all reacting the same way.

Three additional mechanics layer on top of the base simulation:

- **Message mutation** — agents don't just observe the event; they retell it to neighbors in a simplified, personality-filtered version (telephone game). Each retelling carries the transmitting agent's emotional and cognitive fingerprint, causing the story to drift across the network.
- **Irrationality** — a parameter distinct from `rationality` that models active irrational cognition (conspiracy thinking, motivated reasoning, paranoia) rather than simply poor logical processing. High irrationality drives a new `conspiratorial` behavioral state and makes agents immune to the `authority_response` slider.
- **Narrative sentiment** — a second output layer tracking not just what agents _do_ (behavioral states) but what they _believe and say_ (the dominant narrative framing circulating in the population).

**Outputs:**

- CSV/JSON data export (per-agent state and narrative type at every simulation tick, including message lineage)
- Streamlit interactive dashboard (sliders + live charts, including narrative sentiment gauge)

**Stack:** Python, Mesa (agent framework), NetworkX (social graph), Streamlit (dashboard)

---

## Architecture

```
┌─────────────────────────────────┐
│  config.py                      │  Parameter distributions + event presets
└────────────────┬────────────────┘
                 │
┌────────────────▼────────────────┐
│  event.py                       │  Event dataclass: severity, type, believability
└────────────────┬────────────────┘
                 │ triggers at tick 0
┌────────────────▼────────────────┐
│  agent.py  (HumanAgent)         │  1000 agents, rule-based decision logic
│  - Personality (Big Five)        │
│  - Cognitive params              │
│  - Social network position       │
│  - State machine: behavior state │
└────────────────┬────────────────┘
                 │ scheduled by Mesa
┌────────────────▼────────────────┐
│  model.py  (SwarmModel)         │  Mesa Model, social graph, DataCollector
└────────────────┬────────────────┘
                 │ exports
┌────────────────▼────────────────┐
│  run.py                         │  CLI entrypoint, runs N ticks, saves CSV/JSON
└─────────────────────────────────┘
                 │
┌────────────────▼────────────────┐
│  dashboard.py  (Streamlit)      │  Interactive UI: sliders, run button, charts
└─────────────────────────────────┘
```

---

## Files to Be Created

```
test-1/
├── config.py             # Parameter distributions, constants, event presets
├── event.py              # Event dataclass
├── agent.py              # HumanAgent class (Mesa Agent)
├── message_mutation.py   # compose_message() logic — personality-filtered retelling
├── model.py              # SwarmModel class (Mesa Model)
├── run.py                # CLI: run simulation, export CSV/JSON
├── dashboard.py          # Streamlit dashboard
└── requirements.txt      # Dependencies
```

---

## Agent Parameters (Each Agent Gets Its Own Random Values)

Every agent is initialized with unique parameter values drawn from statistical distributions — this is what creates behavioral diversity across the 1000 agents.

### Personality — Big Five (floats 0.0 to 1.0)

| Parameter           | How It's Set               | What It Controls                                        |
| ------------------- | -------------------------- | ------------------------------------------------------- |
| `openness`          | Normal(mean=0.5, std=0.15) | Willingness to change behavior after the event          |
| `conscientiousness` | Normal(0.5, 0.15)          | How rule-following and deliberate the response is       |
| `neuroticism`       | Normal(0.5, 0.15)          | Emotional volatility — higher = more likely to panic    |
| `extraversion`      | Normal(0.5, 0.15)          | Social amplification — spreads states to neighbors more |
| `agreeableness`     | Normal(0.5, 0.15)          | Susceptibility to peer influence                        |

### Cognitive Parameters

| Parameter            | How It's Set          | What It Controls                                                                                                                                                                                                                                                            |
| -------------------- | --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rationality`        | Normal(0.5, 0.2)      | 0 = poor logical processing, 1 = strong logical reasoning                                                                                                                                                                                                                   |
| `irrationality`      | Normal(0.3, 0.2)      | Active irrational cognition — conspiracy thinking, motivated reasoning, paranoia. Independent of `rationality`: a high-rationality agent can still have high irrationality (smart conspiracy theorist). Drives the `conspiratorial` state and distorts message composition. |
| `risk_tolerance`     | Normal(0.5, 0.2)      | Threshold before triggering high-arousal response                                                                                                                                                                                                                           |
| `information_access` | Normal(0.6, 0.2)      | What fraction of true event info the agent receives                                                                                                                                                                                                                         |
| `trust_in_authority` | Normal(0.5, 0.25)     | Weight given to official/government sources                                                                                                                                                                                                                                 |
| `decision_lag`       | Uniform(0 to 5 ticks) | Delay before the agent starts reacting                                                                                                                                                                                                                                      |

### Social Parameters

| Parameter                 | How It's Set       | What It Controls                                          |
| ------------------------- | ------------------ | --------------------------------------------------------- |
| `social_influence_weight` | Normal(0.4, 0.2)   | How much neighbors' behavior shifts the agent's own state |
| `echo_chamber_factor`     | Normal(0.3, 0.2)   | Only influenced by agents with similar values             |
| `media_consumption`       | Random categorical | mainstream / social_media / alternative / none            |

### Demographic Parameters

| Parameter          | Values                            | Effect                                        |
| ------------------ | --------------------------------- | --------------------------------------------- |
| `age_group`        | teen / adult / elder              | Adjusts weights on rationality and risk       |
| `income_level`     | low / mid / high                  | Adjusts risk tolerance and information access |
| `group_membership` | list (political, religious, etc.) | Determines social graph clustering            |

---

## Behavior State Machine

Each agent moves through states based on their parameters and neighbor influence:

```
calm ──► aware ──► anxious ──► panic
                          ├──► conspiratorial   ← NEW
                          ├──► comply
                          ├──► adapt
                          └──► ignore
                               (after N ticks)
                                    └──► recovery ──► calm
```

### Transition Rules (pure logic — no LLM calls)

| From      | To               | Condition                                                      |
| --------- | ---------------- | -------------------------------------------------------------- |
| `calm`    | `aware`          | Event has started AND agent's `decision_lag` ticks have passed |
| `aware`   | `anxious`        | `event.severity × neuroticism > 0.5`                           |
| `anxious` | `panic`          | `rationality < 0.3` AND `risk_tolerance < 0.4`                 |
| `anxious` | `conspiratorial` | `irrationality > 0.7` AND `trust_in_authority < 0.3` — **NEW** |
| `anxious` | `comply`         | `trust_in_authority > 0.6` AND `rationality > 0.5`             |
| `anxious` | `adapt`          | `openness > 0.6` AND `rationality > 0.4`                       |
| `anxious` | `ignore`         | `risk_tolerance > 0.7` OR `information_access < 0.2`           |

**Notes on `conspiratorial`:** Agents in this state are immune to `authority_response` (official messaging cannot reach them). The state is highly contagious within echo chambers — it spreads fast between agents who share low `trust_in_authority` values. It produces the most distorted message mutations.

**Social contagion:** Every tick, each agent is also pulled toward the majority state of its social network neighbors, weighted by `social_influence_weight`. This creates cascade and clustering effects.

---

## Message Mutation (Telephone Game)

Each tick, after updating their own behavioral state, agents compose a simplified retelling of the event and pass it to their neighbors. The retelling is shaped by the agent's personality:

| Trait                    | Effect on composed message                             |
| ------------------------ | ------------------------------------------------------ |
| High `neuroticism`       | Inflates threat language, adds urgency                 |
| High `irrationality`     | Strips source credibility, adds conspiratorial framing |
| High `openness`          | Reframes toward opportunity or learning                |
| High `agreeableness`     | Adds social consensus framing ("everyone says…")       |
| Low `information_access` | Factual detail drops out — message becomes vaguer      |
| High `extraversion`      | Message spreads to more neighbors per tick             |

**Implementation:** Each `HumanAgent` gets:

- An `inbox` list — messages received from neighbors this tick
- A `compose_message(received_summary)` method in `message_mutation.py` — applies rule-based trait filters to produce the agent's version
- A `narrative_type` field — categorical label for the agent's current framing: `alarmed / conspiratorial / neutral / adaptive`

Messages carry lineage metadata (originating agent ID, hop count) so the CSV export can reconstruct how a story mutated across the network.

---

## Narrative Sentiment

A second output layer tracked alongside behavioral states. Where behavioral states answer _what are agents doing_, narrative sentiment answers _what story is the population telling itself about the event_.

Each agent's `narrative_type` is derived from their `compose_message()` output and collected by Mesa's `DataCollector` every tick. The dashboard displays it as a stacked bar that evolves over time:

```
tick 24:  [alarmed 38%][conspir. 12%][neutral 10%][adaptive 40%]
```

High `severity` + low `believability` creates the most interesting splits — behavioral states may stay calm while the narrative turns conspiratorial. This is tracked separately from and in addition to the behavioral state line chart.

---

## Event Parameters (Configurable via Dashboard Sliders)

```python
Event(
    name             = "Breaking News",   # label shown in dashboard
    severity         = 0.7,              # 0.0 (trivial) → 1.0 (catastrophic)
    believability    = 0.8,              # 0.0 (rumor) → 1.0 (confirmed fact)
    spread_speed     = 0.5,              # 0.0 (slow) → 1.0 (instant viral)
    authority_response = 0.4,           # 0.0 (silent) → 1.0 (strong official action)
    event_type       = "social",         # social / disaster / economic / political
    tick_of_onset    = 0                 # which tick the event fires
)
```

---

## Dashboard (Streamlit)

The dashboard lets you:

- Adjust all event parameters via sliders
- Click **Run Simulation** to run 100 ticks across 1000 agents
- See live charts:
  - **Line chart:** behavior state % over time (panic / comply / adapt / ignore / calm / conspiratorial)
  - **Bar chart:** final state distribution at last tick
  - **Stacked bar:** narrative sentiment over time (alarmed / conspiratorial / neutral / adaptive) — updated each tick alongside the behavior chart
  - **Network graph:** social graph with agents colored by state

---

## How to Run (Once Built)

```bash
# Install dependencies
pip install -r requirements.txt

# Run simulation via CLI (exports CSV + JSON to /data folder)
python run.py

# Launch interactive dashboard
streamlit run dashboard.py
```

---

## What Makes This Realistic

1. **Scale-free social network** (Barabási–Albert model) — a small number of highly connected "hubs" (influencers), most agents have few connections. This mirrors real social networks.
2. **Big Five personality distributions** — parameter values are drawn from population-level norms from psychology research, so the distribution of personality types matches real-world data.
3. **Social contagion** — behavior cascades through the network. A few panic agents can trigger neighbors, creating realistic crowd dynamics.
4. **Decision lag** — not everyone reacts immediately, mimicking real-world information diffusion delays.
5. **Bounded rationality** — agents don't have perfect information or perfect reasoning; `information_access` and `rationality` cap what they know and how well they process it.

---

## Verification Plan

| Test                                         | Expected Result                                            |
| -------------------------------------------- | ---------------------------------------------------------- |
| Run default simulation                       | 1000 agents across 8 states, no uniform response           |
| Increase `severity` from 0.2 → 0.9           | panic% rises, calm% drops                                  |
| Set `social_influence_weight = 0`            | No cascade — agents act independently                      |
| Set `believability = 0.1`                    | Most agents stay calm or ignore (rumor effect)             |
| Set `trust_in_authority = 0.9` for all       | comply% dominates                                          |
| Set `irrationality` distribution mean to 0.8 | conspiratorial% spikes, authority_response has no effect   |
| Trace message lineage in CSV                 | Each message hop shows increasing distortion from original |
| Set `irrationality = 0`, `neuroticism = 0`   | Narrative sentiment stays neutral/adaptive throughout      |

---

## Dependencies

| ------------ | ------- | ---------------------------------------- |
| Package | Version | Purpose |
| ------------ | ------- | ---------------------------------------- |
| `mesa` | >=2.3 | Agent-based modeling framework |
| `streamlit` | >=1.35 | Interactive dashboard |
| `matplotlib` | >=3.8 | Charts and network visualization |
| `networkx` | >=3.3 | Social graph (Barabási–Albert network) |
| `pandas` | >=2.2 | Data collection and CSV export |
| `numpy` | >=1.26 | Statistical distributions for agent init |
| ------------ | ------- | ---------------------------------------- |
