"""
Simulation / test harness for Agent 4 (Enrollment Agent).

IMPORTANT: This script does NOT contain any enrollment logic itself.
It only calls EnrollmentAgent's public methods — register_user(),
upload_document(), schedule_orientation(), answer_faq(),
check_and_send_reminders(), get_user_status() — the exact same methods
a real website backend will call later. This script just simulates what
3 different users would do over time, to prove the agent behaves correctly
end-to-end before any real frontend exists.

Usage:
    python -m app.test_enrollment_agent
"""

import json

from agents.enrollment_agent import EnrollmentAgent


def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def main():
    agent = EnrollmentAgent()

    # ----------------------------------------------------------------
    # User 1: Priya (Bihar) — completes the FULL journey end-to-end
    # ----------------------------------------------------------------
    print_section("USER 1: Priya (Bihar) — full journey")

    result = agent.register_user("Priya Kumari", "Bihar", contact="9876543210")
    print("Register:", result["message"])
    priya_id = result["user_id"]

    for doc in ["ID Proof", "Address Proof", "Educational Certificate", "Passport Photo"]:
        r = agent.upload_document(priya_id, doc)
        print(f"Upload '{doc}':", r["message"])

    faq_r = agent.answer_faq(priya_id, "When is my orientation?")
    print("FAQ asked 'When is my orientation?' ->", faq_r["answer"])

    r = agent.schedule_orientation(priya_id, "2026-07-20")
    print("Schedule orientation:", r["message"])

    r = agent.complete_orientation(priya_id)
    print("Complete orientation:", r["message"])

    r = agent.mark_enrolled(priya_id)
    print("Mark enrolled:", r["message"])

    status = agent.get_user_status(priya_id)
    print("\nFinal status for Priya:")
    print(f"  Stage: {status['current_stage']}")
    print(f"  Documents: {status['documents']['uploaded']}")
    print(f"  Activity log entries: {len(status['activity_log'])}")

    # ----------------------------------------------------------------
    # User 2: Rahul (Kerala) — registers, then STALLS (tests reminders)
    # ----------------------------------------------------------------
    print_section("USER 2: Rahul (Kerala) — registers then goes inactive")

    result = agent.register_user("Rahul Menon", "Kerala", contact="9123456780")
    print("Register:", result["message"])
    rahul_id = result["user_id"]

    # Simulate 3 days of inactivity (threshold for REGISTERED stage is 2 days)
    agent._backdate_last_activity(rahul_id, days_ago=3)
    print("(Simulated: Rahul has been inactive for 3 days)")

    # ----------------------------------------------------------------
    # User 3: Meera (Maharashtra) — uploads docs, schedules orientation,
    # then stalls before completing it
    # ----------------------------------------------------------------
    print_section("USER 3: Meera (Maharashtra) — partial journey, then stalls")

    result = agent.register_user("Meera Joshi", "Maharashtra", contact="meera@example.com")
    print("Register:", result["message"])
    meera_id = result["user_id"]

    for doc in ["ID Proof", "Address Proof", "Educational Certificate", "Passport Photo"]:
        agent.upload_document(meera_id, doc)
    print("All documents uploaded.")

    r = agent.schedule_orientation(meera_id, "2026-07-15")
    print("Schedule orientation:", r["message"])

    # Simulate 2 days inactivity after scheduling (threshold is 1 day)
    agent._backdate_last_activity(meera_id, days_ago=2)
    print("(Simulated: Meera has been inactive for 2 days since scheduling)")

    # Ask an FAQ that won't match anything (tests fallback)
    faq_r = agent.answer_faq(meera_id, "Can I get a scholarship for travel?")
    print("FAQ asked (no match expected):", faq_r["answer"])

    # ----------------------------------------------------------------
    # Run the reminder batch job — should catch Rahul + Meera, not Priya
    # ----------------------------------------------------------------
    print_section("REMINDER CHECK (batch job)")

    reminders = agent.check_and_send_reminders()
    print(f"Total reminders triggered: {len(reminders)}\n")
    for r in reminders:
        print(f"  -> {r['name']} (stage: {r['stage']}, inactive {r['days_inactive']} days)")
        print(f"     Message: {r['message']}\n")

    # ----------------------------------------------------------------
    # Final status snapshot for all 3 users
    # ----------------------------------------------------------------
    print_section("FINAL STATUS SNAPSHOT")

    for uid, name in [(priya_id, "Priya"), (rahul_id, "Rahul"), (meera_id, "Meera")]:
        status = agent.get_user_status(uid)
        print(f"{name}: stage={status['current_stage']}, "
              f"docs={len(status['documents']['uploaded'])}/4, "
              f"activity_entries={len(status['activity_log'])}")


if __name__ == "__main__":
    main()