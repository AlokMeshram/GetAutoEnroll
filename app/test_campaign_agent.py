from agents.campaign_agent import CampaignStrategyAgent

agent = CampaignStrategyAgent()

# run() already prints its own headers, executes the full pipeline
# (load -> cluster -> batch calls -> validate/retry -> save), and
# returns the results dict keyed by state name.
campaigns = agent.run()

print("\nFinished.")
print(f"\nGenerated {len(campaigns)} campaign strategies.")

failed_states = [state for state, data in campaigns.items() if data.get("_error")]
if failed_states:
    print(f"States that failed generation: {failed_states}")