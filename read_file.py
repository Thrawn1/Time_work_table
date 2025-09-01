#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MSK-only payroll ingester from a single .dat source (tail-reader) with SQLite storage.
- Reads last N lines from a .dat file (default 500), parses only emp_id and ts (local MSK),
  filters by year+month, and commits unique events to SQLite.
- No UTC used. Stores only local timestamps (TEXT 'YYYY-MM-DD HH:MM:SS').
- Two layers in DB: events_raw (from file) and events_manual (boss edits). Effective view merges them with
  manual having priority.

Subcommands:
  init-db                 Initialize DB schema (idempotent)
  ingest --file F --year Y --month M [--tail-size N] [--extend-limit K] [--encoding enc]
  manual-add --emp-id E --ts "YYYY-MM-DD HH:MM:SS" [--reason R] [--created-by U] [--raw-id ID]
  manual-void (--id MID | --emp-id E --ts "YYYY-MM-DD HH:MM:SS")
  report-month --year Y --month M [--emp-id E]

Examples:
  python msk_ingest_tail_sqlite.py init-db --db payroll.db
  python msk_ingest_tail_sqlite.py ingest --db payroll.db --file ./usb/raw.dat --year 2025 --month 9 --tail-size 500
  python msk_ingest_tail_sqlite.py manual-add --db payroll.db --emp-id 4 --ts "2025-09-01 07:55" --reason "исправление" --created-by "начальник"
  python msk_ingest_tail_sqlite.py manual-void --db payroll.db --emp-id 4 --ts "2025-09-01 07:55"
  python msk_ingest_tail_sqlite.py report-month --db payroll.db --year 2025 --month 9
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import io
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

# ------------------------------
# Data model (in-memory)
# ------------------------------

@dataclass
class Event:
    emp_id: int
    ts_local: dt.datetime  # naive local MSK
    raw_text: str          # original line (for audit)

# ------------------------------
# Utilities
# ------------------------------

def try_decode(data: bytes, encodings: List[str]) -> str:
    last_err: Optional[Exception] = None
    for enc in encodings:
        try:
            return data.decode(enc)
        except Exception as e:
            last_err = e
    raise last_err  # type: ignore


def read_tail_lines(path: Path, n_lines: int, chunk_size: int = 64 * 1024) -> List[str]:
    """Efficiently read the last n_lines from a text file without loading entire file."""
    if n_lines <= 0:
        return []
    size = path.stat().st_size
    with path.open('rb') as f:
        # Accumulate from the end
        blocks: List[bytes] = []
        remaining = size
        lines_found = 0
        while remaining > 0 and lines_found <= n_lines:
            read_size = chunk_size if remaining >= chunk_size else remaining
            f.seek(remaining - read_size)
            chunk = f.read(read_size)
            blocks.append(chunk)
            remaining -= read_size
            lines_found = b"".join(reversed(blocks)).count(b"\n")
        data = b"".join(reversed(blocks))
    # Split into lines robustly (handles \r\n/\n). Keep only full lines.
    text = try_decode(data, ["utf-8", "utf-8-sig", "cp1251"])  # simple fallback
    # Ensure we don't return a trailing partial line if file didn't end with newline
    if not text.endswith("\n"):
        # drop the last partial line segment after the final newline, if any
        last_nl = text.rfind("\n")
        if last_nl != -1:
            text = text[: last_nl + 1]
        else:
            # file has no newlines; return empty, we consider it partial
            return []
    lines = text.splitlines()
    return lines[-n_lines:]


def detect_and_split(line: str) -> List[str]:
    # Trim leading/trailing whitespace indentation
    s = line.strip()
    if not s:
        return []
    if "\t" in s:
        return s.split("\t")
    # default: split by any amount of whitespace
    return s.split()


def parse_dat_lines(lines: Iterable[str]) -> Tuple[List[Event], List[Tuple[str, str]]]:
    events: List[Event] = []
    rejected: List[Tuple[str, str]] = []  # (raw_text, reason)
    for ln in lines:
        try:
            parts = detect_and_split(ln)
            if not parts:
                continue
            if len(parts) < 6:
                rejected.append((ln, "insufficient_fields"))
                continue
            emp_id_str = parts[0]
            ts_str = parts[1]
            # validate emp_id
            try:
                emp_id = int(emp_id_str)
                if emp_id <= 0:
                    raise ValueError("emp_id <= 0")
            except Exception:
                rejected.append((ln, "bad_emp_id"))
                continue
            # parse ts
            try:
                ts_local = dt.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                rejected.append((ln, "bad_ts_format"))
                continue
            events.append(Event(emp_id=emp_id, ts_local=ts_local, raw_text=ln.rstrip("\n")))
        except Exception as e:
            rejected.append((ln, f"unexpected_error:{e!r}"))
    return events, rejected


def filter_by_month(events: List[Event], year: int, month: int) -> List[Event]:
    res = [e for e in events if e.ts_local.year == year and e.ts_local.month == month]
    # Sort for stable inserts/reporting
    res.sort(key=lambda e: (e.ts_local, e.emp_id))
    return res

# ------------------------------
# SQLite schema & operations
# ------------------------------

SCHEMA_SQL = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS import_batches (
  id INTEGER PRIMARY KEY,
  source_file_name TEXT NOT NULL,
  imported_at_local TEXT NOT NULL,
  tail_size INTEGER NOT NULL,
  rows_read INTEGER NOT NULL,
  rows_ok INTEGER NOT NULL,
  rows_rejected INTEGER NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS events_raw (
  id INTEGER PRIMARY KEY,
  emp_id INTEGER NOT NULL,
  ts_local TEXT NOT NULL, -- 'YYYY-MM-DD HH:MM:SS' (MSK)
  import_batch_id INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
  raw_line_hash TEXT NOT NULL,
  source_line_no INTEGER,
  UNIQUE(emp_id, ts_local)
);

CREATE TABLE IF NOT EXISTS events_manual (
  id INTEGER PRIMARY KEY,
  emp_id INTEGER NOT NULL,
  ts_local TEXT NOT NULL,
  reason TEXT,
  created_by TEXT,
  created_at_local TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','void')),
  raw_id INTEGER REFERENCES events_raw(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS events_rejected (
  id INTEGER PRIMARY KEY,
  import_batch_id INTEGER NOT NULL REFERENCES import_batches(id) ON DELETE CASCADE,
  raw_text TEXT NOT NULL,
  reason TEXT NOT NULL
);

CREATE VIEW IF NOT EXISTS events_effective AS
-- active manual events
SELECT m.emp_id, m.ts_local, 'manual' AS source, m.id AS src_id
FROM events_manual m
WHERE m.status = 'active'
UNION ALL
-- raw events not overridden by active manual (by raw_id or by same emp_id+ts_local)
SELECT r.emp_id, r.ts_local, 'raw' AS source, r.id AS src_id
FROM events_raw r
WHERE NOT EXISTS (
  SELECT 1 FROM events_manual m
  WHERE m.status='active' AND (
    m.raw_id = r.id OR (m.emp_id = r.emp_id AND m.ts_local = r.ts_local)
  )
);
"""


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


def insert_import_batch(conn: sqlite3.Connection, source_file_name: str, tail_size: int, rows_read: int, rows_ok: int, rows_rejected: int, note: Optional[str] = None) -> int:
    imported_at_local = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        "INSERT INTO import_batches(source_file_name, imported_at_local, tail_size, rows_read, rows_ok, rows_rejected, note) VALUES(?,?,?,?,?,?,?)",
        (source_file_name, imported_at_local, tail_size, rows_read, rows_ok, rows_rejected, note),
    )
    return int(cur.lastrowid)


def bulk_insert_raw(conn: sqlite3.Connection, batch_id: int, events: List[Event]) -> Tuple[int, int]:
    """Insert events into events_raw with UNIQUE(emp_id, ts_local). Returns (inserted, duplicates)."""
    inserted = 0
    duplicates = 0
    for e in events:
        key = f"{e.emp_id}|{e.ts_local.strftime('%Y-%m-%d %H:%M:%S')}"
        h = sha1(key)
        try:
            conn.execute(
                """
                INSERT INTO events_raw(emp_id, ts_local, import_batch_id, raw_line_hash, source_line_no)
                VALUES(?,?,?,?,NULL)
                ON CONFLICT(emp_id, ts_local) DO NOTHING
                """,
                (e.emp_id, e.ts_local.strftime('%Y-%m-%d %H:%M:%S'), batch_id, h),
            )
            if conn.total_changes > 0:
                inserted += 1
            else:
                duplicates += 1
        except sqlite3.IntegrityError:
            duplicates += 1
    return inserted, duplicates


def bulk_insert_rejected(conn: sqlite3.Connection, batch_id: int, rejected: List[Tuple[str, str]]) -> None:
    if not rejected:
        return
    conn.executemany(
        "INSERT INTO events_rejected(import_batch_id, raw_text, reason) VALUES(?,?,?)",
        [(batch_id, raw, reason) for (raw, reason) in rejected],
    )


def manual_add(conn: sqlite3.Connection, emp_id: int, ts_local_str: str, reason: Optional[str], created_by: Optional[str], raw_id: Optional[int]) -> int:
    created_at_local = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute(
        """
        INSERT INTO events_manual(emp_id, ts_local, reason, created_by, created_at_local, status, raw_id)
        VALUES(?,?,?,?,?,'active',?)
        """,
        (emp_id, ts_local_str, reason, created_by, created_at_local, raw_id),
    )
    return int(cur.lastrowid)


def manual_void(conn: sqlite3.Connection, manual_id: Optional[int], emp_id: Optional[int], ts_local_str: Optional[str]) -> int:
    if manual_id is not None:
        cur = conn.execute("UPDATE events_manual SET status='void' WHERE id=? AND status='active'", (manual_id,))
        return cur.rowcount
    if emp_id is not None and ts_local_str is not None:
        cur = conn.execute(
            "UPDATE events_manual SET status='void' WHERE emp_id=? AND ts_local=? AND status='active'",
            (emp_id, ts_local_str),
        )
        return cur.rowcount
    raise ValueError("Provide either --id or (--emp-id and --ts)")


def report_month(conn: sqlite3.Connection, year: int, month: int, emp_id: Optional[int]) -> List[Tuple[int, str, str]]:
    start = dt.datetime(year, month, 1)
    end_month = month + 1
    end_year = year
    if end_month == 13:
        end_month = 1
        end_year += 1
    end = dt.datetime(end_year, end_month, 1)
    params: Tuple = (start.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S'))
    sql = "SELECT emp_id, ts_local, source FROM events_effective WHERE ts_local >= ? AND ts_local < ?"
    if emp_id is not None:
        sql += " AND emp_id = ?"
        params = (params[0], params[1], emp_id)
    sql += " ORDER BY emp_id, ts_local"
    cur = conn.execute(sql, params)
    return cur.fetchall()

# ------------------------------
# Ingest orchestration
# ------------------------------

def ingest_tail(db_path: Path, file_path: Path, year: int, month: int, tail_size: int, extend_limit: int, encoding_hint: Optional[str]) -> None:
    if not file_path.exists():
        print(f"[error] File not found: {file_path}")
        sys.exit(2)

    # Iterative tail expansion (only if needed)
    current_tail = max(1, tail_size)
    all_events: List[Event] = []
    rejected_all: List[Tuple[str, str]] = []

    while True:
        lines = read_tail_lines(file_path, current_tail)
        if not lines:
            print(f"[warn] Tail read returned 0 lines for N={current_tail}")
        events, rejected = parse_dat_lines(lines)
        filtered = filter_by_month(events, year, month)
        all_events = filtered
        rejected_all = rejected
        # Stop if we got any events for the period or reached limit or read whole file (heuristic)
        if all_events or current_tail >= extend_limit:
            break
        # else expand 2x, capped by extend_limit
        current_tail = min(current_tail * 2, extend_limit)

    # Commit to DB
    conn = connect_db(db_path)
    try:
        init_db(conn)
        conn.execute("BEGIN")
        batch_id = insert_import_batch(
            conn,
            source_file_name=str(file_path),
            tail_size=current_tail,
            rows_read=len(lines) if 'lines' in locals() else 0,
            rows_ok=len(all_events),
            rows_rejected=len(rejected_all),
            note=f"period={year:04d}-{month:02d}",
        )
        ins, dups = bulk_insert_raw(conn, batch_id, all_events)
        bulk_insert_rejected(conn, batch_id, rejected_all)
        conn.commit()
        print(f"[ok] Import batch #{batch_id}: inserted={ins}, duplicates={dups}, rejected={len(rejected_all)}, tail_used={current_tail}")
    except Exception as e:
        conn.rollback()
        print(f"[error] Ingest failed: {e}")
        raise
    finally:
        conn.close()

# ------------------------------
# CLI
# ------------------------------

def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MSK-only tail ingester for payroll .dat into SQLite")
    p.add_argument("--db", required=True, help="Path to SQLite DB (e.g., payroll.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_init = sub.add_parser("init-db", help="Initialize database schema")

    sp_ing = sub.add_parser("ingest", help="Ingest last N lines from .dat for given year/month")
    sp_ing.add_argument("--file", required=True, help="Path to .dat file")
    sp_ing.add_argument("--year", type=int, required=True, help="Target year")
    sp_ing.add_argument("--month", type=int, required=True, choices=range(1,13), help="Target month 1-12")
    sp_ing.add_argument("--tail-size", type=int, default=500, help="Initial tail lines to read")
    sp_ing.add_argument("--extend-limit", type=int, default=50_000, help="Max lines to read if month not found in tail")
    sp_ing.add_argument("--encoding", default=None, help="Optional encoding hint (unused; utf-8/cp1251 auto tried)")

    sp_add = sub.add_parser("manual-add", help="Add a manual event (boss edit)")
    sp_add.add_argument("--emp-id", type=int, required=True)
    sp_add.add_argument("--ts", required=True, help="Local MSK timestamp 'YYYY-MM-DD HH:MM:SS'")
    sp_add.add_argument("--reason", default=None)
    sp_add.add_argument("--created-by", default=None)
    sp_add.add_argument("--raw-id", type=int, default=None)

    sp_void = sub.add_parser("manual-void", help="Void (deactivate) a manual event")
    g = sp_void.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", type=int)
    g.add_argument("--by-emp-ts", nargs=2, metavar=("EMP_ID","TS"), help="Target by (emp_id, ts_local)")

    sp_rep = sub.add_parser("report-month", help="List effective events for a month")
    sp_rep.add_argument("--year", type=int, required=True)
    sp_rep.add_argument("--month", type=int, required=True, choices=range(1,13))
    sp_rep.add_argument("--emp-id", type=int, default=None)

    return p


def main(argv: List[str]) -> None:
    cli = build_cli()
    args = cli.parse_args(argv)
    db_path = Path(args.db)

    if args.cmd == 'init-db':
        conn = connect_db(db_path)
        try:
            init_db(conn)
            print("[ok] DB schema initialized")
        finally:
            conn.close()
        return

    if args.cmd == 'ingest':
        ingest_tail(
            db_path=db_path,
            file_path=Path(args.file),
            year=args.year,
            month=args.month,
            tail_size=args.tail_size,
            extend_limit=args.extend_limit,
            encoding_hint=args.encoding,
        )
        return

    if args.cmd == 'manual-add':
        conn = connect_db(db_path)
        try:
            init_db(conn)
            # Validate ts format
            try:
                dt.datetime.strptime(args.ts, '%Y-%m-%d %H:%M:%S')
            except Exception:
                print("[error] --ts must be 'YYYY-MM-DD HH:MM:SS'")
                sys.exit(2)
            mid = manual_add(conn, args.emp_id, args.ts, args.reason, args.created_by, args.raw_id)
            conn.commit()
            print(f"[ok] manual event id={mid} added")
        finally:
            conn.close()
        return

    if args.cmd == 'manual-void':
        conn = connect_db(db_path)
        try:
            init_db(conn)
            if args.id is not None:
                changed = manual_void(conn, manual_id=args.id, emp_id=None, ts_local_str=None)
            else:
                emp_id = int(args.by_emp_ts[0])
                ts_local_str = args.by_emp_ts[1]
                changed = manual_void(conn, manual_id=None, emp_id=emp_id, ts_local_str=ts_local_str)
            conn.commit()
            print(f"[ok] manual events voided: {changed}")
        finally:
            conn.close()
        return

    if args.cmd == 'report-month':
        conn = connect_db(db_path)
        try:
            init_db(conn)
            rows = report_month(conn, args.year, args.month, args.emp_id)
            if not rows:
                print("(no rows)")
            else:
                for emp_id, ts_local, source in rows:
                    print(f"{emp_id}\t{ts_local}\t{source}")
        finally:
            conn.close()
        return


if __name__ == '__main__':
    main(sys.argv[1:])
