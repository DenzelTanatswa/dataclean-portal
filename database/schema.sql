-- DataClean Portal — Reference Schema
-- Tables are created automatically by the application.
-- This file is for reference / manual DBA use only.

CREATE TABLE IF NOT EXISTS datasets (
    dataset_id        SERIAL PRIMARY KEY,
    dataset_name      VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255),
    file_type         VARCHAR(10),
    row_count         INTEGER,
    column_count      INTEGER,
    uploaded_at       TIMESTAMP DEFAULT NOW(),
    quality_score     FLOAT,
    status            VARCHAR(50) DEFAULT 'uploaded'
);

CREATE TABLE IF NOT EXISTS cleaning_runs (
    run_id                SERIAL PRIMARY KEY,
    run_code              VARCHAR(30) UNIQUE,
    dataset_id            INTEGER REFERENCES datasets(dataset_id),
    run_timestamp         TIMESTAMP DEFAULT NOW(),
    original_rows         INTEGER,
    cleaned_rows          INTEGER,
    rows_removed          INTEGER,
    quality_score_before  FLOAT,
    quality_score_after   FLOAT,
    version               INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS cleaning_audit (
    audit_id   SERIAL PRIMARY KEY,
    run_id     INTEGER REFERENCES cleaning_runs(run_id),
    operation  VARCHAR(255),
    changes    INTEGER,
    timestamp  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quality_checks (
    check_id        SERIAL PRIMARY KEY,
    dataset_id      INTEGER REFERENCES datasets(dataset_id),
    run_id          INTEGER REFERENCES cleaning_runs(run_id),
    column_name     VARCHAR(255),
    check_type      VARCHAR(100),
    issue_count     INTEGER,
    records_checked INTEGER,
    status          VARCHAR(20),
    timestamp       TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dataset_versions (
    version_id     SERIAL PRIMARY KEY,
    dataset_id     INTEGER REFERENCES datasets(dataset_id),
    run_id         INTEGER REFERENCES cleaning_runs(run_id),
    version_number INTEGER,
    description    TEXT,
    row_count      INTEGER,
    quality_score  FLOAT,
    created_at     TIMESTAMP DEFAULT NOW()
);
