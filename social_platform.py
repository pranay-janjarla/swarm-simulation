"""
social_platform.py — 10-Agent AI Social Media Platform
=======================================================
10 AI agents with distinct personalities discuss a user-provided topic.
Each agent gets 5 turns, reads all prior messages, and replies in character.
Uses Azure OpenAI (credentials from .env).

Run:
    python social_platform.py
"""
from __future__ import annotations

import os
import re
import sys
import textwrap
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Azure OpenAI client
# ---------------------------------------------------------------------------

def _build_client() -> AzureOpenAI:
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key  = os.environ.get("AZURE_OPENAI_API_KEY")
    api_ver  = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    if not endpoint:
        sys.exit(
            "ERROR: AZURE_OPENAI_ENDPOINT is not set.\n"
            "Add it to your .env file:\n"
            "  AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/\n"
        )

    if api_key:
        return AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_ver)

    # No API key — try Azure AD (requires azure-identity package)
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        credential     = DefaultAzureCredential()
        token_provider = get_bearer_token_provider(
            credential, "https://cognitiveservices.azure.com/.default"
        )
        return AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_ver,
        )
    except ImportError:
        sys.exit(
            "ERROR: AZURE_OPENAI_API_KEY is not set and azure-identity is not installed.\n"
            "Either:\n"
            "  1. Add AZURE_OPENAI_API_KEY=<your-key> to .env\n"
            "  2. Install azure-identity:  pip install azure-identity\n"
        )


_client    = _build_client()
_DEPLOYMENT = (
    os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
    or os.environ.get("AZURE_DEPLOYMENT_NAME", "gpt-4o")
)

# ---------------------------------------------------------------------------
# Agent definitions — 10 distinct personalities
# ---------------------------------------------------------------------------

@dataclass
class AgentProfile:
    name: str
    handle: str          # @username shown in feed
    avatar: str          # single emoji used as avatar
    color: str           # ANSI escape for terminal coloring
    system_prompt: str   # personality instruction for the LLM

AGENTS: List[AgentProfile] = [
    AgentProfile(
        name="Alex",
        handle="@alex_the_optimist",
        avatar="☀️",
        color="\033[93m",   # yellow
        system_prompt=(
            "You are Alex, an enthusiastic optimist on a social media platform. "
            "You always find the silver lining, are upbeat, use exclamation points, "
            "and genuinely believe things will work out. You celebrate others' points "
            "when you agree and gently reframe negatives as opportunities. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Morgan",
        handle="@morgan_skeptic",
        avatar="🔍",
        color="\033[90m",   # dark grey
        system_prompt=(
            "You are Morgan, a hard-nosed skeptic who demands receipts. "
            "You question every claim, ask for sources, and call out logical fallacies. "
            "You are not mean but you are blunt. You use phrases like 'citation needed', "
            "'where's the evidence?', and 'that's a bold claim'. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Jordan",
        handle="@jordan_philosopher",
        avatar="🦉",
        color="\033[96m",   # cyan
        system_prompt=(
            "You are Jordan, a deep philosopher who connects everything to big ideas. "
            "You ask 'but what does this mean for humanity?', reference Plato, Nietzsche, "
            "Camus, or similar thinkers when relevant, and enjoy paradoxes. "
            "Your tone is thoughtful and slightly academic but accessible. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Sam",
        handle="@sam_pragmatist",
        avatar="🔧",
        color="\033[32m",   # green
        system_prompt=(
            "You are Sam, a no-nonsense pragmatist. You cut through theory and "
            "ask 'okay but what do we actually DO about this?' You focus on "
            "actionable steps, feasibility, and real-world constraints. "
            "You are impatient with abstract debates that lead nowhere. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Riley",
        handle="@riley_empath",
        avatar="💙",
        color="\033[94m",   # blue
        system_prompt=(
            "You are Riley, a deeply empathetic person who centers the human "
            "emotional experience. You consider how people feel, the vulnerable "
            "and marginalized, and the psychological toll of issues. "
            "You use warm, compassionate language and often say 'imagine how X must feel'. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Casey",
        handle="@casey_contrarian",
        avatar="😈",
        color="\033[91m",   # red
        system_prompt=(
            "You are Casey, a provocateur and devil's advocate. You instinctively "
            "argue the opposite of whatever consensus is forming, not because you're "
            "trolling but because you believe unchallenged views are dangerous. "
            "You enjoy saying 'actually, have you considered...' and flipping assumptions. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Taylor",
        handle="@taylor_expert",
        avatar="📊",
        color="\033[35m",   # magenta
        system_prompt=(
            "You are Taylor, a domain expert who loves citing data and studies. "
            "You use precise language, reference statistics, and correct "
            "misconceptions with authoritative calm. You say things like "
            "'research indicates', 'the data suggests', and 'technically speaking'. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Blake",
        handle="@blake_humorist",
        avatar="😂",
        color="\033[33m",   # dark yellow
        system_prompt=(
            "You are Blake, the group's comedian. You use wit, sarcasm, and "
            "absurd analogies to make points. You can't resist a pun or a pop-culture "
            "reference. Even serious topics get a playful angle from you, though "
            "you know when to dial it back slightly. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Quinn",
        handle="@quinn_activist",
        avatar="✊",
        color="\033[92m",   # bright green
        system_prompt=(
            "You are Quinn, a passionate social activist. You connect every topic "
            "to systemic power, justice, and collective action. You are fired up, "
            "use phrases like 'this is why we need to...', and end messages with "
            "a call to action. You hold others accountable for their blind spots. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
    AgentProfile(
        name="Drew",
        handle="@drew_analyst",
        avatar="⚖️",
        color="\033[97m",   # white
        system_prompt=(
            "You are Drew, a balanced analyst who weighs all sides objectively. "
            "You present pros and cons, avoid taking strong personal stances, "
            "and synthesize multiple viewpoints. You say things like 'on one hand... "
            "on the other hand' and 'it's more nuanced than that'. "
            "Keep replies under 80 words. You may tag other users by their @handle."
        ),
    ),
]

# Map handle → profile for easy lookup
_AGENT_BY_HANDLE: dict[str, AgentProfile] = {a.handle: a for a in AGENTS}

# ---------------------------------------------------------------------------
# Message dataclass
# ---------------------------------------------------------------------------

@dataclass
class Post:
    agent: AgentProfile
    turn: int           # 1-based turn number for this agent
    content: str
    reply_to: Optional[str] = None   # handle of agent being replied to

# ---------------------------------------------------------------------------
# Terminal rendering
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"

_TERMINAL_WIDTH = 80


def _wrap(text: str, indent: int = 4) -> str:
    prefix = " " * indent
    return textwrap.fill(text, width=_TERMINAL_WIDTH - indent, initial_indent=prefix, subsequent_indent=prefix)


def render_post(post: Post, post_index: int) -> None:
    a = post.agent
    sep = f"{DIM}{'─' * _TERMINAL_WIDTH}{RESET}"
    reply_line = f"  {DIM}↳ replying to {post.reply_to}{RESET}\n" if post.reply_to else ""
    header = (
        f"{a.color}{BOLD}{a.avatar}  {a.name}{RESET}"
        f"  {DIM}{a.handle}{RESET}"
        f"  {DIM}[turn {post.turn}/5  •  post #{post_index}]{RESET}"
    )
    print(sep)
    print(header)
    if reply_line:
        print(reply_line, end="")
    print(_wrap(post.content))
    print()


def render_header(topic: str) -> None:
    border = "═" * _TERMINAL_WIDTH
    print(f"\n{BOLD}{border}{RESET}")
    title = "  🌐  AI SOCIAL MEDIA PLATFORM  🌐"
    print(f"{BOLD}{title.center(_TERMINAL_WIDTH)}{RESET}")
    print(f"{BOLD}{border}{RESET}")
    topic_line = f"  Topic: {topic}"
    print(f"{BOLD}{topic_line}{RESET}")
    agents_line = "  Agents: " + "  ".join(f"{a.avatar}{a.name}" for a in AGENTS)
    # word-wrap agent list
    wrapped = textwrap.fill(agents_line, width=_TERMINAL_WIDTH, subsequent_indent="          ")
    print(wrapped)
    print(f"{BOLD}{'─' * _TERMINAL_WIDTH}{RESET}\n")


def render_footer(posts: List[Post]) -> None:
    border = "═" * _TERMINAL_WIDTH
    print(f"\n{BOLD}{border}{RESET}")
    print(f"{BOLD}{'  DISCUSSION COMPLETE':^{_TERMINAL_WIDTH}}{RESET}")
    print(f"{BOLD}{border}{RESET}")
    print(f"  Total posts : {len(posts)}")
    print(f"  Agents      : {len(AGENTS)}")
    print(f"  Turns/agent : 5")
    print(f"{BOLD}{border}{RESET}\n")

# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _build_conversation_context(topic: str, history: List[Post]) -> str:
    """Serialize the conversation so far into a readable feed for the LLM."""
    if not history:
        return f"[The discussion has just started. The topic is: {topic}]"
    lines = [f"[Discussion topic: {topic}]\n"]
    for p in history:
        reply = f" (replying to {p.reply_to})" if p.reply_to else ""
        lines.append(f"{p.agent.name} {p.agent.handle}{reply}:\n{p.content}\n")
    return "\n".join(lines)


def _pick_reply_target(agent: AgentProfile, history: List[Post]) -> Optional[str]:
    """Return a handle to reply to — prefer the most recent post not by this agent."""
    for post in reversed(history):
        if post.agent.handle != agent.handle:
            return post.agent.handle
    return None


def generate_post(
    agent: AgentProfile,
    topic: str,
    history: List[Post],
    turn: int,
    *,
    max_tokens: int = 5000,
    deployment: Optional[str] = None,
    word_limit: int = 80,
    reply_threading: bool = True,
    active_agents: Optional[List[AgentProfile]] = None,
) -> Post:
    """Call Azure OpenAI and return a Post for this agent's turn."""
    reply_to = _pick_reply_target(agent, history) if reply_threading else None
    context  = _build_conversation_context(topic, history)

    # Substitute word limit in system prompt if different from the hardcoded default
    system_content = re.sub(
        r"Keep replies under \d+ words\.",
        f"Keep replies under {word_limit} words.",
        agent.system_prompt,
    )

    roster = active_agents or AGENTS
    if turn == 1:
        user_msg = (
            f"The group is starting a new discussion. The topic is:\n\n\"{topic}\"\n\n"
            f"Give your opening take on this topic in character. "
            f"Other participants are: "
            + ", ".join(f"{a.name} ({a.handle})" for a in roster if a.handle != agent.handle)
            + "."
        )
    else:
        user_msg = (
            f"Here is the conversation so far:\n\n{context}\n\n"
            f"It is now your turn (turn {turn}). "
            f"Reply to the ongoing discussion"
            + (f", especially to {reply_to} if relevant" if reply_to else "")
            + ". Stay in character."
        )

    response = _client.chat.completions.create(
        model=deployment or _DEPLOYMENT,
        messages=[
            {"role": "developer", "content": system_content},
            {"role": "user",      "content": user_msg},
        ],
        max_completion_tokens=max_tokens,
    )
    choice  = response.choices[0]
    content = choice.message.content

    # Thinking models can return None content when only reasoning tokens exist
    if not content:
        finish = choice.finish_reason
        raise ValueError(
            f"Model returned empty content (finish_reason={finish!r}). "
            "The model may have used all tokens on reasoning. Try raising max_completion_tokens."
        )

    return Post(agent=agent, turn=turn, content=content.strip(), reply_to=reply_to if turn > 1 else None)

# ---------------------------------------------------------------------------
# Conversation orchestration
# ---------------------------------------------------------------------------

TURNS_PER_AGENT = 5


def run_discussion(topic: str) -> List[Post]:
    """
    Orchestrate 10 agents × 5 turns.
    Order: round-robin across all agents, 5 full rounds.
    Each agent sees the full history up to their post.
    """
    all_posts: List[Post] = []
    agent_turn_count: dict[str, int] = {a.handle: 0 for a in AGENTS}

    render_header(topic)

    for round_num in range(1, TURNS_PER_AGENT + 1):
        round_label = f"  ── Round {round_num} of {TURNS_PER_AGENT} ──"
        print(f"\n{BOLD}{round_label.center(_TERMINAL_WIDTH)}{RESET}\n")

        for agent in AGENTS:
            agent_turn_count[agent.handle] += 1
            turn = agent_turn_count[agent.handle]

            # Animated spinner while the thinking model reasons
            result: dict = {}
            stop_spinner = threading.Event()

            def _spinner() -> None:
                frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                i = 0
                while not stop_spinner.is_set():
                    elapsed = int(time.perf_counter() - result.get("t0", time.perf_counter()))
                    frame   = frames[i % len(frames)]
                    sys.stdout.write(
                        f"\r  {agent.color}{agent.avatar} {agent.name}{RESET}"
                        f"  {frame} thinking...  {elapsed}s   "
                    )
                    sys.stdout.flush()
                    i += 1
                    time.sleep(0.1)
                sys.stdout.write("\r" + " " * 70 + "\r")
                sys.stdout.flush()

            result["t0"] = time.perf_counter()
            spinner_thread = threading.Thread(target=_spinner, daemon=True)
            spinner_thread.start()

            try:
                post = generate_post(agent, topic, all_posts, turn)
            except Exception as exc:
                stop_spinner.set()
                spinner_thread.join()
                print(f"  ⚠️  {agent.name} encountered an error: {exc}")
                continue
            finally:
                stop_spinner.set()
                spinner_thread.join()

            all_posts.append(post)
            render_post(post, len(all_posts))

            time.sleep(0.2)

    return all_posts

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI Social Media Platform")
    parser.add_argument(
        "--topic",
        type=str,
        default="",
        help="Discussion topic (skips the interactive prompt and auto-saves)",
    )
    args = parser.parse_args()

    if args.topic.strip():
        topic = args.topic.strip()
        print(f"\n{BOLD}🌐 AI Social Media Platform{RESET}")
        print(f"Topic: {topic}\n")
    else:
        print(f"\n{BOLD}🌐 Welcome to the AI Social Media Platform{RESET}")
        print("10 AI agents with distinct personalities will discuss any topic you choose.")
        print("Each agent gets 5 turns to speak. Sit back and read the debate unfold.\n")
        topic = input(f"{BOLD}Enter a discussion topic: {RESET}").strip()
        if not topic:
            print("No topic entered. Exiting.")
            sys.exit(0)

    posts = run_discussion(topic)
    render_footer(posts)

    transcript_dir = Path("/app/transcripts")
    transcript_dir.mkdir(parents=True, exist_ok=True)
    out_path = transcript_dir / f"transcript_{topic[:30].replace(' ', '_')}.txt"

    if args.topic.strip():
        # Non-interactive mode: always save
        save = "y"
    else:
        save = input("Save transcript to file? [y/N]: ").strip().lower()

    if save == "y":
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"AI Social Media Platform — Transcript\n")
            f.write(f"Topic: {topic}\n")
            f.write("=" * 60 + "\n\n")
            for i, p in enumerate(posts, 1):
                reply = f" (replying to {p.reply_to})" if p.reply_to else ""
                f.write(f"[Post #{i}] {p.agent.name} {p.agent.handle} — Turn {p.turn}/5{reply}\n")
                f.write(p.content + "\n\n")
        print(f"Transcript saved to {out_path}")


if __name__ == "__main__":
    main()
