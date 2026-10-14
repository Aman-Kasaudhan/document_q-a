-- Document Q&A with Evidence: data model (SQLite)
-- All statements are idempotent (IF NOT EXISTS) so init can run on every start.

-- One row per successfully ingested file.
CREATE TABLE IF NOT EXISTS documents (
    doc_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT    NOT NULL UNIQUE,          -- natural key: one active version per file
    content_hash  TEXT    NOT NULL UNIQUE,          -- sha256 of normalised text; blocks duplicate content
    char_count    INTEGER NOT NULL CHECK (char_count > 0),
    status        TEXT    NOT NULL DEFAULT 'active',
    ingested_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Chunks of a document, with character offsets into the normalised text.
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id       INTEGER NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    text         TEXT    NOT NULL,
    char_start   INTEGER NOT NULL,
    char_end     INTEGER NOT NULL,
    chunk_hash   TEXT    NOT NULL,
    UNIQUE (doc_id, chunk_index),
    CHECK (char_end > char_start)
);
CREATE INDEX IF NOT EXISTS idx_chunks_hash ON chunks(chunk_hash);

-- Full-text index (BM25 ranking). chunk_id links back to chunks; it is not indexed.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    chunk_id UNINDEXED,
    tokenize = 'porter unicode61'
);

-- Event log: every file seen in every ingestion run, with outcome and reason.
CREATE TABLE IF NOT EXISTS ingestion_log (
    log_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id     TEXT NOT NULL,
    filename   TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('ingested','updated','skipped_unchanged','rejected','failed')),
    reason     TEXT,
    logged_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Audit trail of questions and how they were answered.
CREATE TABLE IF NOT EXISTS query_log (
    query_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    question   TEXT NOT NULL,
    status     TEXT NOT NULL CHECK (status IN ('answered','insufficient_evidence')),
    answer     TEXT,
    top_score  REAL,
    chunk_ids  TEXT,          -- comma separated chunk_ids that were retrieved
    provider   TEXT,
    note       TEXT,
    asked_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
