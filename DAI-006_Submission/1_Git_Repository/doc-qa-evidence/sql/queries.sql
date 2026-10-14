-- Reference / audit queries. Run with: sqlite3 data/docqa.db < sql/queries.sql
-- (The tests execute every statement in this file to keep it valid.)

-- 1. Documents with chunk counts
SELECT d.filename, COUNT(c.chunk_id) AS chunks, d.char_count, d.ingested_at
FROM documents d LEFT JOIN chunks c ON c.doc_id = d.doc_id
GROUP BY d.doc_id ORDER BY d.filename;

-- 2. Rejected or failed files (most recent first)
SELECT filename, status, reason, logged_at
FROM ingestion_log WHERE status IN ('rejected','failed')
ORDER BY log_id DESC LIMIT 20;

-- 3. Ingestion outcome counts per run
SELECT run_id, status, COUNT(*) AS files
FROM ingestion_log GROUP BY run_id, status ORDER BY MIN(log_id);

-- 4. BM25 retrieval (lower bm25 = better match). :q is an FTS5 MATCH expression
SELECT d.filename, c.chunk_index, ROUND(bm25(chunks_fts), 3) AS bm25, c.text
FROM chunks_fts
JOIN chunks c    ON c.chunk_id = chunks_fts.chunk_id
JOIN documents d ON d.doc_id = c.doc_id
WHERE chunks_fts MATCH :q
ORDER BY bm25(chunks_fts) LIMIT 5;

-- 5. Questions that could not be answered (candidates for new documents)
SELECT question, top_score, note, asked_at
FROM query_log WHERE status = 'insufficient_evidence'
ORDER BY query_id DESC LIMIT 20;

-- 6. Answer rate by provider
SELECT provider, status, COUNT(*) AS n
FROM query_log GROUP BY provider, status;

-- 7. Integrity check: chunks without a matching FTS row (should return 0 rows)
SELECT c.chunk_id FROM chunks c
LEFT JOIN chunks_fts f ON f.chunk_id = c.chunk_id
WHERE f.chunk_id IS NULL;
