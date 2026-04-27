# message_mutation.py — telephone-game message composition
#
# Each agent composes its own retelling of the event shaped by its personality.
# The message dict schema:
#   severity_perceived : float  — how severe the agent believes the event is
#   credibility        : float  — how credible the agent believes the info
#   framing            : str    — "alarmed" | "conspiratorial" | "neutral" | "adaptive"
#   hop_count          : int    — hops from origin (0 = direct from event)
#   origin_agent_id    : int    — unique_id of the agent that first spread it

import numpy as np


def compose_message(agent, received_messages: list) -> dict | None:
    """
    Apply personality-driven distortions to incoming messages and return the
    agent's retelling. Returns None if there is nothing to compose.

    Trait effects on composed message
    ----------------------------------
    High neuroticism       → inflates perceived threat (severity up)
    High irrationality     → strips credibility, pushes conspiratorial framing
    Low information_access → severity is dampened (vague, detail-stripped)
    High agreeableness     → moderate severity toward mean (consensus framing)
    High openness          → reframes toward adaptive / opportunity lens
    (extraversion controls fan-out upstream, not message content)
    """
    if not received_messages:
        return None

    # --- Aggregate received messages ---
    avg_severity    = float(np.mean([m["severity_perceived"] for m in received_messages]))
    avg_credibility = float(np.mean([m["credibility"]        for m in received_messages]))
    max_hops        = max(m["hop_count"] for m in received_messages)
    # Preserve the earliest-known origin for lineage tracking
    origin_id       = min(m["origin_agent_id"] for m in received_messages)

    severity    = avg_severity
    credibility = avg_credibility

    # --- Trait-based mutations ---

    # Neuroticism: inflates threat perception
    severity += agent.neuroticism * 0.15

    # Irrationality: undermines credibility, adds conspiratorial spin
    credibility -= agent.irrationality * 0.25

    # Low information_access: message becomes vaguer (severity dampened)
    severity *= 0.40 + agent.information_access * 0.60

    # Agreeableness: pull toward moderate (social-consensus dampening)
    severity *= 1.0 - agent.agreeableness * 0.10

    severity    = float(np.clip(severity,    0.0, 1.0))
    credibility = float(np.clip(credibility, 0.0, 1.0))

    # --- Determine framing ---
    if agent.irrationality > 0.60 and credibility < 0.40:
        framing = "conspiratorial"
    elif agent.neuroticism > 0.65 and severity > 0.50:
        framing = "alarmed"
    elif agent.openness > 0.60 and agent.rationality > 0.45:
        framing = "adaptive"
    else:
        framing = "neutral"

    return {
        "severity_perceived": severity,
        "credibility":        credibility,
        "framing":            framing,
        "hop_count":          max_hops + 1,
        "origin_agent_id":    origin_id,
    }
