# Architecture

![Architecture diagram](architecture.png)

_Regenerate the image with `python docs/make_architecture.py` (needs `pip install matplotlib`). The Mermaid source below renders on GitHub and is kept as an editable text version._


```mermaid
flowchart LR
    A[Raw files<br/>data/raw] --> B[Validate<br/>extension, empty, UTF-8]
    B -->|rejected| L[(ingestion_log)]
    B --> C[Normalise + SHA-256]
    C -->|same hash| S[skip unchanged]
    C -->|new / changed| D[Chunk<br/>paragraphs + overlap]
    D --> E[(SQLite<br/>documents, chunks, chunks_fts)]
    Q[Question] --> R[Retrieve<br/>FTS5 BM25, top 10]
    E --> R
    R --> K[Rank by keyword coverage<br/>= evidence score]
    K --> G{score >= MIN_SCORE<br/>and no unknown entity?}
    G -->|no| N[insufficient_evidence]
    G -->|yes| P[AnswerProvider]
    P -->|extractive default| X[Best sentence + source chunk]
    P -->|ollama optional| X
    P -->|error / malformed| F[fallback: extractive]
    F --> X
    X --> O[Answer + source chunk]
    N --> LOG[(query_log)]
    O --> LOG
```

## Layers

| Layer | Module | Responsibility |
|---|---|---|
| Source | `data/raw/` | Synthetic documents (+ 3 deliberately invalid files) |
| Validation | `ingest.read_and_validate` | Extension, encoding, empty-file checks |
| Raw -> curated | `ingest`, `chunking` | Normalise, hash, chunk, transactional load |
| Store | `sql/schema.sql` | documents, chunks, FTS5 index, ingestion_log, query_log |
| Retrieval | `retrieval` | BM25 candidates, keyword-coverage evidence score, unknown-entity check |
| AI seam | `providers/` | `AnswerProvider` interface; extractive and Ollama implementations |
| Orchestration | `qa` | Evidence gate, provider call, fallback, audit logging |
| Interface | `cli` | ingest / ask / eval / stats |

## Data model

```
documents (doc_id PK, filename UNIQUE, content_hash UNIQUE, char_count, status, ingested_at)
    1 --- n
chunks    (chunk_id PK, doc_id FK, chunk_index, text, char_start, char_end, chunk_hash,
           UNIQUE(doc_id, chunk_index))
chunks_fts (FTS5: text, chunk_id UNINDEXED)      -- one row per chunk
ingestion_log (log_id, run_id, filename, status, reason, logged_at)   -- event log
query_log     (query_id, question, status, answer, top_score, chunk_ids, provider, note, asked_at)
```
