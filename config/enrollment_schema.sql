-- ============================================================
-- Agent 4: Enrollment Agent — additional tables
-- These are ADDED to the existing iac_gpi_project.db.
-- They do NOT modify states / economic_indicators / youth_demographics /
-- skill_training / clusters, which already exist from Agent 1's setup.
-- ============================================================

CREATE TABLE IF NOT EXISTS enrollment_users (
    user_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    state_name          TEXT NOT NULL,
    contact             TEXT,
    current_stage       TEXT NOT NULL DEFAULT 'REGISTERED',
    status              TEXT NOT NULL DEFAULT 'ACTIVE',   -- ACTIVE or DROPPED
    registered_at       TEXT NOT NULL,
    last_activity_at    TEXT NOT NULL,   -- any interaction (FAQ, etc.) — general "last seen"
    last_progress_at    TEXT NOT NULL    -- only stage-advancing actions — used for reminder checks
);

CREATE TABLE IF NOT EXISTS enrollment_documents (
    doc_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    document_type       TEXT NOT NULL,
    uploaded_at         TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES enrollment_users(user_id)
);

CREATE TABLE IF NOT EXISTS enrollment_orientation (
    orientation_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL UNIQUE,
    scheduled_date      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'SCHEDULED',  -- SCHEDULED or COMPLETED
    FOREIGN KEY (user_id) REFERENCES enrollment_users(user_id)
);

CREATE TABLE IF NOT EXISTS enrollment_activity_log (
    log_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL,
    action              TEXT NOT NULL,
    details             TEXT,
    timestamp           TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES enrollment_users(user_id)
);