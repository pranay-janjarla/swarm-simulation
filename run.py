# run.py — CLI entrypoint: run simulation, export CSV + JSON
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from event import Event
from model import SwarmModel
from config import EVENT_PRESETS, BEHAVIOR_STATES, NARRATIVE_TYPES, STANCE_TYPES, NUM_AGENTS

# ANSI colours for terminal summary
_C = {
    "calm":           "\033[92m",   # green
    "aware":          "\033[32m",   # dark green
    "anxious":        "\033[93m",   # yellow
    "panic":          "\033[91m",   # red
    "conspiratorial": "\033[95m",   # magenta
    "comply":         "\033[94m",   # blue
    "adapt":          "\033[96m",   # cyan
    "ignore":         "\033[90m",   # grey
    "recovery":       "\033[33m",   # dark yellow
    "RESET":          "\033[0m",
    "BOLD":           "\033[1m",
}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run the swarm AI simulation (1000 agents, configurable event).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--preset",        default=None,       choices=list(EVENT_PRESETS),
                   help="Load an event preset (overrides individual event flags)")
    p.add_argument("--ticks",         type=int,  default=100,  help="Number of simulation ticks")
    p.add_argument("--agents",        type=int,  default=NUM_AGENTS, help="Number of agents")
    p.add_argument("--seed",          type=int,  default=42,   help="Random seed")
    p.add_argument("--name",          default="Event",          help="Event name")
    p.add_argument("--severity",      type=float, default=0.6,  help="Event severity [0–1]")
    p.add_argument("--believability", type=float, default=0.7,  help="Event believability [0–1]")
    p.add_argument("--spread-speed",  type=float, default=0.5,  help="Info spread speed [0–1]")
    p.add_argument("--authority",     type=float, default=0.4,  help="Authority response [0–1]")
    p.add_argument("--event-type",    default="social",
                   choices=["social", "disaster", "economic", "political"],
                   help="Event category")
    p.add_argument("--tick-of-onset", type=int,  default=0,    help="Tick when event fires")
    p.add_argument("--out-dir",       default="data",           help="Output directory for exports")
    p.add_argument("--no-export",     action="store_true",      help="Skip CSV/JSON export")
    return p


def build_event(args: argparse.Namespace) -> Event:
    if args.preset:
        params = dict(EVENT_PRESETS[args.preset])
        params["name"] = args.preset
        return Event(**params)
    return Event(
        name               = args.name,
        severity           = args.severity,
        believability      = args.believability,
        spread_speed       = args.spread_speed,
        authority_response = args.authority,
        event_type         = args.event_type,
        tick_of_onset      = args.tick_of_onset,
    )


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _ensure_dir(path: str) -> Path:
    d = Path(path)
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_results(model: SwarmModel, out_dir: str, timestamp: str) -> tuple[Path, Path]:
    d = _ensure_dir(out_dir)
    csv_path  = d / f"results_{timestamp}.csv"
    json_path = d / f"results_{timestamp}.json"

    # --- Model-level CSV (one row per tick) ---
    model_df = model.get_model_dataframe()
    model_df.index.name = "tick"
    model_df.to_csv(csv_path)

    # --- Agent-level JSON (snapshot at final tick) ---
    agent_df = model.get_agent_dataframe()
    # Keep only the last tick for each agent
    last_tick = agent_df.index.get_level_values("Step").max()
    final_df  = agent_df.xs(last_tick, level="Step")

    payload = {
        "meta": {
            "ticks":      model.schedule.steps,
            "num_agents": model.num_agents,
            "event":      {
                "name":               model.event.name,
                "severity":           model.event.severity,
                "believability":      model.event.believability,
                "spread_speed":       model.event.spread_speed,
                "authority_response": model.event.authority_response,
                "event_type":         model.event.event_type,
                "tick_of_onset":      model.event.tick_of_onset,
            },
        },
        "final_stance_counts":    model.stance_counts(),
        "final_state_counts":     model.state_counts(),
        "final_narrative_counts": model.narrative_counts(),
        "agents": final_df.reset_index().to_dict(orient="records"),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return csv_path, json_path


# ---------------------------------------------------------------------------
# Pretty summary
# ---------------------------------------------------------------------------

_STANCE_COLOR = {
    "positive": "\033[92m",   # bright green
    "neutral":  "\033[90m",   # grey
    "negative": "\033[91m",   # red
}


def print_summary(model: SwarmModel) -> None:
    total   = model.num_agents
    states  = model.state_counts()
    narrs   = model.narrative_counts()
    stances = model.stance_counts()
    R, B    = _C["RESET"], _C["BOLD"]

    print(f"\n{B}=== Simulation complete — tick {model.schedule.steps} ==={R}")
    print(f"{B}Event:{R} {model.event.name}  "
          f"(severity={model.event.severity:.2f}, "
          f"believability={model.event.believability:.2f})\n")

    # ── Primary output: public stance ────────────────────────────────────────
    print(f"{B}Public Stance (how agents feel about the event):{R}")
    for stance in STANCE_TYPES:
        n   = stances.get(stance, 0)
        pct = n / total * 100
        bar = "█" * int(pct / 2)
        col = _STANCE_COLOR.get(stance, "")
        print(f"  {col}{stance:<16}{R}  {n:>5} agents  ({pct:5.1f}%)  {col}{bar}{R}")

    # ── Secondary: behavior states ────────────────────────────────────────────
    print(f"\n{B}Behavior States:{R}")
    for state in BEHAVIOR_STATES:
        n   = states.get(state, 0)
        pct = n / total * 100
        bar = "█" * int(pct / 2)
        col = _C.get(state, "")
        print(f"  {col}{state:<16}{R}  {n:>5} agents  ({pct:5.1f}%)  {col}{bar}{R}")

    print(f"\n{B}Narrative Types:{R}")
    for narr in NARRATIVE_TYPES:
        n   = narrs.get(narr, 0)
        pct = n / total * 100
        print(f"  {narr:<16}  {n:>5} agents  ({pct:5.1f}%)")

    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    event = build_event(args)
    model = SwarmModel(event=event, num_agents=args.agents, seed=args.seed)

    print(f"Running {args.ticks} ticks with {args.agents} agents "
          f"(seed={args.seed}) …")

    t0 = time.perf_counter()
    for tick in range(args.ticks):
        model.step()
        if (tick + 1) % 10 == 0 or tick == 0:
            counts = model.state_counts()
            pct_calm  = counts["calm"]  / args.agents * 100
            pct_panic = counts["panic"] / args.agents * 100
            pct_cons  = counts["conspiratorial"] / args.agents * 100
            sys.stdout.write(
                f"\r  tick {tick+1:>4}/{args.ticks}  "
                f"calm={pct_calm:5.1f}%  "
                f"panic={pct_panic:4.1f}%  "
                f"conspiratorial={pct_cons:4.1f}%   "
            )
            sys.stdout.flush()
    elapsed = time.perf_counter() - t0
    print(f"\n  Done in {elapsed:.1f}s")

    print_summary(model)

    if not args.no_export:
        from datetime import datetime
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path, json_path = export_results(model, args.out_dir, ts)
        print(f"Exported:\n  CSV  → {csv_path}\n  JSON → {json_path}\n")


if __name__ == "__main__":
    main()
