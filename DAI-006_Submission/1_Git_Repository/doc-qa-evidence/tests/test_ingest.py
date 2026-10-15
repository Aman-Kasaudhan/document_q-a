from src.ingest import ingest_directory


def counts(conn):
    return tuple(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                 for t in ("documents", "chunks", "chunks_fts"))


def ingest(conn, directory, settings):
    return ingest_directory(conn, directory, settings.chunk_size, settings.chunk_overlap)


def test_ingestion_is_idempotent(conn, docs_dir, settings):
    first = ingest(conn, docs_dir, settings)
    before = counts(conn)
    second = ingest(conn, docs_dir, settings)
    assert first.ingested == 5 and second.ingested==0
    assert second.skipped_unchanged == 5
    assert counts(conn) == before                      # no duplicate rows after a re-run
    assert before[1] == before[2] > 0                  # every chunk is indexed exactly once


def test_invalid_files_are_rejected_and_logged(conn, docs_dir, settings):
    summary=ingest(conn, docs_dir, settings)
    assert summary.rejected == 3
    reasons = {r["filename"]: r["reason"] for r in conn.execute(
        "SELECT filename, reason FROM ingestion_log WHERE status = 'rejected'")}
    assert reasons["empty_notes.txt"] == "empty_file"
    assert reasons["budget_export.xyz"].startswith("unsupported_extension")
    assert reasons["corrupt_encoding.txt"].startswith("invalid_encoding")
    assert conn.execute("SELECT COUNT(*) FROM documents WHERE filename IN "
                        "('empty_notes.txt','budget_export.xyz','corrupt_encoding.txt')").fetchone()[0] == 0


def test_changed_file_replaces_old_chunks(conn, docs_dir, settings):
    ingest(conn, docs_dir, settings)
    (docs_dir / "expense_policy.md").write_text(
        "# Expenses\nThe daily meal allowance is 75 USD during business travel.\n", encoding="utf-8")
    summary = ingest(conn, docs_dir, settings)
    assert summary.updated == 1
    texts = " ".join(r["text"] for r in conn.execute(
        "SELECT c.text FROM chunks c JOIN documents d USING(doc_id) WHERE d.filename='expense_policy.md'"))
    assert "75 USD" in texts and "60 USD" not in texts
    stale = conn.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH '\"hotel\"'").fetchone()[0]
    assert stale == 0                                   


def test_duplicate_content_under_another_name_is_rejected(conn, docs_dir, settings):
    ingest(conn, docs_dir, settings)
    (docs_dir / "copy_of_leave.md").write_text(
        (docs_dir / "leave_policy.md").read_text(encoding="utf-8"), encoding="utf-8")
    summary = ingest(conn, docs_dir, settings)
    assert summary.rejected == 4                       # 3 bad files + the duplicate
    row =conn.execute("SELECT reason FROM ingestion_log WHERE filename='copy_of_leave.md'").fetchone()
    assert row["reason"]=="duplicate_content_of:leave_policy.md"


def test_missing_directory_raises_clear_error(conn, tmp_path, settings):
    import pytest
    with pytest.raises(FileNotFoundError):
        ingest(conn, tmp_path / "does_not_exist", settings)
