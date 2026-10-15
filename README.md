# Document Q&A with Evidence (DAI-006)

A small document ingestion pipeline and retrieval-based Q&A application in **Python + SQL (SQLite FTS5)**.
Every answer shows the **source chunk** it came from. When the documents do not support an
answer, the system returns **"Insufficient evidence"** instead of guessing.

- Demo video: `<ADD LINK>`
- Design note (1 page): [docs/design_note.pdf](design_note.pdf) · [docs/design_note.md](design_note.md) · Architecture: [docs/architecture.md](DAI-006_Submission/1_Git_Repository/doc-qa-evidence/architecture.md)
- Test evidence: [docs/test_results.txt](docs/test_results.txt) · Eval results: [docs/eval_results.txt](docs/eval_results.txt)

## 1. Problem statement

Given a folder of documents, ingest, clean and store them in a SQL database, then answer
questions using only that content. Requirements: show the supporting chunk; return
`insufficient_evidence` when unsupported; synthetic/public data only; AI behind a clear
interface; runs from a clean setup; no secrets in code; at least 3 tests and one edge-case demo.

## 2. Approach

1. **Ingest** - validate (extension, UTF-8, non-empty), normalise, SHA-256 hash, chunk (paragraph-aware, ~500 chars, 50 overlap), load in one transaction per file.
2. **Retrieve** - SQLite FTS5 (BM25) returns candidates; each is scored by *keyword coverage* (share of the question's keywords found in the chunk).
3. **Evidence gate** - refuse if best coverage `< MIN_SCORE` (0.60) or if the question names an entity (e.g. "Enterprise") that appears in no document.
4. **Answer** - an `AnswerProvider` produces the answer from the retrieved chunks only. Default is extractive (best sentence); a local LLM via Ollama is optional.
5. **Audit** - every question, outcome, score and retrieved chunk ids go to `query_log`.

## 3. Architecture / data flow

![Architecture diagram](docs/architecture.png)

## 4. Technologies

| Area | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | Standard library does most of the work |
| Database | SQLite + FTS5 | Real SQL and BM25 search with zero setup |
| AI (default) | Extractive provider | Deterministic, no download, easy to test |
| AI (optional) | Ollama local LLM | Free, no API key; called through `requests` |
| Config | python-dotenv | `.env` file, nothing hard-coded |
| Tests | pytest | 46 tests |

## 5. Project structure

```
doc-qa-evidence/
├── README.md  requirements.txt  pytest.ini  .gitignore  .env.example
├── data/
│   ├── raw/                  # 5 synthetic policy/FAQ docs + 3 deliberately invalid files
│   └── eval_questions.json   # 10 answerable + 5 unanswerable questions
├── sql/
│   ├── schema.sql            # tables, constraints, FTS5 index
│   └── queries.sql           # audit / reference queries (validated by a test)
├── src/
│   ├── config.py db.py models.py textutil.py
│   ├── ingest.py chunking.py retrieval.py qa.py cli.py
│   └── providers/            # base.py (interface), extractive.py, ollama.py
├── tests/                    # conftest + chunking, ingest, qa tests
├── docs/                     # architecture, design note (md + pdf), test + eval results
└── .github/workflows/ci.yml  # runs tests + eval on every push
```

## 6. Setup (clean machine)

```bash
git clone <your-repo-url>
cd doc-qa-evidence
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env   (defaults work as-is)
```

Optional local LLM: install [Ollama](https://ollama.com), `ollama pull llama3.2`, set `ANSWER_PROVIDER=ollama` in `.env`
(or pass `--provider ollama`). If Ollama is not running, the app logs the failure and falls back to the extractive provider.

## 7. How to run

```bash
python -m src.cli ingest                 # load data/raw (safe to re-run)
python -m src.cli stats                  # documents, chunk counts, rejected files
python -m src.cli ask "How much does the Pro plan cost per month?"
python -m src.cli ask "What is the CEO's salary?"
python -m src.cli ask "..." --json       # machine-readable output
python -m src.cli eval                   # run all 15 eval questions
pytest -v                                # run the tests
```

## 8. Data model

See [sql/schema.sql](sql/schema.sql).

| Table | Purpose |
|---|---|
| `documents` | One row per ingested file. `filename` UNIQUE, `content_hash` UNIQUE (blocks duplicate content) |
| `chunks` | Text, index, character offsets, hash; FK to `documents` with `ON DELETE CASCADE`; `UNIQUE(doc_id, chunk_index)` |
| `chunks_fts` | FTS5 index (porter stemming) used for BM25 retrieval |
| `ingestion_log` | Event log of every file in every run: ingested / updated / skipped_unchanged / rejected / failed + reason |
| `query_log` | Question, status, answer, evidence score, retrieved chunk ids, provider, note |

## 9. AI approach

- **Interface:** `AnswerProvider.answer(question, chunks) -> ProviderResult`. All model access is behind it; retrieval and the evidence gate never call a model. `providers.get_provider()` is the only place that picks an implementation.
- **Input to the model:** the question and the top-3 retrieved chunks, numbered `[1]..[3]`, with an instruction to use only that context.
- **Expected output:** a short answer ending in the passage number used, e.g. `[2]`, or the token `INSUFFICIENT_EVIDENCE`. The cited passage becomes the displayed source chunk.
- **Stored/used:** answer, provider name, score and chunk ids are written to `query_log`.
- **Bad responses:** timeout, connection error, HTTP error, invalid JSON, empty text, or an answer with no valid citation raise `ProviderError`; the service falls back to the extractive provider and records `provider_failed_fallback_used:<reason>`. An explicit model refusal becomes `insufficient_evidence`.
- **Low confidence:** questions whose evidence score is below `MIN_SCORE` never reach the provider.

**Threshold tuning:** on the eval set every answerable question scored 0.67-1.00 and every unanswerable one 0.00-0.33
(except the near-miss "Enterprise" question, 0.75, caught by the unknown-entity check), so `MIN_SCORE=0.60` sits in the gap.

## 10. Assumptions

- Documents are UTF-8 `.txt` / `.md` files in English; all data is synthetic (fictional company "Nimbus Works").
- A file name identifies a document: an edited file replaces its old chunks; identical content under a new name is rejected.
- Capitalised words in a question (after the first word) are treated as names that must exist in the documents.

## 11. Tests performed (46, all passing)

Full output: [docs/test_results.txt](docs/test_results.txt).

| Area | What is checked |
|---|---|
| Ingestion | **idempotent re-run** (row counts unchanged); changed file replaces chunks and FTS rows; **empty, `.xyz` and non-UTF-8 files rejected and logged**; duplicate content rejected; missing directory error |
| Chunking | offsets match the text; full coverage; long paragraphs split; overlap; invalid parameters |
| Q&A | all 15 eval questions (right source + expected fact, or refusal); **near-miss entity refused**; empty question; stop-word-only question; empty database; audit log |
| AI provider | **provider failure -> fallback**; model refusal respected; Ollama: valid answer, empty output, no citation, bad citation, bad JSON, HTTP 500, timeout, refusal token; end-to-end with broken Ollama |
| SQL | every statement in `sql/queries.sql` runs; integrity query returns no orphan chunks |

## 12. Sample output

```
$ python -m src.cli ingest
  rejected           budget_export.xyz  (unsupported_extension:.xyz)
  rejected           corrupt_encoding.txt  (invalid_encoding:not_utf8)
  rejected           empty_notes.txt  (empty_file)
  ingested           expense_policy.md  (2 chunks)
  ...
Summary: ingested=5 updated=0 unchanged=0 rejected=3 failed=0
$ python -m src.cli ingest        # second run
Summary: ingested=0 updated=0 unchanged=5 rejected=3 failed=0

$ python -m src.cli ask "How long must passwords be?"
Status: ANSWERED  (evidence score 1.00, provider: extractive)
Answer: Passwords must be at least 14 characters long and changed every 90 days.
Source: it_security_policy.md, chunk 0 (chars 0-434)
  | ## Passwords
  | Passwords must be at least 14 characters long and changed every 90 days. ...

$ python -m src.cli ask "What is the CEO's salary?"
Status: INSUFFICIENT EVIDENCE  (best evidence score 0.00, threshold 0.60)
Answer: Insufficient evidence: the documents do not contain enough information to answer this question.
Reason: no_matching_chunks

$ python -m src.cli ask "How much does the Enterprise plan cost per month?"
Status: INSUFFICIENT EVIDENCE  (best evidence score 0.75, threshold 0.60)
Reason: unknown_entity_not_in_documents:enterprise

$ python -m src.cli eval
...
Accuracy: 15/15 = 100%  (MIN_SCORE=0.6)
```

## 13. Known limitations

- Keyword retrieval does not understand synonyms ("pay" vs "salary"); a paraphrased question may be refused.
- The extractive provider returns one sentence and cannot combine facts from several chunks.
- The unknown-entity check is a heuristic based on capitalisation.
- Deleting a source file does not remove it from the database.
- `MIN_SCORE` is tuned on 15 synthetic questions; real data needs re-tuning.
- The eval set was written alongside the documents, so 100% accuracy shows correctness on this set, not general quality.

## 14. What I would improve for production

- Hybrid retrieval (BM25 + embeddings) with a cross-encoder reranker.
- PostgreSQL with `pgvector`, or a dedicated vector store, for larger volumes; batch/streaming ingestion with change detection and removal of deleted files.
- Support for PDF/DOCX, document versioning, and per-chunk metadata (section titles, page numbers).
- Calibrated confidence, sentence-level citations, an LLM-as-judge groundedness check, and dashboards over `query_log`.
- Authentication, rate limiting, and an API (FastAPI) instead of a CLI only.
