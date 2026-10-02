"""
Agent 5: Monitoring & Analytics Agent
-----------------------------------------
Reads Agent 4's live enrollment database + Agent 1/2's state and campaign
data, and computes real-time engagement, effectiveness, and dropout metrics.

Responsibilities (Task 6):
    - Track engagement metrics       -> funnel counts, FAQ activity, reminders sent
    - Campaign effectiveness         -> conversion rate per state/cluster/channel
    - Dropout rates                  -> % of users stuck at each funnel stage
    - Real-time strategy flags       -> rule-based alerts when a state/cluster
                                         underperforms, to feed back into Agent 2

Design note: fully deterministic (SQL + Python), NO LLM calls — consistent
with Agent 4 and appropriate for "real-time" tracking, which should not
depend on API latency, quota, or non-determinism. This agent can be re-run
as often as needed (e.g. every few minutes) at zero marginal cost.

Input:
    - iac_gpi_project.db (Agent 4's live tables)
    - outputs/state_intelligence.json  (for cluster/persona context)
    - outputs/campaign_strategy.json   (for campaign priority context)

Output:
    - outputs/analytics_report.json
"""

import json
import sqlite3
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from config.enrollment_config import DB_PATH, FUNNEL_STAGES


STATE_INTELLIGENCE_FILE = Path("outputs/state_intelligence.json")
CAMPAIGN_STRATEGY_FILE = Path("outputs/campaign_strategy.json")
OUTPUT_FILE = Path("outputs/analytics_report.json")

# A stage is considered "stalled/dropout risk" if a user has sat in it
# without progressing for this many days. Mirrors Agent 4's reminder
# thresholds conceptually, but used here for reporting, not messaging.
DROPOUT_FLAG_DAYS = {
    "REGISTERED": 5,
    "DOCUMENTS_UPLOADED": 5,
    "ORIENTATION_SCHEDULED": 3,
}

# Rule-based thresholds for flagging a state/cluster as needing strategy attention
HIGH_DROPOUT_THRESHOLD_PCT = 30.0
LOW_FAQ_MATCH_RATE_THRESHOLD_PCT = 60.0


class AnalyticsAgent:
    """
    Agent 5

    Computes real-time engagement, funnel effectiveness, and dropout
    analytics from Agent 4's live database, cross-referenced with
    Agent 1's cluster/persona data and Agent 2's campaign context.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    # --------------------------------------------------
    # Loading supporting context (Agent 1 + Agent 2 outputs)
    # --------------------------------------------------

    def load_state_context(self):
        """Returns {state_name: {cluster, persona, priority}}"""
        context = {}
        if STATE_INTELLIGENCE_FILE.exists():
            with open(STATE_INTELLIGENCE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for entry in data:
                if entry.get("status") == "success":
                    p = entry["profile"]
                    context[p["state"]] = {
                        "cluster": p["cluster"],
                        "persona": p["persona"],
                        "priority": p["priority"],
                    }
        return context

    def load_campaign_context(self):
        """Returns {state_name: {campaign_priority, communication_channels}}"""
        context = {}
        if CAMPAIGN_STRATEGY_FILE.exists():
            with open(CAMPAIGN_STRATEGY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            campaigns = data.get("campaigns", data)
            for state, c in campaigns.items():
                if not c.get("_error"):
                    context[state] = {
                        "campaign_priority": c.get("campaign_priority", ""),
                        "communication_channels": c.get("communication_channels", []),
                    }
        return context

    # --------------------------------------------------
    # DB access
    # --------------------------------------------------

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_all_users(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM enrollment_users").fetchall()
            return [dict(r) for r in rows]

    def fetch_all_activity(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM enrollment_activity_log").fetchall()
            return [dict(r) for r in rows]

    def fetch_all_documents(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM enrollment_documents").fetchall()
            return [dict(r) for r in rows]

    def fetch_all_orientations(self):
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM enrollment_orientation").fetchall()
            return [dict(r) for r in rows]

    # --------------------------------------------------
    # 1. Funnel counts (overall, per state, per cluster)
    # --------------------------------------------------

    def compute_funnel_counts(self, users):
        overall = {stage: 0 for stage in FUNNEL_STAGES}
        by_state = defaultdict(lambda: {stage: 0 for stage in FUNNEL_STAGES})

        for user in users:
            stage = user["current_stage"]
            state = user["state_name"]
            if stage in overall:
                overall[stage] += 1
                by_state[state][stage] += 1

        return overall, dict(by_state)

    def compute_funnel_by_cluster(self, by_state, state_context):
        by_cluster = defaultdict(lambda: {stage: 0 for stage in FUNNEL_STAGES})
        for state, counts in by_state.items():
            cluster = state_context.get(state, {}).get("cluster", "UNKNOWN")
            for stage, n in counts.items():
                by_cluster[cluster][stage] += n
        return dict(by_cluster)

    # --------------------------------------------------
    # 2. Conversion / campaign effectiveness
    # --------------------------------------------------

    def compute_conversion_rates(self, by_state):
        """
        Conversion rate = ENROLLED / total registered, per state.
        This is the clearest "did the campaign actually work" signal.
        """
        conversion = {}
        for state, counts in by_state.items():
            total = sum(counts.values())
            enrolled = counts.get("ENROLLED", 0)
            rate = round((enrolled / total * 100), 2) if total > 0 else 0.0
            conversion[state] = {
                "total_registered": total,
                "enrolled": enrolled,
                "conversion_rate_pct": rate,
            }
        return conversion

    # --------------------------------------------------
    # 3. Dropout analysis
    # --------------------------------------------------

    def compute_dropout_analysis(self, users):
        """
        Flags individual users who have been stuck in a stage beyond the
        threshold for that stage, and aggregates a per-state dropout-risk
        percentage (stuck users / total active users in that state).
        """
        now = datetime.now()
        stuck_users = []
        state_active_counts = defaultdict(int)
        state_stuck_counts = defaultdict(int)

        for user in users:
            if user["status"] != "ACTIVE":
                continue

            state = user["state_name"]
            stage = user["current_stage"]
            state_active_counts[state] += 1

            if stage not in DROPOUT_FLAG_DAYS:
                continue  # ORIENTATION_COMPLETED / ENROLLED are not dropout-risk stages

            last_progress = datetime.fromisoformat(user["last_progress_at"])
            days_stuck = (now - last_progress).days
            threshold = DROPOUT_FLAG_DAYS[stage]

            if days_stuck >= threshold:
                state_stuck_counts[state] += 1
                stuck_users.append({
                    "user_id": user["user_id"],
                    "name": user["name"],
                    "state": state,
                    "stage": stage,
                    "days_stuck": days_stuck,
                })

        state_dropout_pct = {}
        for state, active_count in state_active_counts.items():
            stuck = state_stuck_counts.get(state, 0)
            pct = round((stuck / active_count * 100), 2) if active_count > 0 else 0.0
            state_dropout_pct[state] = {
                "active_users": active_count,
                "stuck_users": stuck,
                "dropout_risk_pct": pct,
            }

        return stuck_users, state_dropout_pct

    # --------------------------------------------------
    # 4. FAQ engagement analysis
    # --------------------------------------------------

    def compute_faq_analytics(self, activity_log):
        faq_events = [a for a in activity_log if a["action"] == "FAQ_ASKED"]
        total = len(faq_events)
        unmatched = sum(1 for a in faq_events if "matched: None" in (a["details"] or ""))
        matched = total - unmatched

        match_rate = round((matched / total * 100), 2) if total > 0 else None

        return {
            "total_faq_questions": total,
            "matched": matched,
            "unmatched": unmatched,
            "match_rate_pct": match_rate,
        }

    # --------------------------------------------------
    # 5. Reminder activity
    # --------------------------------------------------

    def compute_reminder_stats(self, activity_log):
        reminders = [a for a in activity_log if a["action"] == "REMINDER_SENT"]
        by_stage = defaultdict(int)
        for r in reminders:
            details = r["details"] or ""
            for stage in FUNNEL_STAGES:
                if f"stage={stage}" in details:
                    by_stage[stage] += 1
        return {
            "total_reminders_sent": len(reminders),
            "reminders_by_stage": dict(by_stage),
        }

    # --------------------------------------------------
    # 6. Rule-based strategy flags (feeds back toward Agent 2 logic)
    # --------------------------------------------------

    def generate_strategy_flags(self, state_dropout_pct, conversion_rates, faq_analytics, state_context, campaign_context):
        flags = []

        for state, dropout in state_dropout_pct.items():
            if dropout["dropout_risk_pct"] >= HIGH_DROPOUT_THRESHOLD_PCT and dropout["active_users"] > 0:
                cluster_info = state_context.get(state, {})
                flags.append({
                    "type": "HIGH_DROPOUT",
                    "state": state,
                    "cluster": cluster_info.get("cluster", "UNKNOWN"),
                    "persona": cluster_info.get("persona", "UNKNOWN"),
                    "dropout_risk_pct": dropout["dropout_risk_pct"],
                    "recommendation": (
                        f"{state} has {dropout['dropout_risk_pct']}% of active users stuck without "
                        f"progress. Consider increasing reminder frequency or reviewing whether the "
                        f"channels for this persona ({cluster_info.get('persona', 'N/A')}) match actual usage."
                    ),
                })

        for state, conv in conversion_rates.items():
            if conv["total_registered"] >= 3 and conv["conversion_rate_pct"] < 20.0:
                flags.append({
                    "type": "LOW_CONVERSION",
                    "state": state,
                    "conversion_rate_pct": conv["conversion_rate_pct"],
                    "total_registered": conv["total_registered"],
                    "recommendation": (
                        f"{state} shows low conversion ({conv['conversion_rate_pct']}% of "
                        f"{conv['total_registered']} registrations reached ENROLLED). Review "
                        f"the funnel steps for friction points specific to this state."
                    ),
                })

        if faq_analytics["total_faq_questions"] > 0 and faq_analytics["match_rate_pct"] is not None:
            if faq_analytics["match_rate_pct"] < LOW_FAQ_MATCH_RATE_THRESHOLD_PCT:
                flags.append({
                    "type": "FAQ_KNOWLEDGE_GAP",
                    "match_rate_pct": faq_analytics["match_rate_pct"],
                    "unmatched_count": faq_analytics["unmatched"],
                    "recommendation": (
                        f"Only {faq_analytics['match_rate_pct']}% of FAQ questions matched the "
                        f"knowledge base. Review unmatched questions in the activity log and "
                        f"expand FAQ_KNOWLEDGE_BASE in enrollment_config.py."
                    ),
                })

        return flags

    # --------------------------------------------------
    # Orchestration
    # --------------------------------------------------

    def generate_report(self):
        state_context = self.load_state_context()
        campaign_context = self.load_campaign_context()

        users = self.fetch_all_users()
        activity_log = self.fetch_all_activity()

        overall_funnel, by_state_funnel = self.compute_funnel_counts(users)
        by_cluster_funnel = self.compute_funnel_by_cluster(by_state_funnel, state_context)

        conversion_rates = self.compute_conversion_rates(by_state_funnel)
        stuck_users, state_dropout_pct = self.compute_dropout_analysis(users)
        faq_analytics = self.compute_faq_analytics(activity_log)
        reminder_stats = self.compute_reminder_stats(activity_log)

        strategy_flags = self.generate_strategy_flags(
            state_dropout_pct, conversion_rates, faq_analytics, state_context, campaign_context
        )

        report = {
            "generated_by": "AnalyticsAgent",
            "generation_method": "rule-based (deterministic, no LLM calls)",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "total_users": len(users),
            "overall_funnel": overall_funnel,
            "funnel_by_state": by_state_funnel,
            "funnel_by_cluster": by_cluster_funnel,
            "conversion_rates_by_state": conversion_rates,
            "dropout_risk_by_state": state_dropout_pct,
            "stuck_users_detail": stuck_users,
            "faq_analytics": faq_analytics,
            "reminder_stats": reminder_stats,
            "strategy_flags": strategy_flags,
        }

        return report

    def save_report(self, report):
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        print(f"Analytics report saved -> {OUTPUT_FILE}")

    def run(self):
        print("=" * 60)
        print("   IAC MONITORING & ANALYTICS AGENT")
        print("=" * 60)

        report = self.generate_report()
        self.save_report(report)

        print(f"\nTotal users tracked: {report['total_users']}")
        print(f"Overall funnel: {report['overall_funnel']}")
        print(f"Strategy flags raised: {len(report['strategy_flags'])}")
        for flag in report["strategy_flags"]:
            print(f"  [{flag['type']}] {flag.get('state', 'GLOBAL')}: {flag['recommendation']}")

        return report


# --------------------------------------------------------------------------

if __name__ == "__main__":
    agent = AnalyticsAgent()
    agent.run()