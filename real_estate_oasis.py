"""
real_estate_oasis.py — Dubai Real Estate Market Simulation via CAMEL-AI OASIS
==============================================================================
15 agents (1 neutral seeder + 14 market personas) react to a real estate market
event over 3 autonomous LLM rounds on a simulated Reddit-style platform.

Stance per agent (positive / neutral / negative toward the event) is extracted
post-simulation by reading the OASIS SQLite database and calling Azure OpenAI.

Run (Docker):
    docker compose run --rm realestate
"""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import textwrap
import threading
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PROFILE_PATH   = "./data/user_data_realestate_15.json"
TRANSCRIPT_DIR = Path("./transcripts")
DB_PATH        = "./transcripts/oasis_realestate.db"
NUM_ROUNDS     = 3      # autonomous LLM rounds after the seed post

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
CYAN    = "\033[96m"

STANCE_COLORS = {"positive": GREEN, "neutral": YELLOW, "negative": RED}
_W = 80


def _wrap(text: str, indent: int = 4) -> str:
    prefix = " " * indent
    return textwrap.fill(
        text, width=_W - indent,
        initial_indent=prefix, subsequent_indent=prefix,
    )


# ---------------------------------------------------------------------------
# Azure OpenAI client  (for post-simulation stance extraction)
# ---------------------------------------------------------------------------

def _build_az_client() -> AzureOpenAI:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    api_key  = os.environ.get("AZURE_OPENAI_API_KEY", "")
    api_ver  = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    if not endpoint or not api_key:
        sys.exit(
            "ERROR: AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set in .env\n"
        )
    return AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_ver)


_az_client  = _build_az_client()
_DEPLOYMENT = os.environ.get("AZURE_DEPLOYMENT_NAME", os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"))


# ---------------------------------------------------------------------------
# CAMEL-AI OASIS model builder
# ---------------------------------------------------------------------------

def _build_oasis_model():
    """Build a CAMEL ModelFactory model backed by Azure OpenAI."""
    try:
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType
    except ImportError:
        sys.exit(
            "ERROR: camel-oasis is not installed.\n"
            "Add 'camel-oasis' to requirements.txt and rebuild: "
            "docker compose build\n"
        )

    deployment = os.environ.get("AZURE_DEPLOYMENT_NAME", os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"))
    return ModelFactory.create(
        model_platform=ModelPlatformType.AZURE,
        model_type=deployment,
        api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
        url=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
    )


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

async def run_simulation(event_description: str) -> str:
    """
    Run the OASIS swarm simulation.
    Returns the path to the SQLite DB written by OASIS.
    """
    try:
        import oasis
        from oasis import (
            ActionType, DefaultPlatformType, LLMAction, ManualAction,
            generate_reddit_agent_graph,
        )
    except ImportError as exc:
        sys.exit(
            f"ERROR: Could not import oasis — {exc}\n"
            "Make sure camel-oasis is installed and the Docker image has been rebuilt.\n"
        )

    AVAILABLE_ACTIONS = [
        ActionType.CREATE_POST,
        ActionType.CREATE_COMMENT,
        ActionType.LIKE_POST,
        ActionType.DISLIKE_POST,
        ActionType.FOLLOW,
        ActionType.REPOST,
        ActionType.DO_NOTHING,
        ActionType.SEARCH_POSTS,
        ActionType.TREND,
    ]

    model = _build_oasis_model()

    print(f"\n{BOLD}Building agent graph ({PROFILE_PATH})…{RESET}")
    agent_graph = await generate_reddit_agent_graph(
        PROFILE_PATH,
        model=model,
        available_actions=AVAILABLE_ACTIONS,
    )

    # Remove stale DB
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"{BOLD}Initialising simulation environment…{RESET}")
    env = oasis.make(
        agent_graph=agent_graph,
        platform=DefaultPlatformType.REDDIT,
        database_path=DB_PATH,
    )
    await env.reset()

    # ── Phase 0: Seed — agent 0 (UAE Property News) posts the event ──────────
    seed_agent   = env.agent_graph.get_agent(0)
    seed_content = (
        f"🚨 BREAKING — Dubai Real Estate Market Update:\n"
        f"{event_description}\n\n"
        f"#DubaiRealEstate #UAEProperty #PropertyMarket"
    )
    print(f"\n{CYAN}{BOLD}{'─' * _W}{RESET}")
    print(f"{CYAN}{BOLD}  [ SEED POST — UAE Property News ]{RESET}")
    print(f"{CYAN}{BOLD}{'─' * _W}{RESET}")
    print(_wrap(seed_content))

    await env.step(
        {
            seed_agent: ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": seed_content},
            )
        }
    )

    # ── Phases 1–3: Autonomous LLM rounds ────────────────────────────────────
    for round_num in range(1, NUM_ROUNDS + 1):
        print(f"\n{BOLD}{'─' * _W}{RESET}")
        print(f"{BOLD}  Round {round_num}/{NUM_ROUNDS} — agents deliberating…{RESET}")
        print(f"{BOLD}{'─' * _W}{RESET}")

        all_actions = {
            agent: LLMAction()
            for _, agent in env.agent_graph.get_agents()
        }
        await env.step(all_actions)
        print(f"  {DIM}Round {round_num} complete.{RESET}")

    await env.close()
    print(f"\n{GREEN}{BOLD}Simulation complete.{RESET}  DB → {DB_PATH}")
    return DB_PATH


# ---------------------------------------------------------------------------
# SQLite → stance extraction
# ---------------------------------------------------------------------------

def _read_simulation_data(db_path: str) -> dict[int, list[str]]:
    """
    Read all posts and comments from the OASIS SQLite DB.
    Discovers column names dynamically so it is robust to schema changes.
    Returns {user_id: [text, text, ...]}
    """
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0].lower() for row in cur.fetchall()}

    posts_by_user: dict[int, list[str]] = {}

    def _extract_table(table_name: str) -> None:
        cur.execute(f"PRAGMA table_info({table_name})")
        cols = {row[1].lower() for row in cur.fetchall()}

        content_col = next(
            (c for c in ("content", "text", "body", "message") if c in cols), None
        )
        user_col = next(
            (c for c in ("user_id", "author_id", "agent_id") if c in cols), None
        )
        if not content_col or not user_col:
            return

        cur.execute(
            f"SELECT {user_col}, {content_col} "
            f"FROM {table_name} "
            f"WHERE {content_col} IS NOT NULL AND TRIM({content_col}) != ''"
        )
        for uid, text in cur.fetchall():
            posts_by_user.setdefault(int(uid), []).append(str(text))

    for table in tables:
        if "post" in table or "comment" in table:
            _extract_table(table)

    conn.close()
    return posts_by_user


def extract_stances(event_description: str, db_path: str) -> list[dict]:
    """
    For each agent: gather their posts from the DB, call Azure OpenAI to
    classify stance as positive / neutral / negative.
    Returns list of result dicts.
    """
    with open(PROFILE_PATH, encoding="utf-8") as f:
        profiles = json.load(f)

    posts_by_user = _read_simulation_data(db_path)
    results: list[dict] = []
    spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

    print(f"\n{BOLD}Extracting stances ({len(profiles)} agents)…{RESET}\n")

    for idx, profile in enumerate(profiles):
        name     = profile.get("realname", f"Agent {idx}")
        username = profile.get("username", f"agent_{idx}")
        role     = profile.get("profession", "Unknown")
        persona  = profile.get("persona", "")
        posts    = posts_by_user.get(idx, [])

        # Agent 0 is the neutral seeder — hardcode
        if idx == 0:
            results.append({
                "agent_index": 0,
                "name": name, "username": username, "role": role,
                "stance": "neutral", "confidence": 1.0,
                "reason": "Neutral news-aggregator / event seeder — stance not evaluated.",
                "posts": posts,
            })
            continue

        if not posts:
            results.append({
                "agent_index": idx,
                "name": name, "username": username, "role": role,
                "stance": "neutral", "confidence": 0.3,
                "reason": "Agent produced no posts during the simulation.",
                "posts": [],
            })
            continue

        # Build the classification prompt
        posts_text = "\n".join(f"  - {p}" for p in posts[:10])
        prompt = (
            "You are analysing the stance of a social media user toward a real estate market event.\n\n"
            f"EVENT: {event_description}\n\n"
            f"AGENT: {name} (@{username}) — {role}\n"
            f"PERSONA: {persona}\n\n"
            "POSTS/COMMENTS MADE DURING SIMULATION:\n"
            f"{posts_text}\n\n"
            "Classify the agent's stance toward the event as exactly one of:\n"
            "  positive — views the event as beneficial, an opportunity, or good news\n"
            "  neutral  — balanced, factual, or undecided\n"
            "  negative — views the event as harmful, risky, or bad news\n\n"
            "Respond in JSON only:\n"
            '{"stance": "positive"|"neutral"|"negative", "confidence": 0.0-1.0, '
            '"reason": "one concise sentence"}'
        )

        # Spinner
        done = threading.Event()

        def _spin(agent_name: str = name) -> None:
            i = 0
            while not done.is_set():
                sys.stdout.write(
                    f"\r  {DIM}{spinner_chars[i % len(spinner_chars)]}  "
                    f"Analysing {agent_name}…{RESET}  "
                )
                sys.stdout.flush()
                i += 1
                time.sleep(0.1)

        spin_thread = threading.Thread(target=_spin, daemon=True)
        spin_thread.start()

        try:
            response = _az_client.chat.completions.create(
                model=_DEPLOYMENT,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            raw    = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            stance     = str(parsed.get("stance", "neutral")).lower()
            confidence = float(parsed.get("confidence", 0.5))
            reason     = str(parsed.get("reason", ""))
        except Exception as exc:
            stance, confidence, reason = "neutral", 0.0, f"API error: {exc}"
        finally:
            done.set()
            spin_thread.join()
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()

        results.append({
            "agent_index": idx,
            "name": name, "username": username, "role": role,
            "stance": stance, "confidence": confidence,
            "reason": reason, "posts": posts,
        })

    return results


# ---------------------------------------------------------------------------
# Terminal rendering
# ---------------------------------------------------------------------------

def render_stance_summary(event_description: str, results: list[dict]) -> None:
    border = "═" * _W
    print(f"\n{BOLD}{border}{RESET}")
    print(f"{BOLD}  🏙  DUBAI REAL ESTATE — SWARM STANCE SUMMARY{RESET}")
    print(f"{BOLD}{border}{RESET}")
    event_short = event_description[:68] + ("…" if len(event_description) > 68 else "")
    print(f"  {DIM}Event: {event_short}{RESET}\n")

    tally: dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
    for r in results:
        tally[r["stance"]] = tally.get(r["stance"], 0) + 1

    total = len(results)
    for stance, count in tally.items():
        pct = count / total * 100
        bar = "█" * int(pct / 2)
        col = STANCE_COLORS.get(stance, "")
        print(f"  {col}{stance:<12}{RESET}  {count:>2}/{total}  ({pct:4.0f}%)  {col}{bar}{RESET}")

    print(f"\n{BOLD}{'─' * _W}{RESET}")
    print(f"{BOLD}  Per-agent breakdown:{RESET}\n")

    for r in results:
        col      = STANCE_COLORS.get(r["stance"], "")
        conf_str = f"{r['confidence']:.0%}" if r.get("confidence") else "—"
        print(
            f"  {col}{BOLD}{r['stance'].upper():<10}{RESET}"
            f"  {r['name']:<26}  {DIM}{r['role'][:28]:<28}{RESET}"
            f"  {DIM}conf={conf_str}{RESET}"
        )
        if r.get("reason"):
            print(_wrap(r["reason"], indent=12))
        print()

    print(f"{BOLD}{border}{RESET}\n")


# ---------------------------------------------------------------------------
# Save outputs
# ---------------------------------------------------------------------------

def save_outputs(event_description: str, results: list[dict]) -> None:
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = event_description[:40].replace(" ", "_").replace("/", "-")

    json_path = TRANSCRIPT_DIR / f"realestate_stance_{slug}_{ts}.json"
    payload   = {
        "event":      event_description,
        "timestamp":  ts,
        "num_agents": len(results),
        "tally": {
            "positive": sum(1 for r in results if r["stance"] == "positive"),
            "neutral":  sum(1 for r in results if r["stance"] == "neutral"),
            "negative": sum(1 for r in results if r["stance"] == "negative"),
        },
        "agents": results,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    txt_path = TRANSCRIPT_DIR / f"realestate_stance_{slug}_{ts}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Dubai Real Estate — Swarm Stance Report\n")
        f.write(f"Event     : {event_description}\n")
        f.write(f"Generated : {ts}\n\n")
        for r in results:
            f.write(f"[{r['stance'].upper():<8}] {r['name']}  ({r['role']})\n")
            f.write(f"           {r['reason']}\n\n")

    print(f"Exported:\n  JSON → {json_path}\n  TXT  → {txt_path}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    global NUM_ROUNDS, PROFILE_PATH
    import argparse

    parser = argparse.ArgumentParser(
        description="Dubai Real Estate OASIS Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--event",
        type=str,
        default="",
        help="Market event description (skips the interactive prompt)",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=None,
        help=f"Number of autonomous LLM rounds (default: {NUM_ROUNDS})",
    )
    parser.add_argument(
        "--profile-path",
        type=str,
        default=None,
        help=f"Path to agent profiles JSON (default: {PROFILE_PATH})",
    )
    args = parser.parse_args()

    # Apply overrides
    if args.rounds is not None:
        NUM_ROUNDS = max(1, args.rounds)
    if args.profile_path:
        PROFILE_PATH = args.profile_path

    print(f"\n{BOLD}{'═' * _W}{RESET}")
    print(f"{BOLD}  🏙  DUBAI REAL ESTATE MARKET — SWARM AI SIMULATION{RESET}")
    print(f"{BOLD}  CAMEL-AI OASIS · 15 agents · {NUM_ROUNDS} LLM rounds{RESET}")
    print(f"{BOLD}{'═' * _W}{RESET}\n")

    if args.event.strip():
        event_description = args.event.strip()
        print(f"Event: {event_description}\n")
    else:
        event_description = input(
            "Describe the market event\n"
            "(e.g. 'Dubai property prices rise 15% YoY, new Golden Visa rules announced'):\n> "
        ).strip()

    if not event_description:
        event_description = (
            "Dubai residential property prices surge 15% year-on-year, "
            "driven by record Golden Visa applications and constrained supply "
            "in prime districts (Palm Jumeirah, Downtown, Dubai Marina)."
        )
        print(f"{DIM}Using default event: {event_description}{RESET}\n")

    db_path = asyncio.run(run_simulation(event_description))
    results = extract_stances(event_description, db_path)
    render_stance_summary(event_description, results)
    save_outputs(event_description, results)


if __name__ == "__main__":
    main()
