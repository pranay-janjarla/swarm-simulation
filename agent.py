# agent.py — HumanAgent: 1000 unique agents with rule-based behavior state machine
from __future__ import annotations
from collections import Counter

import mesa

from config import (
    PERSONALITY_PARAMS, COGNITIVE_PARAMS, SOCIAL_PARAMS,
    MEDIA_OPTIONS, MEDIA_WEIGHTS,
    AGE_GROUPS, AGE_WEIGHTS,
    INCOME_LEVELS, INCOME_WEIGHTS,
    GROUP_MEMBERSHIPS,
    AGE_RATIONALITY_MOD, AGE_RISK_MOD,
    INCOME_INFO_MOD, INCOME_RISK_MOD,
    BEHAVIOR_TO_STANCE,
)
from message_mutation import compose_message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _normal(mean: float, std: float, rng) -> float:
    return _clamp(rng.normal(mean, std))


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class HumanAgent(mesa.Agent):
    """
    A single agent in the swarm simulation.

    State machine
    -------------
    calm → aware → anxious → panic | conspiratorial | comply | adapt | ignore
                                           ↓ (after N ticks)
                                        recovery → calm

    Message passing
    ---------------
    Each tick agents read their inbox (messages received last tick), compose a
    personality-filtered retelling via message_mutation.compose_message(), and
    queue it into neighbours' next_inbox.  Model swaps next_inbox → inbox at
    the start of each tick so every agent sees a consistent snapshot.
    """

    # How many ticks before an agent in each terminal state moves to recovery
    _RECOVERY_TICKS: dict[str, int] = {
        "panic":          15,
        "comply":         20,
        "adapt":          20,
        "ignore":         10,
        "conspiratorial": 30,
    }

    # Reach multiplier by media consumption type
    _MEDIA_REACH: dict[str, float] = {
        "mainstream":  0.80,
        "social_media": 1.00,
        "alternative": 0.50,
        "none":        0.20,
    }

    # States that can spread via social contagion
    # Only fear (panic) and distrust (conspiratorial) spread emotionally;
    # rational choices like comply/adapt are individual, not contagious.
    _CONTAGIOUS_STATES = frozenset({"panic", "conspiratorial"})

    def __init__(self, unique_id: int, model):
        super().__init__(unique_id, model)
        rng = model.rng

        # --- Personality (Big Five) ---
        self.openness          = _normal(*PERSONALITY_PARAMS["openness"],          rng)
        self.conscientiousness = _normal(*PERSONALITY_PARAMS["conscientiousness"], rng)
        self.neuroticism       = _normal(*PERSONALITY_PARAMS["neuroticism"],       rng)
        self.extraversion      = _normal(*PERSONALITY_PARAMS["extraversion"],      rng)
        self.agreeableness     = _normal(*PERSONALITY_PARAMS["agreeableness"],     rng)

        # --- Cognitive ---
        self.rationality        = _normal(*COGNITIVE_PARAMS["rationality"],        rng)
        self.irrationality      = _normal(*COGNITIVE_PARAMS["irrationality"],      rng)
        self.risk_tolerance     = _normal(*COGNITIVE_PARAMS["risk_tolerance"],     rng)
        self.information_access = _normal(*COGNITIVE_PARAMS["information_access"], rng)
        self.trust_in_authority = _normal(*COGNITIVE_PARAMS["trust_in_authority"], rng)
        self.decision_lag       = int(rng.integers(0, 6))  # Uniform(0–5 ticks)

        # --- Social ---
        self.social_influence_weight = _normal(*SOCIAL_PARAMS["social_influence_weight"], rng)
        self.echo_chamber_factor     = _normal(*SOCIAL_PARAMS["echo_chamber_factor"],     rng)
        self.media_consumption       = str(rng.choice(MEDIA_OPTIONS, p=MEDIA_WEIGHTS))

        # --- Demographic ---
        self.age_group    = str(rng.choice(AGE_GROUPS,   p=AGE_WEIGHTS))
        self.income_level = str(rng.choice(INCOME_LEVELS, p=INCOME_WEIGHTS))
        n_groups = int(rng.integers(1, 3))
        self.group_membership = list(
            rng.choice(GROUP_MEMBERSHIPS, size=n_groups, replace=False)
        )

        # Apply demographic modifiers
        self.rationality        = _clamp(self.rationality        + AGE_RATIONALITY_MOD[self.age_group])
        self.risk_tolerance     = _clamp(self.risk_tolerance     + AGE_RISK_MOD[self.age_group])
        self.information_access = _clamp(self.information_access + INCOME_INFO_MOD[self.income_level])
        self.risk_tolerance     = _clamp(self.risk_tolerance     + INCOME_RISK_MOD[self.income_level])

        # --- Behaviour state ---
        self.behavior_state:   str       = "calm"
        self.narrative_type:   str       = "neutral"
        self.stance:           str       = "neutral"   # positive / neutral / negative
        self.ticks_in_state:   int       = 0
        self.event_aware_tick: int | None = None   # tick when agent first noticed event

        # --- Message buffers (two-buffer pattern; model swaps each tick) ---
        self.inbox:      list[dict] = []   # messages to read this tick
        self.next_inbox: list[dict] = []   # messages queued for next tick

        # Private: outbox message composed this tick (reset each step)
        self._outbox: dict | None = None

    # ------------------------------------------------------------------
    # Mesa entry point
    # ------------------------------------------------------------------

    def step(self) -> None:
        event        = self.model.event
        current_tick: int = self.model.schedule.steps  # incremented by scheduler AFTER all agents step

        self._update_state(event, current_tick)
        self._apply_social_contagion()
        self._compose_and_send(event)
        self._update_narrative()
        self._update_stance(event)

        self.ticks_in_state += 1
        self._outbox = None   # clean up for next tick

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _effective_severity(self, event) -> float:
        """Perceived severity after information filtering."""
        return float(event.severity * event.believability * self.information_access)

    def _update_state(self, event, tick: int) -> None:
        if not event.active:
            return

        # Stochastic awareness: agent may learn about the event this tick
        if self.event_aware_tick is None:
            reach = (
                event.spread_speed
                * self._MEDIA_REACH[self.media_consumption]
                * self.information_access
            )
            if self.model.rng.random() < reach:
                self.event_aware_tick = tick

        state = self.behavior_state

        # calm → aware
        if state == "calm":
            if (
                self.event_aware_tick is not None
                and (tick - self.event_aware_tick) >= self.decision_lag
            ):
                self.behavior_state = "aware"
                self.ticks_in_state = 0

        # aware → anxious / conspiratorial / ignore
        elif state == "aware":
            # High-irrationality, low-trust agents may reject the narrative directly
            # (probability proportional to disbelievability — high bel → rare direct con)
            if (self.irrationality > 0.50 and self.trust_in_authority < 0.35
                    and self.model.rng.random() < (1.0 - event.believability)):
                self.behavior_state = "conspiratorial"
                self.ticks_in_state = 0
            elif event.severity * self.neuroticism > 0.25:
                self.behavior_state = "anxious"
                self.ticks_in_state = 0
            elif self.ticks_in_state > 10:
                self.behavior_state = "ignore"
                self.ticks_in_state = 0

        # anxious → terminal state (stochastic, personality × event weighted)
        # Replaces deterministic if-else which funnelled 90%+ agents to one state.
        elif state == "anxious":
            # Build weighted scores for each terminal outcome.
            # p_com uses authority × trust only (no rationality — avoids near-zero products).
            p_con = self.irrationality * (1.0 - self.trust_in_authority) * (1.0 - event.believability * 0.7)
            p_com = event.authority_response * self.trust_in_authority
            p_pan = event.severity * self.neuroticism * max(0.0, 1.0 - self.rationality)
            p_ada = self.openness * self.rationality * (1.0 - event.severity * 0.5)
            p_ign = self.risk_tolerance * (1.0 - self.information_access)

            scores = [max(s, 0.01) for s in (p_con, p_com, p_pan, p_ada, p_ign)]
            total  = sum(scores)
            probs  = [s / total for s in scores]

            next_state = str(self.model.rng.choice(
                ["conspiratorial", "comply", "panic", "adapt", "ignore"],
                p=probs,
            ))
            self.behavior_state = next_state
            self.ticks_in_state = 0

        # terminal states → recovery
        elif state in self._RECOVERY_TICKS:
            if self.ticks_in_state > self._RECOVERY_TICKS[state]:
                self.behavior_state = "recovery"
                self.ticks_in_state = 0

        # recovery → calm
        elif state == "recovery":
            if self.ticks_in_state > 5:
                self.behavior_state = "calm"
                self.ticks_in_state = 0

    def _apply_social_contagion(self) -> None:
        """Pull agent toward majority state of compatible neighbours."""
        if self.behavior_state == "calm":
            return   # calm agents are unaffected by contagion

        neighbours = list(self.model.graph.neighbors(self.unique_id))
        if not neighbours:
            return

        # Echo-chamber filter: only listen to neighbours with similar trust_in_authority
        similarity_threshold = 1.0 - self.echo_chamber_factor
        compatible = [
            self.model.agent_by_id[int(nid)]
            for nid in neighbours
            if abs(
                self.model.agent_by_id[int(nid)].trust_in_authority
                - self.trust_in_authority
            ) < similarity_threshold
        ]
        if not compatible:
            return

        majority = Counter(a.behavior_state for a in compatible).most_common(1)[0][0]

        if majority != self.behavior_state and majority in self._CONTAGIOUS_STATES:
            if self.model.rng.random() < self.social_influence_weight:
                self.behavior_state = majority
                self.ticks_in_state = 0

    def _compose_and_send(self, event) -> None:
        """Compose a personality-filtered message and queue it to neighbours."""
        if not event.active or self.behavior_state == "calm":
            return

        # Build source: prioritise inbox; fall back to own perception
        own_perception = {
            "severity_perceived": self._effective_severity(event),
            "credibility":        float(event.believability * self.trust_in_authority),
            "framing":            self.narrative_type,
            "hop_count":          0,
            "origin_agent_id":    self.unique_id,
        }
        source = self.inbox if self.inbox else [own_perception]
        msg = compose_message(self, source)
        if msg is None:
            return

        self._outbox = msg

        neighbours = list(self.model.graph.neighbors(self.unique_id))
        if not neighbours:
            return

        # Extraversion controls how many neighbours receive the message
        n_send = max(1, int(len(neighbours) * (0.30 + self.extraversion * 0.70)))
        n_send = min(n_send, len(neighbours))
        targets = self.model.rng.choice(neighbours, size=n_send, replace=False)
        for nid in targets:
            self.model.agent_by_id[int(nid)].next_inbox.append(msg)

    def _update_narrative(self) -> None:
        """Derive narrative_type from outbox message or fallback to behavior state."""
        if self._outbox is not None:
            self.narrative_type = self._outbox["framing"]
        elif self.behavior_state == "conspiratorial":
            self.narrative_type = "conspiratorial"
        elif self.behavior_state == "panic":
            self.narrative_type = "alarmed"
        elif self.behavior_state in ("adapt", "comply"):
            self.narrative_type = "adaptive"
        else:
            self.narrative_type = "neutral"

    def _update_stance(self, event) -> None:
        """Derive agent's stance toward the event: positive / neutral / negative.

        Baseline comes from behavior_state via BEHAVIOR_TO_STANCE.
        Personality modifiers reflect three empirically grounded patterns:

        1. Smart-but-paranoid: high irrationality + distrust overrides positive → negative
           (e.g. a compliant agent who secretly distrusts authority)
        2. Anxious-but-aware: neurotic agents in the 'aware' state tip toward negative
           before they've even resolved into a terminal state
        3. Resilient recovery: high-rationality + high-openness agents leaving a crisis
           emerge positive rather than just neutral
        """
        base = BEHAVIOR_TO_STANCE[self.behavior_state]

        if base == "positive":
            # Reluctant compliance: paranoid agents comply outwardly but feel negative
            if self.irrationality > 0.75 and self.trust_in_authority < 0.30:
                self.stance = "negative"
                return

        elif base == "neutral":
            # Neurotic awareness: fear is already forming before the state machine resolves
            if self.behavior_state == "aware" and self.neuroticism > 0.65:
                self.stance = "negative"
                return
            # Post-crisis growth: rational, open agents who've recovered trend positive
            if self.behavior_state == "recovery" and self.rationality > 0.60 and self.openness > 0.60:
                self.stance = "positive"
                return

        self.stance = base
