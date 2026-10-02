"""
Agent 2: Campaign Strategy Agent
----------------------------------
Reads state_intelligence.json (Agent 1's output), groups states by cluster,
and generates a distinct, data-grounded campaign strategy for every state —
using the MINIMUM number of Gemini API calls needed for reliable output.

Prompt templates live in campaign_prompt.py (kept separate from agent logic).

Design notes:
- Clusters are NOT called 1-per-call blindly. Large clusters are split into
  chunks (default max 4 states/call) because an oversized single call risks
  truncated/malformed JSON and generic, copy-pasted campaign content.
- Every call explicitly injects each state's real metrics AND Agent 1's
  analysis (summary/strengths/challenges/recommendation) into the prompt,
  matching the original single-state schema exactly.
- Every response is validated (all expected states present + valid JSON)
  and retried automatically if it fails.
- Rate-limited with a delay between calls to stay within free-tier limits.
- If a chunk fails all retries, individual states in it are retried one at a
  time using the single-state fallback prompt, so a single bad batch doesn't
  lose multiple states' worth of data.

Output: campaign_strategy.json, keyed by state name.
"""

import json
import time
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import GOOGLE_API_KEY
from prompts.campaign_prompt import (
    CAMPAIGN_PROMPT_MULTI_STATE,
    CAMPAIGN_PROMPT_SINGLE_STATE,
    STATE_BLOCK_TEMPLATE,
)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

INPUT_FILE = Path("outputs/state_intelligence.json")
OUTPUT_FILE = Path("outputs/campaign_strategy.json")

MAX_STATES_PER_CALL = 4      # caps batch size regardless of cluster size
MAX_RETRIES = 2               # retries per chunk if validation fails
RETRY_WAIT_SECONDS = 8
RATE_LIMIT_WAIT_SECONDS = 45
CALL_DELAY_SECONDS = 5        # delay between successful calls


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------

class CampaignStrategyAgent:
    """
    Agent 2

    Reads Agent 1's state intelligence output, groups states by cluster,
    and generates personalized multi-channel campaign strategies with
    minimal, reliable API usage.
    """

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.4,
        )

    # --------------------------------------------------
    # Loading Agent 1's output
    # --------------------------------------------------

    def load_state_intelligence(self):
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = data.get("reports", data)
            if isinstance(data, dict):
                data = list(data.values())

        successful = [entry for entry in data if entry.get("status") == "success"]
        if len(successful) != len(data):
            skipped = len(data) - len(successful)
            print(f"Warning: skipping {skipped} entries with non-success status.")

        return successful

    def group_by_cluster(self, entries):
        clusters = {}
        for entry in entries:
            profile = entry["profile"]
            cluster_id = profile["cluster"]
            clusters.setdefault(cluster_id, []).append(entry)
        return clusters

    def chunk_entries(self, entry_list, max_size=MAX_STATES_PER_CALL):
        for i in range(0, len(entry_list), max_size):
            yield entry_list[i:i + max_size]

    # --------------------------------------------------
    # Prompt building
    # --------------------------------------------------

    def format_list_field(self, value):
        """Agent 1 stores strengths/challenges/recommended_strategy as lists."""
        if isinstance(value, list):
            return "\n".join(f"- {item}" for item in value)
        return str(value)

    def build_state_block(self, entry):
        profile = entry["profile"]
        analysis = entry.get("analysis", {})

        return STATE_BLOCK_TEMPLATE.format(
            state=profile["state"],
            channels=profile.get("channels", ""),
            literacy=profile["literacy"],
            urban=profile["urban"],
            density=profile["density"],
            youth=profile["youth"],
            pmkvy=profile["pmkvy"],
            unemployment=profile["unemployment"],
            summary=analysis.get("summary", ""),
            strengths=self.format_list_field(analysis.get("strengths", [])),
            challenges=self.format_list_field(analysis.get("challenges", [])),
            recommendation=analysis.get(
                "final_recommendation",
                self.format_list_field(analysis.get("recommended_strategy", [])),
            ),
        )

    def build_multi_state_prompt(self, chunk):
        first_profile = chunk[0]["profile"]
        states_block = "\n".join(self.build_state_block(entry) for entry in chunk)

        return CAMPAIGN_PROMPT_MULTI_STATE.format(
            cluster=first_profile["cluster"],
            persona=first_profile["persona"],
            priority=first_profile["priority"],
            states_block=states_block,
        )

    def build_single_state_prompt(self, entry):
        profile = entry["profile"]
        analysis = entry.get("analysis", {})

        return CAMPAIGN_PROMPT_SINGLE_STATE.format(
            state=profile["state"],
            cluster=profile["cluster"],
            persona=profile["persona"],
            priority=profile["priority"],
            channels=profile.get("channels", ""),
            literacy=profile["literacy"],
            urban=profile["urban"],
            density=profile["density"],
            youth=profile["youth"],
            pmkvy=profile["pmkvy"],
            unemployment=profile["unemployment"],
            summary=analysis.get("summary", ""),
            strengths=self.format_list_field(analysis.get("strengths", [])),
            challenges=self.format_list_field(analysis.get("challenges", [])),
            recommendation=analysis.get(
                "final_recommendation",
                self.format_list_field(analysis.get("recommended_strategy", [])),
            ),
        )

    # --------------------------------------------------
    # LLM calls
    # --------------------------------------------------

    def clean_json_text(self, text):
        text = text.strip()
        text = text.replace("```json", "").replace("```", "")
        return text.strip()

    def extract_text(self, content):
        """
        response.content from ChatGoogleGenerativeAI is normally a string,
        but Gemini sometimes returns multi-part responses, in which case
        LangChain gives back a list of parts (strings or dicts with a
        'text' key). Normalize either case into a single string.
        """
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    parts.append(part["text"])
            return "".join(parts)

        # Fallback: force to string rather than crash
        return str(content)

    def call_llm(self, prompt):
        response = self.llm.invoke(prompt)
        text = self.extract_text(response.content)
        return self.clean_json_text(text)

    def call_chunk_with_retry(self, chunk):
        expected_states = [entry["profile"]["state"] for entry in chunk]
        prompt = self.build_multi_state_prompt(chunk)

        for attempt in range(1, MAX_RETRIES + 2):
            try:
                text = self.call_llm(prompt)
                data = json.loads(text)

                missing = [s for s in expected_states if s not in data]
                if not missing:
                    return data

                print(f"    Attempt {attempt}: missing states {missing}, retrying...")

            except json.JSONDecodeError:
                print(f"    Attempt {attempt}: malformed JSON, retrying...")

            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e):
                    print(f"    Attempt {attempt}: rate limited, waiting {RATE_LIMIT_WAIT_SECONDS}s...")
                    time.sleep(RATE_LIMIT_WAIT_SECONDS)
                    continue
                else:
                    print(f"    Attempt {attempt}: error - {e}, retrying...")

            time.sleep(RETRY_WAIT_SECONDS)

        # Chunk-level batch failed after all retries.
        # Fall back to retrying each state individually (single-state prompt)
        # so a bad batch doesn't lose every state in it.
        print(f"    Batch failed after {MAX_RETRIES + 1} attempts. "
              f"Falling back to single-state calls for: {expected_states}")

        results = {}
        for entry in chunk:
            results.update(self.call_single_state_with_retry(entry))
            time.sleep(CALL_DELAY_SECONDS)
        return results

    def call_single_state_with_retry(self, entry):
        state_name = entry["profile"]["state"]
        prompt = self.build_single_state_prompt(entry)

        for attempt in range(1, MAX_RETRIES + 2):
            try:
                text = self.call_llm(prompt)
                data = json.loads(text)
                return {state_name: data}

            except json.JSONDecodeError:
                print(f"      {state_name} attempt {attempt}: malformed JSON, retrying...")

            except Exception as e:
                if "RESOURCE_EXHAUSTED" in str(e):
                    print(f"      {state_name} attempt {attempt}: rate limited, waiting...")
                    time.sleep(RATE_LIMIT_WAIT_SECONDS)
                    continue
                else:
                    print(f"      {state_name} attempt {attempt}: error - {e}, retrying...")

            time.sleep(RETRY_WAIT_SECONDS)

        print(f"      FAILED to generate campaign for {state_name}")
        return {
            state_name: {
                "campaign_summary": "GENERATION_FAILED",
                "campaign_objective": "",
                "target_persona": "",
                "campaign_priority": "",
                "communication_channels": [],
                "campaign_duration": "",
                "communication_frequency": "",
                "campaign_phases": {"phase_1": "", "phase_2": "", "phase_3": ""},
                "marketing_message": "",
                "KPIs": [],
                "expected_outcomes": [],
                "_error": True,
            }
        }

    # --------------------------------------------------
    # Orchestration
    # --------------------------------------------------

    def generate_all_campaigns(self):
        entries = self.load_state_intelligence()
        clusters = self.group_by_cluster(entries)

        all_results = {}
        total_calls = 0

        for cluster_id in sorted(clusters.keys()):
            cluster_entries = clusters[cluster_id]
            persona = cluster_entries[0]["profile"]["persona"]

            print(f"\nCluster {cluster_id} ({persona}) — {len(cluster_entries)} states")

            for chunk in self.chunk_entries(cluster_entries):
                chunk_states = [e["profile"]["state"] for e in chunk]
                print(f"  Generating campaigns for: {chunk_states}")

                result = self.call_chunk_with_retry(chunk)
                all_results.update(result)
                total_calls += 1

                time.sleep(CALL_DELAY_SECONDS)

        print(f"\nTotal batch-level API calls used: {total_calls} "
              f"(plus any single-state fallback calls logged above)")
        return all_results

    def save_results(self, results):
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        output = {
            "generated_by": "CampaignStrategyAgent",
            "model": "gemini-2.5-flash",
            "state_count": len(results),
            "campaigns": results,
        }
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        print(f"\nCampaign strategies saved -> {OUTPUT_FILE}")

    def run(self):
        print("=" * 60)
        print("   IAC CAMPAIGN STRATEGY AGENT")
        print("=" * 60)

        results = self.generate_all_campaigns()
        self.save_results(results)

        failed = [s for s, v in results.items() if v.get("_error")]
        if failed:
            print(f"\nWarning: {len(failed)} states failed generation: {failed}")
            print("Re-run to retry — successful states are already saved in the output file.")
        else:
            print(f"\nSuccessfully generated campaign strategies for all {len(results)} states.")

        return results


# --------------------------------------------------------------------------

if __name__ == "__main__":
    agent = CampaignStrategyAgent()
    agent.run()