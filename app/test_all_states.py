from agents.state_agent import StateIntelligenceAgent


def main():

    print("=" * 60)
    print("      IAC STATE INTELLIGENCE AGENT")
    print("=" * 60)

    agent = StateIntelligenceAgent()

    reports = agent.analyse_all_states()

    print("\n")
    print("=" * 60)
    print(f"Successfully Generated {len(reports)} State Reports")
    print("=" * 60)

    agent.close()


if __name__ == "__main__":
    main()