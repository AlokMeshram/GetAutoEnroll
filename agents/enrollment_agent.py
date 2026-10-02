"""
Agent 4: Enrollment Agent
----------------------------
Guides an individual user through the IAC enrollment funnel:

    REGISTERED -> DOCUMENTS_UPLOADED -> ORIENTATION_SCHEDULED
               -> ORIENTATION_COMPLETED -> ENROLLED

Responsibilities:
    - Registration guidance      -> register_user()
    - Document upload assistance -> upload_document(), get_document_status()
    - Orientation scheduling     -> schedule_orientation(), complete_orientation()
    - FAQ responses              -> answer_faq()          (rule-based, no LLM)
    - Reminder messages          -> check_and_send_reminders()  (rule-based)
    - Enrollment tracking        -> get_user_status(), mark_enrolled()

Design note — built for reuse by a real website later:
Every method here is a plain, self-contained function that takes simple
arguments and returns a plain dict. This means a future web backend can
call these EXACT same methods directly as request handlers (e.g.
POST /register -> register_user(name, state, contact)) — no rewrite needed.
The simulation script (test_enrollment_agent.py) is just a test harness
calling these same methods; it is not a separate code path.

Storage: SQLite, extends the existing iac_gpi_project.db (adds 4 new
tables, does not touch Agent 1's existing tables).

FAQ + reminders are fully rule-based/deterministic — zero API calls,
zero cost, 100% reproducible, consistent with Agent 4's design goals.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from config.enrollment_config import (
    DB_PATH,
    FUNNEL_STAGES,
    DROPPED_STATUS,
    REQUIRED_DOCUMENTS,
    REMINDER_THRESHOLD_DAYS,
    REMINDER_MESSAGE_TEMPLATES,
    FAQ_KNOWLEDGE_BASE,
    FAQ_FALLBACK_ANSWER,
    FAQ_MATCH_MIN_SCORE,
)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


class EnrollmentAgent:
    """
    Agent 4

    Manages individual user enrollment journeys: registration, document
    upload, orientation scheduling, FAQs, reminders, and status tracking.
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_schema()

    # --------------------------------------------------
    # Setup
    # --------------------------------------------------

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        schema_path = Path(__file__).parent.parent / "config" / "enrollment_schema.sql"
        with self._connect() as conn:
            with open(schema_path, "r", encoding="utf-8") as f:
                conn.executescript(f.read())

    def _log_activity(self, conn, user_id, action, details=""):
        conn.execute(
            "INSERT INTO enrollment_activity_log (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, now_iso()),
        )

    def _touch_last_activity(self, conn, user_id):
        conn.execute(
            "UPDATE enrollment_users SET last_activity_at = ? WHERE user_id = ?",
            (now_iso(), user_id),
        )

    def _touch_last_progress(self, conn, user_id):
        """
        Updates last_progress_at — used ONLY by actions that actually move
        the user forward in the funnel (register, doc upload that advances
        stage, schedule orientation, complete orientation, mark enrolled).

        This is deliberately separate from _touch_last_activity(): a user
        who keeps asking FAQs but never progresses should still receive a
        reminder. If FAQ activity reset the same timestamp used for
        reminder checks, a chatty-but-stuck user would never be reminded —
        exactly the user who most needs the nudge.
        """
        conn.execute(
            "UPDATE enrollment_users SET last_progress_at = ? WHERE user_id = ?",
            (now_iso(), user_id),
        )

    # --------------------------------------------------
    # 1. Registration guidance
    # --------------------------------------------------

    def register_user(self, name, state_name, contact=None):
        """Registers a new user and starts their funnel at REGISTERED."""
        with self._connect() as conn:
            cur = conn.execute(
                """INSERT INTO enrollment_users (name, state_name, contact, current_stage, status,
                                                  registered_at, last_activity_at, last_progress_at)
                   VALUES (?, ?, ?, 'REGISTERED', 'ACTIVE', ?, ?, ?)""",
                (name, state_name, contact, now_iso(), now_iso(), now_iso()),
            )
            user_id = cur.lastrowid
            self._log_activity(conn, user_id, "REGISTERED", f"Registered from {state_name}")

        return {
            "status": "success",
            "user_id": user_id,
            "message": f"Welcome {name}! You're registered. Next step: upload your documents "
                       f"({', '.join(REQUIRED_DOCUMENTS)}).",
            "current_stage": "REGISTERED",
        }

    # --------------------------------------------------
    # 2. Document upload assistance
    # --------------------------------------------------

    def upload_document(self, user_id, document_type):
        """Records one uploaded document. Advances stage once all are uploaded."""
        if document_type not in REQUIRED_DOCUMENTS:
            return {
                "status": "error",
                "message": f"'{document_type}' is not a recognized document type. "
                           f"Required documents: {', '.join(REQUIRED_DOCUMENTS)}.",
            }

        with self._connect() as conn:
            user = conn.execute(
                "SELECT * FROM enrollment_users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                return {"status": "error", "message": "User not found."}

            already = conn.execute(
                "SELECT * FROM enrollment_documents WHERE user_id = ? AND document_type = ?",
                (user_id, document_type),
            ).fetchone()

            if already:
                return {
                    "status": "success",
                    "message": f"'{document_type}' was already uploaded.",
                    "document_status": self._document_status_locked(conn, user_id),
                }

            conn.execute(
                "INSERT INTO enrollment_documents (user_id, document_type, uploaded_at) VALUES (?, ?, ?)",
                (user_id, document_type, now_iso()),
            )
            self._log_activity(conn, user_id, "DOCUMENT_UPLOADED", document_type)
            self._touch_last_activity(conn, user_id)
            self._touch_last_progress(conn, user_id)

            doc_status = self._document_status_locked(conn, user_id)

            # Advance stage if this was the last required document
            if doc_status["all_uploaded"] and user["current_stage"] == "REGISTERED":
                conn.execute(
                    "UPDATE enrollment_users SET current_stage = 'DOCUMENTS_UPLOADED' WHERE user_id = ?",
                    (user_id,),
                )
                self._log_activity(conn, user_id, "STAGE_ADVANCED", "-> DOCUMENTS_UPLOADED")

            return {
                "status": "success",
                "message": f"'{document_type}' uploaded successfully.",
                "document_status": doc_status,
            }

    def _document_status_locked(self, conn, user_id):
        """Internal helper — must be called with an open connection (used inside upload_document)."""
        rows = conn.execute(
            "SELECT document_type FROM enrollment_documents WHERE user_id = ?", (user_id,)
        ).fetchall()
        uploaded = [r["document_type"] for r in rows]
        missing = [d for d in REQUIRED_DOCUMENTS if d not in uploaded]
        return {
            "uploaded": uploaded,
            "missing": missing,
            "all_uploaded": len(missing) == 0,
        }

    def get_document_status(self, user_id):
        """Public method — safe to call anytime, opens its own connection."""
        with self._connect() as conn:
            return self._document_status_locked(conn, user_id)

    # --------------------------------------------------
    # 3. Orientation scheduling
    # --------------------------------------------------

    def schedule_orientation(self, user_id, preferred_date):
        """
        preferred_date: string, e.g. '2026-07-20'. No validation of real
        calendar availability here — that would be a real backend's job.
        """
        with self._connect() as conn:
            user = conn.execute(
                "SELECT * FROM enrollment_users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                return {"status": "error", "message": "User not found."}

            if user["current_stage"] not in ("DOCUMENTS_UPLOADED", "ORIENTATION_SCHEDULED"):
                return {
                    "status": "error",
                    "message": f"Cannot schedule orientation yet — current stage is "
                               f"'{user['current_stage']}'. Documents must be uploaded first.",
                }

            existing = conn.execute(
                "SELECT * FROM enrollment_orientation WHERE user_id = ?", (user_id,)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE enrollment_orientation SET scheduled_date = ?, status = 'SCHEDULED' WHERE user_id = ?",
                    (preferred_date, user_id),
                )
            else:
                conn.execute(
                    "INSERT INTO enrollment_orientation (user_id, scheduled_date, status) VALUES (?, ?, 'SCHEDULED')",
                    (user_id, preferred_date),
                )

            conn.execute(
                "UPDATE enrollment_users SET current_stage = 'ORIENTATION_SCHEDULED' WHERE user_id = ?",
                (user_id,),
            )
            self._log_activity(conn, user_id, "ORIENTATION_SCHEDULED", preferred_date)
            self._touch_last_activity(conn, user_id)
            self._touch_last_progress(conn, user_id)

        return {
            "status": "success",
            "message": f"Orientation scheduled for {preferred_date}.",
            "current_stage": "ORIENTATION_SCHEDULED",
        }

    def complete_orientation(self, user_id):
        with self._connect() as conn:
            user = conn.execute(
                "SELECT * FROM enrollment_users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                return {"status": "error", "message": "User not found."}

            conn.execute(
                "UPDATE enrollment_orientation SET status = 'COMPLETED' WHERE user_id = ?", (user_id,)
            )
            conn.execute(
                "UPDATE enrollment_users SET current_stage = 'ORIENTATION_COMPLETED' WHERE user_id = ?",
                (user_id,),
            )
            self._log_activity(conn, user_id, "ORIENTATION_COMPLETED")
            self._touch_last_activity(conn, user_id)
            self._touch_last_progress(conn, user_id)

        return {"status": "success", "message": "Orientation marked complete.", "current_stage": "ORIENTATION_COMPLETED"}

    # --------------------------------------------------
    # 6. Enrollment tracking (finalize)
    # --------------------------------------------------

    def mark_enrolled(self, user_id):
        with self._connect() as conn:
            user = conn.execute(
                "SELECT * FROM enrollment_users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                return {"status": "error", "message": "User not found."}

            if user["current_stage"] != "ORIENTATION_COMPLETED":
                return {
                    "status": "error",
                    "message": f"Cannot enroll yet — current stage is '{user['current_stage']}'. "
                               f"Orientation must be completed first.",
                }

            conn.execute(
                "UPDATE enrollment_users SET current_stage = 'ENROLLED' WHERE user_id = ?", (user_id,)
            )
            self._log_activity(conn, user_id, "ENROLLED")
            self._touch_last_activity(conn, user_id)
            self._touch_last_progress(conn, user_id)

        return {"status": "success", "message": "User successfully enrolled!", "current_stage": "ENROLLED"}

    def get_user_status(self, user_id):
        with self._connect() as conn:
            user = conn.execute(
                "SELECT * FROM enrollment_users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                return {"status": "error", "message": "User not found."}

            doc_status = self._document_status_locked(conn, user_id)

            orientation = conn.execute(
                "SELECT * FROM enrollment_orientation WHERE user_id = ?", (user_id,)
            ).fetchone()

            activity = conn.execute(
                "SELECT action, details, timestamp FROM enrollment_activity_log WHERE user_id = ? ORDER BY timestamp",
                (user_id,),
            ).fetchall()

        return {
            "status": "success",
            "user_id": user_id,
            "name": user["name"],
            "state": user["state_name"],
            "current_stage": user["current_stage"],
            "account_status": user["status"],
            "registered_at": user["registered_at"],
            "last_activity_at": user["last_activity_at"],
            "last_progress_at": user["last_progress_at"],
            "documents": doc_status,
            "orientation": dict(orientation) if orientation else None,
            "activity_log": [dict(a) for a in activity],
        }

    # --------------------------------------------------
    # 4. FAQ responses (rule-based, no LLM)
    # --------------------------------------------------

    def answer_faq(self, user_id, question_text):
        question_lower = question_text.lower()

        best_match = None
        best_score = 0

        for entry in FAQ_KNOWLEDGE_BASE:
            score = sum(1 for kw in entry["keywords"] if kw in question_lower)
            if score > best_score:
                best_score = score
                best_match = entry

        if best_match and best_score >= FAQ_MATCH_MIN_SCORE:
            answer = best_match["answer"]
            matched_id = best_match["id"]
        else:
            answer = FAQ_FALLBACK_ANSWER
            matched_id = None

        with self._connect() as conn:
            self._log_activity(conn, user_id, "FAQ_ASKED", f"Q: {question_text} | matched: {matched_id}")
            self._touch_last_activity(conn, user_id)

        return {
            "status": "success",
            "question": question_text,
            "answer": answer,
            "matched_faq_id": matched_id,
        }

    # --------------------------------------------------
    # 5. Reminder messages (rule-based, no LLM)
    # --------------------------------------------------

    def check_and_send_reminders(self):
        """
        Batch job — checks every ACTIVE user for stalled progress and
        generates (simulated) reminder messages. In a real deployment this
        would actually dispatch via SMS/WhatsApp API; here it returns the
        list of reminders that WOULD be sent, for logging/testing.
        """
        reminders_sent = []
        now = datetime.now()

        with self._connect() as conn:
            users = conn.execute(
                "SELECT * FROM enrollment_users WHERE status = 'ACTIVE'"
            ).fetchall()

            for user in users:
                stage = user["current_stage"]
                if stage not in REMINDER_THRESHOLD_DAYS:
                    continue  # ORIENTATION_COMPLETED / ENROLLED don't need reminders

                last_progress = datetime.fromisoformat(user["last_progress_at"])
                days_inactive = (now - last_progress).days
                threshold = REMINDER_THRESHOLD_DAYS[stage]

                if days_inactive >= threshold:
                    template = REMINDER_MESSAGE_TEMPLATES[stage]

                    if stage == "REGISTERED":
                        doc_status = self._document_status_locked(conn, user["user_id"])
                        message = template.format(
                            name=user["name"],
                            doc_list=", ".join(doc_status["missing"]),
                        )
                    elif stage == "ORIENTATION_SCHEDULED":
                        orientation = conn.execute(
                            "SELECT scheduled_date FROM enrollment_orientation WHERE user_id = ?",
                            (user["user_id"],),
                        ).fetchone()
                        message = template.format(
                            name=user["name"],
                            orientation_date=orientation["scheduled_date"] if orientation else "TBD",
                        )
                    else:
                        message = template.format(name=user["name"])

                    self._log_activity(conn, user["user_id"], "REMINDER_SENT", f"stage={stage}, days_inactive={days_inactive}")

                    reminders_sent.append({
                        "user_id": user["user_id"],
                        "name": user["name"],
                        "stage": stage,
                        "days_inactive": days_inactive,
                        "message": message,
                    })

        return reminders_sent

    # --------------------------------------------------
    # Utility (mainly for testing / simulation)
    # --------------------------------------------------

    def _backdate_last_activity(self, user_id, days_ago):
        """
        TEST-ONLY helper: artificially ages a user's last_progress_at so
        reminder logic can be exercised without waiting real days.
        Backdates last_progress_at (not last_activity_at) since that is
        what check_and_send_reminders() actually evaluates — mirrors a
        user who has genuinely not advanced in the funnel, regardless of
        whether they've asked FAQs in the meantime.
        Not intended for use by a real website backend.
        """
        backdated = (datetime.now() - timedelta(days=days_ago)).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "UPDATE enrollment_users SET last_progress_at = ? WHERE user_id = ?",
                (backdated, user_id),
            )