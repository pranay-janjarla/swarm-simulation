"""Run this to discover the actual OASIS API in the installed package."""
import oasis
print("=== oasis top-level ===")
print([x for x in dir(oasis) if not x.startswith("_")])

print("\n=== oasis.social_agent.agent_graph ===")
from oasis.social_agent import agent_graph
print([x for x in dir(agent_graph) if not x.startswith("_")])

print("\n=== oasis ActionType values ===")
try:
    from oasis import ActionType
    print(list(ActionType))
except Exception as e:
    print(f"  ActionType import error: {e}")
    try:
        from oasis.actions import ActionType
        print(list(ActionType))
    except Exception as e2:
        print(f"  oasis.actions error: {e2}")
