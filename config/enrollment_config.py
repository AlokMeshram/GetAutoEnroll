"""
Configuration for Agent 4 (Enrollment Agent).

Kept separate from agent logic so the FAQ list, document checklist, and
reminder timing can be edited without touching the agent's code — same
separation-of-concerns principle used for CLUSTER_CONFIG and the prompt files.
"""

# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

DB_PATH = "iac_gpi_project.db"   # same database Agent 1's data lives in


# --------------------------------------------------------------------------
# Funnel stages
# --------------------------------------------------------------------------
# A user always sits in exactly one of these stages. Order matters — it
# defines the expected forward progression used by the reminder logic.

FUNNEL_STAGES = [
    "REGISTERED",
    "DOCUMENTS_UPLOADED",
    "ORIENTATION_SCHEDULED",
    "ORIENTATION_COMPLETED",
    "ENROLLED",
]

DROPPED_STATUS = "DROPPED"  # set separately from stage if a user goes fully inactive


# --------------------------------------------------------------------------
# Required documents (placeholder checklist — update with IAC's actual
# document requirements when available)
# --------------------------------------------------------------------------

REQUIRED_DOCUMENTS = [
    "ID Proof",
    "Address Proof",
    "Educational Certificate",
    "Passport Photo",
]


# --------------------------------------------------------------------------
# Reminder rules — how many days of inactivity at each stage before a
# reminder should fire. Tune these once real usage data exists.
# --------------------------------------------------------------------------

REMINDER_THRESHOLD_DAYS = {
    "REGISTERED": 2,               # registered but no documents uploaded in 2 days
    "DOCUMENTS_UPLOADED": 3,       # documents uploaded but no orientation booked in 3 days
    "ORIENTATION_SCHEDULED": 1,    # orientation booked, remind 1 day before/after as a nudge
}

REMINDER_MESSAGE_TEMPLATES = {
    "REGISTERED": (
        "Hi {name}, thanks for registering with IAC! You're almost there — "
        "please upload your documents ({doc_list}) to continue your enrollment."
    ),
    "DOCUMENTS_UPLOADED": (
        "Hi {name}, your documents are received! Please schedule your orientation "
        "session now to complete your enrollment with IAC."
    ),
    "ORIENTATION_SCHEDULED": (
        "Hi {name}, this is a reminder about your upcoming IAC orientation session "
        "on {orientation_date}. We look forward to seeing you!"
    ),
}


# --------------------------------------------------------------------------
# FAQ knowledge base — rule-based keyword matching, no LLM required.
# Each entry: keywords (lowercase, used for matching) + the answer to return.
# --------------------------------------------------------------------------

FAQ_KNOWLEDGE_BASE = [
    {
        "id": "docs_required",
        "keywords": ["document", "documents", "upload", "id proof", "certificate", "photo"],
        "question": "What documents do I need to upload?",
        "answer": (
            "You need to upload: " + ", ".join(REQUIRED_DOCUMENTS) + ". "
            "You can upload them one at a time — we'll track your progress."
        ),
    },
    {
        "id": "how_to_register",
        "keywords": ["register", "registration", "sign up", "signup", "join", "apply"],
        "question": "How do I register for IAC programs?",
        "answer": (
            "You can register by sharing your name, state, and a contact number/email. "
            "Once registered, you'll be guided through document upload and orientation scheduling."
        ),
    },
    {
        "id": "orientation_info",
        "keywords": ["orientation", "schedule", "session", "meeting", "when", "date"],
        "question": "What is orientation and when does it happen?",
        "answer": (
            "Orientation is a short introductory session explaining the program, expectations, "
            "and next steps. You can schedule it any time after your documents are uploaded."
        ),
    },
    {
        "id": "enrollment_status",
        "keywords": ["status", "progress", "where am i", "track", "stage"],
        "question": "How do I check my enrollment status?",
        "answer": (
            "You can check your current enrollment stage anytime — just ask "
            "'what is my status' and we'll tell you exactly where you are."
        ),
    },
    {
        "id": "fees_cost",
        "keywords": ["fee", "fees", "cost", "price", "free", "payment"],
        "question": "Is there a fee to join IAC programs?",
        "answer": (
            "IAC's core skilling and outreach programs are designed to be accessible. "
            "For program-specific fee details, a community champion will confirm this with you directly."
        ),
    },
    {
        "id": "contact_help",
        "keywords": ["help", "contact", "champion", "support", "talk to someone", "human"],
        "question": "How can I talk to a real person / community champion?",
        "answer": (
            "A local Community Champion can assist you in person or over a call. "
            "Let us know your village/area and we'll connect you with your nearest champion."
        ),
    },
]

FAQ_FALLBACK_ANSWER = (
    "I don't have a direct answer for that yet — let me connect you with a local "
    "Community Champion who can help further."
)

FAQ_MATCH_MIN_SCORE = 1  # minimum keyword overlap count to consider a match valid