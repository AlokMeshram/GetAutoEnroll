import json

from agents.state_agent import StateIntelligenceAgent

agent = StateIntelligenceAgent()

result = agent.analyse_state("Bihar")

print("\nPROFILE\n")
print(json.dumps(result["profile"], indent=4))

print("\nANALYSIS\n")
print(json.dumps(result["analysis"], indent=4))

agent.close()