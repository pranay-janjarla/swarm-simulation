"""
test_agents.py — step-by-step diagnostic for the social platform
=================================================================
Run inside Docker:
    docker compose run --rm social python test_agents.py

Tests each layer independently so you can see exactly where it breaks.
"""
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

endpoint   = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
api_key    = os.environ.get("AZURE_OPENAI_API_KEY", "")
api_ver    = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5")

print(f"Endpoint   : {endpoint}")
print(f"Deployment : {deployment}")
print(f"API version: {api_ver}")
print(f"API key set: {'YES' if api_key else 'NO'}\n")

client = AzureOpenAI(azure_endpoint=endpoint, api_key=api_key, api_version=api_ver)

TOPIC = "Should AI replace human jobs?"

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def call(messages: list, label: str) -> str | None:
    print(f"  Calling API ({label})...")
    try:
        resp = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_completion_tokens=5000,
        )
        choice  = resp.choices[0]
        content = choice.message.content
        reason  = choice.finish_reason
        print(f"  finish_reason : {reason}")
        print(f"  content       : {repr(content[:120]) if content else 'None  <-- PROBLEM'}")
        if resp.usage:
            print(f"  tokens        : prompt={resp.usage.prompt_tokens}  "
                  f"completion={resp.usage.completion_tokens}")
        return content
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return None

def sep(title: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

# ---------------------------------------------------------------------------
# STEP 1 — bare minimum: single user message, no role shenanigans
# ---------------------------------------------------------------------------
sep("STEP 1 — bare user message only")
reply1 = call(
    [{"role": "user", "content": f"In one sentence, what do you think about: {TOPIC}"}],
    "bare user message"
)
if not reply1:
    print("\nFAIL: Basic API call returned no content. Check endpoint/key/deployment.")
    sys.exit(1)
print(f"\nPASS: Got reply: {reply1[:100]}")

# ---------------------------------------------------------------------------
# STEP 2 — developer role (replaces 'system' for o1/gpt-5 thinking models)
# ---------------------------------------------------------------------------
sep("STEP 2 — developer role (gpt-5 style)")
reply2 = call(
    [
        {"role": "developer", "content": "You are an optimist. Always be upbeat and positive."},
        {"role": "user",      "content": f"Give your take on: {TOPIC}"},
    ],
    "developer role"
)
if not reply2:
    print("\nFAIL at developer role — trying without it (merge into user message)...")
    reply2 = call(
        [{"role": "user", "content":
          f"You are an optimist. Always be upbeat.\nGive your take on: {TOPIC}"}],
        "personality in user message"
    )
if reply2:
    print(f"\nPASS: Got reply: {reply2[:100]}")
else:
    print("\nFAIL: Cannot get a personality-flavoured reply.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# STEP 3 — agent A posts, agent B reads it and replies
# ---------------------------------------------------------------------------
sep("STEP 3 — Agent A posts, Agent B reads and replies")

agent_a_personality = "You are Alex, an optimist. Be upbeat."
agent_b_personality = "You are Morgan, a skeptic. Demand evidence."

# Agent A turn 1
post_a = call(
    [
        {"role": "developer", "content": agent_a_personality},
        {"role": "user",      "content": f'The topic is: "{TOPIC}". Give your opening take.'},
    ],
    "Agent A turn 1"
)
if not post_a:
    print("\nFAIL: Agent A produced no content.")
    sys.exit(1)
print(f"\nAgent A said: {post_a[:150]}")

# Agent B reads Agent A and replies
context = f"[Topic: {TOPIC}]\n\nAlex @alex_the_optimist:\n{post_a}"
post_b = call(
    [
        {"role": "developer", "content": agent_b_personality},
        {"role": "user",      "content":
            f"Here is the conversation so far:\n\n{context}\n\n"
            f"Reply to @alex_the_optimist. Stay in character."},
    ],
    "Agent B reads A and replies"
)
if not post_b:
    print("\nFAIL: Agent B produced no content after reading Agent A.")
    sys.exit(1)
print(f"\nAgent B replied: {post_b[:150]}")

# ---------------------------------------------------------------------------
# STEP 4 — Agent C reads both A and B, replies to B
# ---------------------------------------------------------------------------
sep("STEP 4 — Agent C reads A+B, replies to B")

agent_c_personality = "You are Sam, a pragmatist. Focus on actionable steps."
context_ab = (
    f"[Topic: {TOPIC}]\n\n"
    f"Alex @alex_the_optimist:\n{post_a}\n\n"
    f"Morgan @morgan_skeptic:\n{post_b}"
)
post_c = call(
    [
        {"role": "developer", "content": agent_c_personality},
        {"role": "user",      "content":
            f"Here is the conversation so far:\n\n{context_ab}\n\n"
            f"Reply to @morgan_skeptic. Stay in character."},
    ],
    "Agent C reads A+B, replies to B"
)
if not post_c:
    print("\nFAIL: Agent C produced no content.")
    sys.exit(1)
print(f"\nAgent C replied: {post_c[:150]}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
sep("ALL STEPS PASSED")
print("  The API, developer role, and agent-reply chain all work.")
print("  You can now run the full platform:\n")
print("    docker compose run --rm social\n")
