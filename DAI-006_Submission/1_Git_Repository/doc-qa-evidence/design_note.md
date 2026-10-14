# Design and Decision Note

**Goal.** Answer questions from a small document set, always show the supporting chunk, and
say "insufficient evidence" when the documents do not support an answer.

**1. SQLite + FTS5 instead of a vector database.** The corpus is small, the brief asks for
SQL, and a reviewer must run it from a clean setup. SQLite is in the Python standard library
and FTS5 gives BM25 ranking with no download. Trade-off: keyword search misses synonyms
("salary" vs "pay"). Alternatives considered: sentence-transformer embeddings with a vector
store, or hybrid BM25 + embeddings with a reranker. I would add those first for a real system.

**2. The evidence score is keyword coverage, not raw BM25.** BM25 is relative: it always
ranks *something* first, even for an unrelated question, so a threshold on it is unstable.
Coverage (share of the question's keywords found in the chunk) is bounded 0..1 and easy to
explain. Threshold `MIN_SCORE = 0.60` was chosen from the eval set: every answerable
question scored 0.67-1.00 and unanswerable questions scored 0.00-0.33, so 0.60 sits in the gap.
It is tuned on 15 questions and would need re-tuning on real data.

**3. Unknown-entity guard.** Coverage alone answered "How much is the *Enterprise* plan?"
with the Pro plan's price (score 0.75). Capitalised terms that appear in no document now force
a refusal. Trade-off: a heuristic, and it can refuse a valid question that names something
only by a synonym.

**4. AI isolated behind `AnswerProvider`.** Retrieval and the evidence gate never touch a
model. The default `ExtractiveProvider` returns the best-matching sentence, so the system is
deterministic and testable. `OllamaProvider` (local LLM) is optional. It must cite a passage
as `[n]`; no citation, empty output, bad JSON, HTTP error or timeout raises `ProviderError`
and the service falls back to the extractive provider and logs why. If the model itself says
`INSUFFICIENT_EVIDENCE`, that is respected.

**5. Idempotent, transactional ingestion.** Files are keyed by name and content hash:
unchanged files are skipped, changed files replace their chunks and FTS rows in one
transaction, byte-identical content under another name is rejected, and invalid files are
logged instead of crashing the run.

**Known limitations.** Plain text/Markdown only; English; no synonym matching; sentence-level
extractive answers cannot combine facts from several chunks; deleted source files are not
removed from the database; thresholds tuned on synthetic data.
