-- propublica-grader facts schema
-- One row per (EIN, fiscal_year) 990 filing. Additional normalized tables for
-- officers, events, and governance. Sourced from IRS e-file XML via the
-- ProPublica Nonprofit Explorer API. All field names map to specific 990 line
-- items or Schedule cells; see docs/schema.md for the complete mapping.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- filings: one row per filed 990 per organization per fiscal year
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS filings (
  ein                       TEXT NOT NULL,
  fiscal_year               INTEGER NOT NULL,
  org_name                  TEXT,
  state                     TEXT,
  city                      TEXT,
  ntee_code                 TEXT,
  ruling_year               TEXT,
  revoked                   INTEGER,

  -- Part I summary
  mission_text              TEXT,          -- Part I Line 1
  voting_members            INTEGER,       -- Part I Line 3 / Part VI Line 1a
  independent_members       INTEGER,       -- Part VI Line 1b
  employees                 INTEGER,       -- Part I Line 5
  volunteers                INTEGER,       -- Part I Line 6
  total_revenue             INTEGER,       -- Part I Line 12
  total_expenses            INTEGER,       -- Part I Line 18
  net_assets_eoy            INTEGER,       -- Part I Line 22
  total_assets              INTEGER,       -- Part X Line 16

  -- Part VIII revenue breakdown
  contributions             INTEGER,       -- Part VIII Line 1h
  program_service_revenue   INTEGER,       -- Part VIII Line 2g
  investment_income         INTEGER,       -- Part VIII Line 3+4+7d
  fundraising_events_1c     INTEGER,       -- Part VIII Line 1c
  government_grants_1e      INTEGER,       -- Part VIII Line 1e

  -- Part IX functional expenses
  officer_comp_part_ix      INTEGER,       -- Part IX Line 5 (aggregate)
  other_salaries_wages      INTEGER,       -- Part IX Line 7
  pension_benefits          INTEGER,       -- Part IX Line 8+9+10
  professional_fundraising  INTEGER,       -- Part IX Line 11e
  fundraising_expenses_d25  INTEGER,       -- Part IX column D Line 25

  -- Part VI governance (0=No, 1=Yes, NULL=unknown)
  coi_policy                INTEGER,       -- Part VI Line 12a
  whistleblower_policy      INTEGER,       -- Part VI Line 13
  doc_retention_policy      INTEGER,       -- Part VI Line 14
  ed_comp_review            INTEGER,       -- Part VI Line 15a
  form_990_board_review     INTEGER,       -- Part VI Line 11a

  -- Part VII Section A attestation
  no_officer_comp_box       INTEGER,       -- "Neither org nor related org compensated any current officer" checkbox

  -- Schedule O narrative (normalized uppercase, whitespace-collapsed)
  schedule_o_review_narr    TEXT,
  schedule_o_public_narr    TEXT,

  -- Meta
  preparer_firm             TEXT,
  preparer_ptin             TEXT,
  signer_name               TEXT,
  signer_title              TEXT,
  filing_signed_date        TEXT,
  object_id                 TEXT,          -- IRS DLN

  -- Flags set by fetcher
  schedule_g_filed          INTEGER,       -- 1 if Schedule G Part II rows exist

  PRIMARY KEY (ein, fiscal_year)
);

CREATE INDEX IF NOT EXISTS idx_filings_ntee ON filings(ntee_code);
CREATE INDEX IF NOT EXISTS idx_filings_state ON filings(state);

-- ---------------------------------------------------------------------------
-- officers: Part VII Section A — one row per person per fiscal year
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS officers (
  ein                        TEXT NOT NULL,
  fiscal_year                INTEGER NOT NULL,
  name                       TEXT NOT NULL,
  title                      TEXT,
  hours_per_week             REAL,
  reportable_comp_org        INTEGER,
  reportable_comp_related    INTEGER,
  other_comp                 INTEGER,
  position_officer           INTEGER,       -- 0/1 flag from Part VII column (C)
  position_director          INTEGER,
  position_key_employee      INTEGER,
  position_highest_comp      INTEGER,
  position_former            INTEGER,
  PRIMARY KEY (ein, fiscal_year, name),
  FOREIGN KEY (ein, fiscal_year) REFERENCES filings(ein, fiscal_year)
);

-- ---------------------------------------------------------------------------
-- events: Schedule G Part II — one row per fundraising event per year
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
  ein                  TEXT NOT NULL,
  fiscal_year          INTEGER NOT NULL,
  event_name           TEXT NOT NULL,
  gross_receipts       INTEGER,
  contributions        INTEGER,
  gross_income         INTEGER,
  cash_prizes          INTEGER,
  noncash_prizes       INTEGER,
  rent_facility        INTEGER,
  food_beverages       INTEGER,
  entertainment        INTEGER,
  other_direct         INTEGER,
  net_income           INTEGER,
  PRIMARY KEY (ein, fiscal_year, event_name),
  FOREIGN KEY (ein, fiscal_year) REFERENCES filings(ein, fiscal_year)
);

-- ---------------------------------------------------------------------------
-- contractors: Part VII Section B — independent contractors >$100K
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS contractors (
  ein              TEXT NOT NULL,
  fiscal_year      INTEGER NOT NULL,
  name             TEXT NOT NULL,
  address          TEXT,
  services         TEXT,
  compensation     INTEGER,
  PRIMARY KEY (ein, fiscal_year, name),
  FOREIGN KEY (ein, fiscal_year) REFERENCES filings(ein, fiscal_year)
);

-- ---------------------------------------------------------------------------
-- scores: one row per (EIN, detector, run_date) — populated by scorer
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scores (
  ein              TEXT NOT NULL,
  detector_id      TEXT NOT NULL,  -- e.g., 'rule_01_zero_ed_comp'
  score            REAL NOT NULL,  -- 0-100 scaled
  years_evaluated  INTEGER,
  run_date         TEXT NOT NULL,
  detail_json      TEXT,           -- detector-specific supporting detail
  PRIMARY KEY (ein, detector_id, run_date)
);

CREATE INDEX IF NOT EXISTS idx_scores_detector ON scores(detector_id);

-- ---------------------------------------------------------------------------
-- composite: one row per EIN per run — the headline score
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS composite (
  ein              TEXT NOT NULL,
  composite_score  REAL NOT NULL,  -- 0-100
  run_date         TEXT NOT NULL,
  n_detectors_fired INTEGER,       -- how many of the 8 rules triggered
  PRIMARY KEY (ein, run_date)
);
