"""
Agent 3: Content Generation Agent
------------------------------------
Reads BOTH:
  - state_intelligence.json (Agent 1: persona, priority, demographics)
  - campaign_strategy.json  (Agent 2: campaign theme, marketing message, channels)

...and generates ready-to-send content (headline, slogan, WhatsApp/SMS/email/
poster/social/community-announcement text, CTA, hashtags, tone) for every state.

Prompt templates live in content_prompt.py (kept separate from agent logic),
same pattern as campaign_prompt.py / campaign_agent.py.

Design notes (same reliability approach as Agent 2):
- Batched by cluster, chunked to a max states-per-call to avoid oversized/
  truncated responses and generic copy-pasted content.
- Every call explicitly injects each state's Agent 2 campaign strategy as
  grounding context, so Agent 3 EXPRESSES the existing strategy rather than
  inventing a new one.
- response.content is normalized via extract_text() to handle both plain
  string and multi-part list responses from Gemini (same fix as Agent 2).
- Every response is validated (all expected states present + valid JSON)
  and retried; a chunk that fails all retries falls back to single-state
  calls so a bad batch doesn't lose multiple states' worth of data.
- Rate-limited with a delay between calls.

Output: content_pack.json, keyed by state name.

NOTE: Language is English-only for now. A future version should extend this
agent to also generate a regional-language version per state (see the
"language" field already present in the output schema for that upgrade path).
"""

import json
import time
from pathlib import Path

from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import GOOGLE_API_KEY
from prompts.content_prompt import (
    CONTENT_PROMPT_MULTI_STATE,
    CONTENT_PROMPT_SINGLE_STATE,
    STATE_CONTENT_BLOCK_TEMPLATE,
)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

STATE_INTELLIGENCE_FILE = Path("outputs/state_intelligence.json")
CAMPAIGN_STRATEGY_FILE = Path("outputs/campaign_strategy.json")
OUTPUT_FILE = Path("outputs/content_pack.json")

MAX_STATES_PER_CALL = 4
MAX_RETRIES = 2
RETRY_WAIT_SECONDS = 8
RATE_LIMIT_WAIT_SECONDS = 45
CALL_DELAY_SECONDS = 5


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------

class ContentGenerationAgent:
    """
    Agent 3

    Reads Agent 1's state intelligence + Agent 2's campaign strategy,
    and generates ready-to-send, channel-specific content per state.
    """

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.5,   # slightly higher: this step is creative writing
        )

    # --------------------------------------------------
    # Loading Agent 1 + Agent 2 outputs and merging them
    # --------------------------------------------------

    def load_state_intelligence(self):
        with open(STATE_INTELLIGENCE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = data.get("reports", data)
            if isinstance(data, dict):
                data = list(data.values())

        return [entry for entry in data if entry.get("status") == "success"]

    def load_campaign_strategy(self):
        with open(CAMPAIGN_STRATEGY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # campaign_strategy.json is wrapped: {"campaigns": {state: {...}}}
        return data.get("campaigns", data)

    def build_merged_states(self):
        """
        Combines Agent 1 profile data with Agent 2 campaign strategy data
        into one list of dicts, one per state, ready for prompt-building.
        """
        intelligence_entries = self.load_state_intelligence()
        campaigns = self.load_campaign_strategy()

        merged = []
        missing_campaigns = []

        for entry in intelligence_entries:
            profile = entry["profile"]
            state_name = profile["state"]
            campaign = campaigns.get(state_name)

            if campaign is None:
                missing_campaigns.append(state_name)
                continue

            if campaign.get("_error"):
                print(f"Warning: {state_name} has a failed campaign strategy, skipping content generation.")
                continue

            merged.append({
                "state": state_name,
                "cluster": profile["cluster"],
                "persona": profile["persona"],
                "priority": profile["priority"],
                "channels": profile.get("channels", ""),
                "campaign_objective": campaign.get("campaign_objective", campaign.get("campaign_summary", "")),
                "marketing_message": campaign.get("marketing_message", ""),
                "target_persona": campaign.get("target_persona", profile["persona"]),
            })

        if missing_campaigns:
            print(f"Warning: no campaign strategy found for: {missing_campaigns} — skipped.")

        return merged

    def group_by_cluster(self, merged_states):
        clusters = {}
        for state in merged_states:
            clusters.setdefault(state["cluster"], []).append(state)
        return clusters

    def chunk_states(self, state_list, max_size=MAX_STATES_PER_CALL):
        for i in range(0, len(state_list), max_size):
            yield state_list[i:i + max_size]

    # --------------------------------------------------
    # Prompt building
    # --------------------------------------------------

    def build_state_block(self, state):
        return STATE_CONTENT_BLOCK_TEMPLATE.format(
            state=state["state"],
            persona=state["persona"],
            priority=state["priority"],
            campaign_objective=state["campaign_objective"],
            marketing_message=state["marketing_message"],
            channels=state["channels"],
            target_persona=state["target_persona"],
        )

    def build_multi_state_prompt(self, chunk):
        first = chunk[0]
        states_block = "\n".join(self.build_state_block(s) for s in chunk)

        return CONTENT_PROMPT_MULTI_STATE.format(
            cluster=first["cluster"],
            persona=first["persona"],
            states_block=states_block,
        )

    def build_single_state_prompt(self, state):
        return CONTENT_PROMPT_SINGLE_STATE.format(
            state=state["state"],
            persona=state["persona"],
            priority=state["priority"],
            campaign_objective=state["campaign_objective"],
            marketing_message=state["marketing_message"],
            channels=state["channels"],
            target_persona=state["target_persona"],
        )

    # --------------------------------------------------
    # LLM calls (same normalization/retry pattern as Agent 2)
    # --------------------------------------------------

    def extract_text(self, content):
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
        return str(content)

    def clean_json_text(self, text):
        text = text.strip()
        text = text.replace("```json", "").replace("```", "")
        return text.strip()

    def call_llm(self, prompt):
        response = self.llm.invoke(prompt)
        text = self.extract_text(response.content)
        return self.clean_json_text(text)

    def call_chunk_with_retry(self, chunk):
        expected_states = [s["state"] for s in chunk]
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

        print(f"    Batch failed after {MAX_RETRIES + 1} attempts. "
              f"Falling back to single-state calls for: {expected_states}")

        results = {}
        for state in chunk:
            results.update(self.call_single_state_with_retry(state))
            time.sleep(CALL_DELAY_SECONDS)
        return results

    def call_single_state_with_retry(self, state):
        state_name = state["state"]
        prompt = self.build_single_state_prompt(state)

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

        print(f"      FAILED to generate content for {state_name}")
        return {
            state_name: {
                "language": "English",
                "campaign_headline": "GENERATION_FAILED",
                "campaign_slogan": "",
                "whatsapp_message": "",
                "sms_message": "",
                "email": {"subject": "", "body": ""},
                "poster_text": "",
                "social_media_caption": "",
                "community_announcement": "",
                "cta": "",
                "hashtags": [],
                "tone": "",
                "_error": True,
            }
        }

    # --------------------------------------------------
    # Orchestration
    # --------------------------------------------------

    def generate_all_content(self):
        merged_states = self.build_merged_states()
        clusters = self.group_by_cluster(merged_states)

        all_results = {}
        total_calls = 0

        for cluster_id in sorted(clusters.keys()):
            cluster_states = clusters[cluster_id]
            persona = cluster_states[0]["persona"]

            print(f"\nCluster {cluster_id} ({persona}) — {len(cluster_states)} states")

            for chunk in self.chunk_states(cluster_states):
                chunk_names = [s["state"] for s in chunk]
                print(f"  Generating content for: {chunk_names}")

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
            "generated_by": "ContentGenerationAgent",
            "model": "gemini-2.5-flash",
            "language_note": "English only — regional language support planned for future version",
            "state_count": len(results),
            "content": results,
        }
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=4, ensure_ascii=False)
        print(f"\nContent pack saved -> {OUTPUT_FILE}")

    def run(self):
        print("=" * 60)
        print("   IAC CONTENT GENERATION AGENT")
        print("=" * 60)

        results = self.generate_all_content()
        self.save_results(results)

        failed = [s for s, v in results.items() if v.get("_error")]
        if failed:
            print(f"\nWarning: {len(failed)} states failed generation: {failed}")
            print("Re-run to retry — successful states are already saved in the output file.")
        else:
            print(f"\nSuccessfully generated content packs for all {len(results)} states.")

        return results


# --------------------------------------------------------------------------

if __name__ == "__main__":
    agent = ContentGenerationAgent()
    agent.run()