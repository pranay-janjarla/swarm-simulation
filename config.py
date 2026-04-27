# config.py — parameter distributions, constants, event presets

NUM_AGENTS = 1000
NETWORK_M  = 3      # Barabási–Albert: edges added per new node

# ---------- Distributions (mean, std) — all values clipped to [0, 1] ----------

PERSONALITY_PARAMS = {
    "openness":          (0.5, 0.15),
    "conscientiousness": (0.5, 0.15),
    "neuroticism":       (0.5, 0.15),
    "extraversion":      (0.5, 0.15),
    "agreeableness":     (0.5, 0.15),
}

COGNITIVE_PARAMS = {
    "rationality":        (0.5, 0.20),
    "irrationality":      (0.40, 0.20),  # independent of rationality
    "risk_tolerance":     (0.5, 0.20),
    "information_access": (0.6, 0.20),
    "trust_in_authority": (0.5, 0.25),
    # decision_lag: Uniform(0, 5) ticks — handled separately
}

SOCIAL_PARAMS = {
    "social_influence_weight": (0.25, 0.15),
    "echo_chamber_factor":     (0.3, 0.20),
}

# ---------- Categorical distributions ----------

MEDIA_OPTIONS = ["mainstream", "social_media", "alternative", "none"]
MEDIA_WEIGHTS = [0.40, 0.30, 0.20, 0.10]

AGE_GROUPS  = ["teen", "adult", "elder"]
AGE_WEIGHTS = [0.20,   0.60,   0.20]

INCOME_LEVELS  = ["low", "mid", "high"]
INCOME_WEIGHTS = [0.30,  0.50,  0.20]

GROUP_MEMBERSHIPS = ["political", "religious", "professional", "local", "none"]

# ---------- Demographic modifiers applied at agent init ----------

AGE_RATIONALITY_MOD = {"teen": -0.10, "adult":  0.00, "elder":  0.05}
AGE_RISK_MOD        = {"teen":  0.10, "adult":  0.00, "elder": -0.10}
INCOME_INFO_MOD     = {"low":  -0.15, "mid":    0.00, "high":   0.15}
INCOME_RISK_MOD     = {"low":  -0.10, "mid":    0.00, "high":   0.10}

# ---------- State / narrative labels ----------

BEHAVIOR_STATES = [
    "calm", "aware", "anxious", "panic",
    "conspiratorial", "comply", "adapt", "ignore", "recovery",
]

NARRATIVE_TYPES = ["alarmed", "conspiratorial", "neutral", "adaptive"]

STATE_COLORS = {
    "calm":           "#4CAF50",
    "aware":          "#8BC34A",
    "anxious":        "#FFC107",
    "panic":          "#F44336",
    "conspiratorial": "#9C27B0",
    "comply":         "#2196F3",
    "adapt":          "#00BCD4",
    "ignore":         "#9E9E9E",
    "recovery":       "#CDDC39",
}

NARRATIVE_COLORS = {
    "alarmed":        "#FF7043",
    "conspiratorial": "#AB47BC",
    "neutral":        "#78909C",
    "adaptive":       "#26A69A",
}

# ---------- Stance (primary output layer) ----------
# Each agent lands on positive / neutral / negative toward the event.
# Grounded in population-level behavioral research:
#   - Rally-round-the-flag: trust + compliance → positive
#   - Negativity bias: fear/panic/conspiracy → negative
#   - Habituation: calm/recovery → neutral

STANCE_TYPES = ["positive", "neutral", "negative"]

STANCE_COLORS = {
    "positive": "#4CAF50",
    "neutral":  "#9E9E9E",
    "negative": "#F44336",
}

# Base stance derived from behavior state; personality modifiers applied in agent.py
BEHAVIOR_TO_STANCE: dict[str, str] = {
    "calm":           "neutral",
    "aware":          "neutral",
    "anxious":        "negative",
    "panic":          "negative",
    "conspiratorial": "negative",
    "comply":         "positive",
    "adapt":          "positive",
    "ignore":         "neutral",
    "recovery":       "neutral",
}

# ---------- Event presets ----------

EVENT_PRESETS = {
    "Breaking News": {
        "severity": 0.6, "believability": 0.70, "spread_speed": 0.80,
        "authority_response": 0.50, "event_type": "social", "tick_of_onset": 0,
    },
    "Natural Disaster": {
        "severity": 0.9, "believability": 0.95, "spread_speed": 0.60,
        "authority_response": 0.80, "event_type": "disaster", "tick_of_onset": 0,
    },
    "Market Crash": {
        "severity": 0.75, "believability": 0.85, "spread_speed": 0.50,
        "authority_response": 0.30, "event_type": "economic", "tick_of_onset": 0,
    },
    "Viral Rumor": {
        "severity": 0.5, "believability": 0.20, "spread_speed": 0.90,
        "authority_response": 0.20, "event_type": "social", "tick_of_onset": 0,
    },
}
