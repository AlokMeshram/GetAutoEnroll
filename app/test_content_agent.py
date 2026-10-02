"""
Runner script for Agent 3 (Content Generation Agent).

Usage (same pattern as test_all_states.py for Agent 1):
    python -m app.test_content_agent

Requires:
    outputs/state_intelligence.json   (Agent 1 output — must already exist)
    outputs/campaign_strategy.json    (Agent 2 output — must already exist)

Produces:
    outputs/content_pack.json
"""

from pathlib import Path

from agents.content_agent import ContentGenerationAgent


def check_prerequisites():
    """
    Fail fast with a clear message if Agent 1 or Agent 2 outputs are missing,
    instead of letting the agent crash deep inside a Gemini call.
    """
    required_files = {
        "Agent 1 output": Path("outputs/state_intelligence.json"),
        "Agent 2 output": Path("outputs/campaign_strategy.json"),
    }

    missing = [name for name, path in required_files.items() if not path.exists()]

    if missing:
        print("Cannot run Agent 3 — missing required input file(s):")
        for name in missing:
            print(f"  - {name}")
        print("\nRun Agent 1 (test_all_states.py) and Agent 2 (test_campaign_agent.py) first.")
        return False

    return True


def main():
    if not check_prerequisites():
        return

    agent = ContentGenerationAgent()
    results = agent.run()

    print("\n" + "=" * 60)
    print(f"Content generation complete — {len(results)} states processed.")
    print("Output saved to: outputs/content_pack.json")
    print("=" * 60)


if __name__ == "__main__":
    main()