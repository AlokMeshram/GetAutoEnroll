import os
import json
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI

from config.settings import GOOGLE_API_KEY
from config.cluster_config import CLUSTER_CONFIG
from prompts.state_prompt import STATE_ANALYSIS_PROMPT

from utils.database import DatabaseManager


class StateIntelligenceAgent:
    """
    =======================================================
                AGENT 1 : STATE INTELLIGENCE AGENT
    =======================================================

    Responsibilities
    ----------------
    • Reads state information from SQLite
    • Reads ML cluster assignment
    • Maps cluster → persona
    • Generates AI intelligence using Gemini
    • Returns structured JSON report
    • Can analyse one state or all states

    =======================================================
    """

    def __init__(self):

        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            google_api_key=GOOGLE_API_KEY,
            temperature=0.3
        )

        self.db = DatabaseManager()

    # ======================================================

    def get_state_data(self, state_name):

        df = self.db.get_state_information(state_name)

        if df.empty:
            return None

        return df.iloc[0]

    # ======================================================

    def build_state_profile(self, state):

        cluster = int(state["cluster_label"])

        config = CLUSTER_CONFIG[cluster]

        profile = {

            "state": state["state_name"],

            "cluster": cluster,

            "persona": config["persona"],

            "priority": config["priority"],

            "channels": config["recommended_channels"],

            "literacy": float(state["literacy_rate_pct"]),

            "urban": float(state["urban_pct"]),

            "density": float(state["pop_density_per_sq_km"]),

            "youth": float(state["youth_pct_of_population"]),

            "pmkvy": float(state["pmkvy_rate_per_lakh_youth"]),

            "unemployment": float(state["unemp_rate_2023_24"])

        }

        return profile

    # ======================================================

    def generate_analysis(self, profile):

        prompt = STATE_ANALYSIS_PROMPT.format(

            state=profile["state"],

            cluster=profile["cluster"],

            persona=profile["persona"],

            priority=profile["priority"],

            channels=", ".join(profile["channels"]),

            literacy=profile["literacy"],

            urban=profile["urban"],

            density=profile["density"],

            youth=profile["youth"],

            pmkvy=profile["pmkvy"],

            unemployment=profile["unemployment"]

        )

        response = self.llm.invoke(prompt)

        text = self.extract_text(response.content).strip()

        text = text.replace("```json", "")
        text = text.replace("```", "")
        text = text.strip()

        try:

            return json.loads(text)

        except Exception:

            return {

                "summary": text,

                "strengths": [],

                "challenges": [],

                "recommended_strategy": [],

                "final_recommendation": ""

            }

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

    # ======================================================

    def analyse_state(self, state_name):

        state = self.get_state_data(state_name)

        if state is None:

            return {

                "status": "error",

                "message": "State not found."

            }

        profile = self.build_state_profile(state)

        report = self.generate_analysis(profile)

        return {

            "status": "success",

            "profile": profile,

            "analysis": report

        }

    # ======================================================

    def analyse_all_states(self):

        os.makedirs("outputs", exist_ok=True)

        states = self.db.get_all_states()

        all_reports = {}

        for state in states:

            state_name = state[0]

            print(f"Analysing {state_name}...")

            result = self.analyse_state(state_name)

            all_reports[state_name] = result

        output_path = os.path.join(
            "outputs",
            "state_intelligence.json"
        )

        final_output = {

            "metadata": {

                "agent_name": "State Intelligence Agent",

                "version": "1.0",

                "generated_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

                "model": "gemini-2.5-flash",

                "total_states": len(all_reports)

            },

            "reports": all_reports

        }

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                final_output,
                f,
                indent=4,
                ensure_ascii=False
            )

        print("\n✅ State Intelligence Reports Saved!")
        print(output_path)

        return final_output

    # ======================================================

    def close(self):

        self.db.close()