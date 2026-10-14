"""Command line interface.

  python -m src.cli ingest [--dir PATH]
  python -m src.cli ask "question" [--provider extractive|ollama] [--json]
  python -m src.cli eval [--file PATH]
  python -m src.cli stats
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from .config import PROJECT_ROOT, Settings
from .db import connect, init_db
from .ingest import ingest_directory
from .models import Answer
from .qa import INSUFFICIENT_MESSAGE, QAService

EVAL_FILE = PROJECT_ROOT / "data" / "eval_questions.json"


def print_answer(ans: Answer, min_score: float) -> None:
    print(f"\nQ: {ans.question}")
    if ans.status == "answered":
        src = ans.primary_source
        print(f"Status: ANSWERED  (evidence score {ans.top_score:.2f}, provider: {ans.provider})")
        print(f"Answer: {ans.answer}")
        if src:
            print(f"Source: {src.filename}, chunk {src.chunk_index} (chars {src.char_start}-{src.char_end})")
            print("  | " + src.text.replace("\n", "\n  | "))
        others = [c for c in ans.sources if not src or c.chunk_id != src.chunk_id]
        if others:
            print("Also retrieved: " + ", ".join(f"{c.filename}#{c.chunk_index} ({c.coverage:.2f})" for c in others))
    else:
        print(f"Status: INSUFFICIENT EVIDENCE  (best evidence score {ans.top_score:.2f}, threshold {min_score:.2f})")
        print(f"Answer: {INSUFFICIENT_MESSAGE}")
        print(f"Reason: {ans.note}")
    if ans.status == "answered" and ans.note:
        print(f"Note: {ans.note}")


def cmd_ingest(args, settings: Settings, conn) -> int:
    directory = Path(args.dir) if args.dir else settings.raw_data_dir
    summary = ingest_directory(conn, directory, settings.chunk_size, settings.chunk_overlap)
    print(f"Ingestion run {summary.run_id} on {directory}")
    for name, status, reason in summary.details:
        print(f"  {status:<18} {name}" + (f"  ({reason})" if reason else ""))
    print(f"Summary: ingested={summary.ingested} updated={summary.updated} "
          f"unchanged={summary.skipped_unchanged} rejected={summary.rejected} failed={summary.failed}")
    return 0


def cmd_ask(args, settings: Settings, conn) -> int:
    if args.provider:
        settings = dataclasses.replace(settings, answer_provider=args.provider)
    ans = QAService(conn, settings).ask(args.question)
    if args.json:
        print(json.dumps(ans.to_dict(), indent=2))
    else:
        print_answer(ans, settings.min_score)
    return 0


def cmd_eval(args, settings: Settings, conn) -> int:
    docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    if docs == 0:
        print("No documents in the database. Run: python -m src.cli ingest")
        return 2
    items = json.loads(Path(args.file or EVAL_FILE).read_text(encoding="utf-8"))
    qa = QAService(conn, settings)
    passed = 0
    print(f"{'ID':<4} {'RESULT':<6} {'STATUS':<22} {'SCORE':<6} QUESTION")
    for item in items:
        ans = qa.ask(item["question"])
        if item["answerable"]:
            src = ans.primary_source
            ok = (ans.status == "answered" and src is not None
                  and src.filename == item["expected_source"]
                  and item["expected_contains"].lower() in (ans.answer or "").lower())
        else:
            ok = ans.status == "insufficient_evidence"
        passed += ok
        print(f"{item['id']:<4} {'PASS' if ok else 'FAIL':<6} {ans.status:<22} {ans.top_score:<6.2f} {item['question']}")
    print(f"\nAccuracy: {passed}/{len(items)} = {passed / len(items):.0%}  (MIN_SCORE={settings.min_score})")
    return 0 if passed == len(items) else 1


def cmd_stats(args, settings: Settings, conn) -> int:
    print("Documents:")
    for r in conn.execute("SELECT d.filename, COUNT(c.chunk_id) n FROM documents d "
                          "LEFT JOIN chunks c ON c.doc_id = d.doc_id GROUP BY d.doc_id ORDER BY d.filename"):
        print(f"  {r['filename']:<28} {r['n']} chunks")
    total = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    print(f"Total chunks: {total}")
    print("Latest rejected/failed files:")
    rows = conn.execute("SELECT filename, status, reason FROM ingestion_log WHERE status IN "
                        "('rejected','failed') ORDER BY log_id DESC LIMIT 5").fetchall()
    for r in rows or []:
        print(f"  {r['filename']:<24} {r['status']:<9} {r['reason']}")
    if not rows:
        print("  (none)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.cli", description="Document Q&A with evidence")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("ingest", help="ingest documents (safe to re-run)")
    i.add_argument("--dir", help="directory to ingest (default: RAW_DATA_DIR)")
    a = sub.add_parser("ask", help="ask a question")
    a.add_argument("question")
    a.add_argument("--provider", choices=["extractive", "ollama"])
    a.add_argument("--json", action="store_true", help="print machine-readable output")
    e = sub.add_parser("eval", help="run the evaluation questions")
    e.add_argument("--file", help="path to an eval JSON file")
    sub.add_parser("stats", help="show documents, chunk counts and rejected files")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    settings = Settings.from_env()
    conn = connect(settings.db_path)
    try:
        init_db(conn)
        handler = {"ingest": cmd_ingest, "ask": cmd_ask, "eval": cmd_eval, "stats": cmd_stats}[args.command]
        return handler(args, settings, conn)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
