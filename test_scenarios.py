# test_scenarios.py — Validate simulation against real-world events
#
# Each scenario defines:
#   params   : Event constructor kwargs derived from historical facts
#   expect   : dict of {state: (min_pct, max_pct)} — plausible ranges
#   rationale: one-line citation of what actually happened
#
# Run:   python test_scenarios.py
# Or:    docker compose run --rm cli python test_scenarios.py

from __future__ import annotations
import sys
from dataclasses import dataclass
from typing import Optional

from config import BEHAVIOR_STATES
from event import Event
from model import SwarmModel

# ── ANSI colours ────────────────────────────────────────────────────────────
PASS  = "\033[92m✔\033[0m"
FAIL  = "\033[91m✘\033[0m"
WARN  = "\033[93m~\033[0m"
BOLD  = "\033[1m"
RESET = "\033[0m"
GREY  = "\033[90m"
RED   = "\033[91m"
GRN   = "\033[92m"
YEL   = "\033[93m"
CYN   = "\033[96m"
MAG   = "\033[95m"
BLU   = "\033[94m"

# ── Scenario definition ──────────────────────────────────────────────────────

@dataclass
class Scenario:
    name:      str
    year:      str
    params:    dict         # Event kwargs
    expect:    dict         # {state: (min_pct, max_pct)}   — % of population
    dominant:  list[str]    # ordered list: top-1 or top-2 expected states
    rationale: str          # what history actually showed

SCENARIOS: list[Scenario] = [

    Scenario(
        name   = "COVID-19 Pandemic Onset",
        year   = "Jan–Mar 2020",
        params = dict(
            name               = "COVID-19 Onset",
            severity           = 0.85,
            believability      = 0.55,  # WHO initially downplayed, mixed signals
            spread_speed       = 0.75,
            authority_response = 0.40,  # fragmented global response
            event_type         = "disaster",
        ),
        expect = {
            "panic":          (10, 40),   # panic-buying, hoarding — widespread
            "conspiratorial": ( 5, 25),   # "lab leak", "5G" narratives
            "comply":         (10, 35),   # lockdown compliance varied widely
            "adapt":          ( 5, 25),   # WFH, masks — proactive adapters
        },
        dominant  = ["panic", "comply"],
        rationale = (
            "Widespread panic-buying; compliance with lockdowns varied "
            "by country but was substantial; ~25–30% eventually became "
            "conspiratorial (lab-leak, anti-mask); notable 'adapt' group "
            "switched to remote work and PPE early."
        ),
    ),

    Scenario(
        name   = "9/11 Terrorist Attacks",
        year   = "Sep 2001",
        params = dict(
            name               = "9/11 Attacks",
            severity           = 0.95,
            believability      = 0.95,  # live TV, unambiguous
            spread_speed       = 0.90,  # breaking news 24/7
            authority_response = 0.75,  # strong govt/patriot act response
            event_type         = "social",
        ),
        expect = {
            "panic":          (15, 40),   # immediate shock/fear
            "comply":         (20, 45),   # strong patriotism / authority follow
            "conspiratorial": ( 2, 12),   # "inside job" minority view initially
            "adapt":          ( 5, 20),   # security adaptations
        },
        dominant  = ["comply", "panic"],
        rationale = (
            "Immediate mass shock and fear (panic); followed by one of the "
            "largest compliance waves in US history (Patriot Act, airport "
            "security acceptance). Conspiratorial narratives ('inside job') "
            "remained a minority initially. High authority trust boost."
        ),
    ),

    Scenario(
        name   = "2008 Global Financial Crisis",
        year   = "Sep–Nov 2008",
        params = dict(
            name               = "2008 Financial Crisis",
            severity           = 0.80,
            believability      = 0.70,  # bank collapses were visible; causes opaque
            spread_speed       = 0.50,  # slower — financial media, not mass TV
            authority_response = 0.25,  # bailouts were unpopular, distrusted
            event_type         = "economic",
        ),
        expect = {
            "panic":          (15, 40),   # market panic, bank runs
            "ignore":         (10, 30),   # many felt it was distant/abstract
            "conspiratorial": (10, 30),   # "bankster" narratives, Occupy movement
            "comply":         ( 5, 20),   # low — authority distrusted
            "adapt":          ( 5, 20),   # some debt-restructuring behaviour
        },
        dominant  = ["panic", "ignore"],
        rationale = (
            "Bank runs and market panic were global; a large segment ignored "
            "it (savings in cash, not stocks). Distrust of Wall St and "
            "government soared — fuelling 'conspiratorial' narratives "
            "(Occupy, QAnon precursors). Low compliance with govt guidance "
            "because bailouts felt unjust."
        ),
    ),

    Scenario(
        name   = "Fukushima Nuclear Disaster",
        year   = "Mar 2011",
        params = dict(
            name               = "Fukushima Disaster",
            severity           = 0.88,
            believability      = 0.90,  # confirmed, cameras everywhere
            spread_speed       = 0.70,
            authority_response = 0.50,  # Japanese govt responded but was opaque
            event_type         = "disaster",
        ),
        expect = {
            "panic":          (15, 40),   # iodine tablet hoarding in Europe, mass evacuation
            "comply":         (15, 35),   # evacuation zone compliance
            "adapt":          (10, 30),   # anti-nuclear movement, energy adaptation
            "conspiratorial": ( 5, 20),   # "govt covering up true radiation levels"
        },
        dominant  = ["panic", "comply"],
        rationale = (
            "Immediate mass panic in Japan (evacuation); iodine tablet "
            "shortages across Europe. Strong comply in evacuation zones. "
            "Significant 'adapt' group — Germany shut down nuclear plants. "
            "Moderate conspiratorial (govt accused of hiding radiation data)."
        ),
    ),

    Scenario(
        name   = "COVID Vaccine Misinformation Wave",
        year   = "Mid 2021",
        params = dict(
            name               = "Vaccine Misinformation",
            severity           = 0.60,  # perceived fear by believers was real, even if claim wasn't
            believability      = 0.20,  # low — claims contradicted by studies
            spread_speed       = 0.95,  # social media virality
            authority_response = 0.40,  # mandates present but trust eroded
            event_type         = "social",
        ),
        expect = {
            "conspiratorial": (10, 35),  # microchips, infertility, 5G claims
            "ignore":         (10, 40),  # majority dismissed misinformation
            "panic":          ( 5, 25),  # some panic around vaccines
            "comply":         ( 5, 25),  # still got vaccinated despite noise
        },
        dominant  = ["conspiratorial", "ignore"],
        rationale = (
            "Rapidly spreading low-credibility claims drove one of the "
            "largest conspiratorial waves in recent history (~30% hesitancy "
            "at peak in US). Majority either ignored the noise or complied "
            "with vaccination. Low severity perception → low panic, high "
            "ignore rate. This scenario stress-tests the irrationality param."
        ),
    ),

    Scenario(
        name   = "Brexit Referendum Result",
        year   = "Jun 2016",
        params = dict(
            name               = "Brexit Vote",
            severity           = 0.55,
            believability      = 0.60,  # heavily contested claims on both sides
            spread_speed       = 0.80,
            authority_response = 0.15,  # UK govt was split; no clear guidance
            event_type         = "political",
        ),
        expect = {
            "panic":          (10, 30),  # markets crashed briefly, Remainers panicked
            "adapt":          (10, 30),  # businesses started contingency planning
            "conspiratorial": (10, 30),  # "£350M for NHS" backlash, deep-state claims
            "ignore":         ( 5, 25),  # large apathetic segment
            "comply":         ( 2, 15),  # very low — authority was discredited
        },
        dominant  = ["adapt", "panic"],
        rationale = (
            "Deeply polarised: Remainers panicked (currency crash, economic "
            "fears); Leavers adapted or ignored. Minimal comply because "
            "official guidance was contradictory. Conspiratorial framing "
            "('elites sabotaging the will of the people') ran strong on "
            "both sides. Classic low-authority, high-polarisation scenario."
        ),
    ),
]

# ── Test runner ──────────────────────────────────────────────────────────────

TICKS      = 120
NUM_AGENTS = 1000
SEED       = 42

def run_scenario(sc: Scenario) -> dict:
    """Run scenario and return PEAK % reached by each state across all ticks.

    Peak values are used because terminal states are transient — agents cycle
    through them and into recovery.  The historically meaningful question is
    'did panic peak above X%?', not 'is panic still high at tick 120?'.
    """
    event = Event(**sc.params)
    model = SwarmModel(event=event, num_agents=NUM_AGENTS, seed=SEED)
    for _ in range(TICKS):
        model.step()

    model_df = model.get_model_dataframe()
    peak_pct: dict[str, float] = {}
    for state in BEHAVIOR_STATES:
        col = f"frac_{state}"
        if col in model_df.columns:
            peak_pct[state] = float(model_df[col].max() * 100)
        else:
            peak_pct[state] = 0.0
    return peak_pct


def check_scenario(sc: Scenario, pct: dict) -> tuple[int, int]:
    """Return (passed_checks, total_checks)."""
    passed = 0
    total  = len(sc.expect)
    for state, (lo, hi) in sc.expect.items():
        if lo <= pct.get(state, 0) <= hi:
            passed += 1
    return passed, total


def dominant_check(sc: Scenario, pct: dict) -> bool:
    """Check that the first expected dominant state is #1 or #2 by population."""
    top2 = sorted(pct, key=pct.get, reverse=True)[:2]
    return sc.dominant[0] in top2


def print_results(sc: Scenario, pct: dict) -> tuple[int, int]:
    passed, total = check_scenario(sc, pct)
    dom_ok        = dominant_check(sc, pct)
    overall       = PASS if passed == total and dom_ok else (WARN if passed >= total // 2 else FAIL)

    top3 = sorted(pct, key=pct.get, reverse=True)[:3]

    print(f"\n{BOLD}{'─'*70}{RESET}")
    print(f"{BOLD}{overall}  {sc.name}  ({sc.year}){RESET}")
    print(f"{GREY}   {sc.rationale}{RESET}")
    print()

    # State table
    print(f"   {'State':<18} {'Peak %':>10}   {'Expected Range':>20}   {'':>4}")
    print(f"   {'─'*18} {'─'*10}   {'─'*20}   {'─'*4}")
    for state, (lo, hi) in sc.expect.items():
        val  = pct.get(state, 0)
        ok   = PASS if lo <= val <= hi else FAIL
        star = " ◀ top" if state == top3[0] else (" (2nd)" if state == top3[1] else "")
        print(f"   {state:<18} {val:>9.1f}%   {f'{lo}%–{hi}%':>20}   {ok}{star}")

    # States not in expect (informational)
    others = {s: v for s, v in pct.items() if s not in sc.expect and v > 0.5}
    if others:
        print(f"   {'─'*18}")
        for state, val in sorted(others.items(), key=lambda x: -x[1]):
            print(f"   {state:<18} {val:>9.1f}%   {'(not checked)':>20}")

    dom_sym = PASS if dom_ok else FAIL
    print(f"\n   Dominant state check: {dom_sym}  "
          f"(expected '{sc.dominant[0]}' in top-2, "
          f"got {top3[0]} / {top3[1]})")
    print(f"   Range checks passed: {passed}/{total}")
    return passed, total


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"\n{BOLD}{'═'*70}")
    print(f"  Swarm Simulation — Real-World Scenario Validation")
    print(f"  {TICKS} ticks · {NUM_AGENTS} agents · seed={SEED}")
    print(f"{'═'*70}{RESET}")

    total_checks  = 0
    passed_checks = 0
    dom_passes    = 0

    for sc in SCENARIOS:
        sys.stdout.write(f"  Running: {sc.name} …")
        sys.stdout.flush()
        pct = run_scenario(sc)
        sys.stdout.write("\r" + " " * 60 + "\r")

        p, t    = print_results(sc, pct)
        passed_checks += p
        total_checks  += t
        dom_passes    += int(dominant_check(sc, pct))

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'═'*70}")
    print(f"  SUMMARY")
    print(f"{'═'*70}{RESET}")
    print(f"  Scenarios run          : {len(SCENARIOS)}")
    print(f"  Range checks passed    : {passed_checks}/{total_checks}  "
          f"({passed_checks/total_checks*100:.0f}%)")
    print(f"  Dominant-state correct : {dom_passes}/{len(SCENARIOS)}")

    overall_pct = (passed_checks + dom_passes) / (total_checks + len(SCENARIOS)) * 100
    if overall_pct >= 75:
        verdict = f"{GRN}{BOLD}GOOD — model behaviour is historically plausible{RESET}"
    elif overall_pct >= 50:
        verdict = f"{YEL}{BOLD}PARTIAL — some scenarios diverge from history{RESET}"
    else:
        verdict = f"{RED}{BOLD}POOR — model parameters need recalibration{RESET}"

    print(f"\n  Overall score: {overall_pct:.0f}%  →  {verdict}")
    print(f"{'═'*70}\n")

    # Non-zero exit code if overall score is poor (useful for CI)
    if overall_pct < 50:
        sys.exit(1)


if __name__ == "__main__":
    main()
