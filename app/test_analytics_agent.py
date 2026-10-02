"""
Runner script for Agent 5 (Monitoring & Analytics Agent).

Usage:
    python -m app.test_analytics_agent

Requires:
    iac_gpi_project.db  (Agent 4's live enrollment data — must have at least
                          some registered users for meaningful output)

Produces:
    outputs/analytics_report.json

Note: unlike Agents 1-3, this agent makes NO API calls and can be re-run
as often as needed (e.g. on a schedule, or after every batch of new user
activity) at zero cost — this is what makes it suitable for "real-time"
tracking as required by Task 6.
"""

from agents.analytics_agent import AnalyticsAgent


def main():
    agent = AnalyticsAgent()
    report = agent.run()

    print("\n" + "=" * 60)
    print("Analytics report complete.")
    print(f"Total users tracked: {report['total_users']}")
    print(f"States with dropout risk data: {len(report['dropout_risk_by_state'])}")
    print(f"Strategy flags raised: {len(report['strategy_flags'])}")
    print("Output saved to: outputs/analytics_report.json")
    print("=" * 60)


if __name__ == "__main__":
    main()