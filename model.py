# model.py — SwarmModel: orchestrates 1000 agents on a scale-free social graph
from __future__ import annotations

import mesa
import networkx as nx
import numpy as np
from mesa.time import RandomActivation
from mesa.datacollection import DataCollector

from config import NUM_AGENTS, NETWORK_M, BEHAVIOR_STATES, NARRATIVE_TYPES, STANCE_TYPES
from event import Event
from agent import HumanAgent


# ---------------------------------------------------------------------------
# Reporter helpers (called by DataCollector per tick)
# ---------------------------------------------------------------------------

def _state_fraction(state: str):
    """Return a reporter function for the fraction of agents in `state`."""
    def reporter(model: SwarmModel) -> float:
        count = sum(
            1 for a in model.schedule.agents if a.behavior_state == state
        )
        return count / model.num_agents
    reporter.__name__ = f"frac_{state}"
    return reporter


def _narrative_fraction(narrative: str):
    """Return a reporter function for the fraction of agents with `narrative`."""
    def reporter(model: SwarmModel) -> float:
        count = sum(
            1 for a in model.schedule.agents if a.narrative_type == narrative
        )
        return count / model.num_agents
    reporter.__name__ = f"frac_narr_{narrative}"
    return reporter


def _stance_fraction(stance: str):
    """Return a reporter function for the fraction of agents with `stance`."""
    def reporter(model: SwarmModel) -> float:
        count = sum(
            1 for a in model.schedule.agents if a.stance == stance
        )
        return count / model.num_agents
    reporter.__name__ = f"frac_stance_{stance}"
    return reporter


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class SwarmModel(mesa.Model):
    """
    Mesa model that manages 1000 HumanAgents on a Barabási–Albert social graph.

    step() sequence each tick
    --------------------------
    1. Swap message buffers: next_inbox → inbox, clear next_inbox
    2. Activate event (if tick_of_onset reached)
    3. Step all agents (RandomActivation — random order each tick)
    4. Collect data via DataCollector
    """

    def __init__(
        self,
        event: Event,
        num_agents: int = NUM_AGENTS,
        seed: int = 42,
    ) -> None:
        super().__init__()
        self.event      = event
        self.num_agents = num_agents
        self.rng        = np.random.default_rng(seed)

        # Mesa scheduler
        self.schedule = RandomActivation(self)

        # Barabási–Albert scale-free network — realistic social topology
        self.graph = nx.barabasi_albert_graph(num_agents, NETWORK_M, seed=seed)

        # Fast O(1) lookup: unique_id → agent
        self.agent_by_id: dict[int, HumanAgent] = {}

        # Create agents — node ids 0..num_agents-1 match unique_ids
        for i in range(num_agents):
            agent = HumanAgent(i, self)
            self.schedule.add(agent)
            self.agent_by_id[i] = agent

        # DataCollector
        model_reporters = {}
        for state in BEHAVIOR_STATES:
            model_reporters[f"frac_{state}"] = _state_fraction(state)
        for narr in NARRATIVE_TYPES:
            model_reporters[f"frac_narr_{narr}"] = _narrative_fraction(narr)
        for stance in STANCE_TYPES:
            model_reporters[f"frac_stance_{stance}"] = _stance_fraction(stance)

        agent_reporters = {
            "behavior_state":        lambda a: a.behavior_state,
            "narrative_type":        lambda a: a.narrative_type,
            "stance":                lambda a: a.stance,
            "neuroticism":           lambda a: round(a.neuroticism,           3),
            "rationality":           lambda a: round(a.rationality,           3),
            "irrationality":         lambda a: round(a.irrationality,         3),
            "trust_in_authority":    lambda a: round(a.trust_in_authority,    3),
            "social_influence_weight": lambda a: round(a.social_influence_weight, 3),
            "information_access":    lambda a: round(a.information_access,    3),
            "age_group":             lambda a: a.age_group,
            "income_level":          lambda a: a.income_level,
            "media_consumption":     lambda a: a.media_consumption,
        }

        self.datacollector = DataCollector(
            model_reporters=model_reporters,
            agent_reporters=agent_reporters,
        )

    # ------------------------------------------------------------------
    # Mesa entry point
    # ------------------------------------------------------------------

    def step(self) -> None:
        # 1. Swap message buffers so every agent reads last tick's messages
        for agent in self.schedule.agents:
            agent.inbox      = agent.next_inbox
            agent.next_inbox = []

        # 2. Activate event once tick_of_onset is reached
        self.event.activate(self.schedule.steps)

        # 3. Step all agents (random order, consistent snapshot via buffer swap)
        self.schedule.step()

        # 4. Collect model + agent data
        self.datacollector.collect(self)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def state_counts(self) -> dict[str, int]:
        """Current count of agents per behavior state."""
        counts: dict[str, int] = {s: 0 for s in BEHAVIOR_STATES}
        for agent in self.schedule.agents:
            counts[agent.behavior_state] += 1
        return counts

    def narrative_counts(self) -> dict[str, int]:
        """Current count of agents per narrative type."""
        counts: dict[str, int] = {n: 0 for n in NARRATIVE_TYPES}
        for agent in self.schedule.agents:
            counts[agent.narrative_type] += 1
        return counts

    def stance_counts(self) -> dict[str, int]:
        """Current count of agents per stance (positive / neutral / negative)."""
        counts: dict[str, int] = {s: 0 for s in STANCE_TYPES}
        for agent in self.schedule.agents:
            counts[agent.stance] += 1
        return counts

    def get_model_dataframe(self):
        """Return the tick-level DataFrame from the DataCollector."""
        return self.datacollector.get_model_vars_dataframe()

    def get_agent_dataframe(self):
        """Return the agent-level DataFrame from the DataCollector."""
        return self.datacollector.get_agent_vars_dataframe()
