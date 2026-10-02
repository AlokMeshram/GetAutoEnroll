-- ============================================================
-- IAC GPI Project: Regional Youth Outreach Database Schema
-- ============================================================

-- Master table: one row per state, holds core identity + geography
CREATE TABLE states (
    state_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    state_name              TEXT UNIQUE NOT NULL,
    area_sq_km              INTEGER,
    total_population        INTEGER,
    decadal_growth_rate     REAL,
    rural_population        INTEGER,
    rural_pct               REAL,
    urban_population        INTEGER,
    urban_pct               REAL,
    pop_density_per_sq_km   REAL,
    sex_ratio               INTEGER
);

-- Economic indicators, one row per state
CREATE TABLE economic_indicators (
    econ_id                             INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id                            INTEGER NOT NULL,
    literacy_rate_pct                   REAL,
    gsdp_current_cr_2022_23             REAL,
    gsdp_growth_current_pct_2022_23     REAL,
    unemp_rate_2023_24                  REAL,
    FOREIGN KEY (state_id) REFERENCES states(state_id)
);

-- Youth demographic breakdown, one row per state
CREATE TABLE youth_demographics (
    youth_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id                INTEGER NOT NULL,
    youth_15_29_total       INTEGER,
    youth_15_29_male        INTEGER,
    youth_15_29_female      INTEGER,
    youth_15_29_rural       INTEGER,
    youth_15_29_urban       INTEGER,
    youth_pct_of_population REAL,
    FOREIGN KEY (state_id) REFERENCES states(state_id)
);

-- Skill training (PMKVY) data, one row per state
CREATE TABLE skill_training (
    skill_id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id                    INTEGER NOT NULL,
    pmkvy_trained_2023_24       INTEGER,
    pmkvy_rate_per_lakh_youth   REAL,
    FOREIGN KEY (state_id) REFERENCES states(state_id)
);

-- Cluster assignment + persona label, one row per state
CREATE TABLE clusters (
    cluster_row_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    state_id            INTEGER NOT NULL UNIQUE,
    cluster_label        INTEGER,
    cluster_persona      TEXT,
    FOREIGN KEY (state_id) REFERENCES states(state_id)
);
