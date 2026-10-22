# seed_logs_to_pg.py
"""
Seed internalparts log CSV into ipv_ai_logs PostgreSQL table.

Usage:
  - put DB creds in .env (PGHOST, PGUSER, PGPASSWORD, PGDATABASE, PGPORT)
  - set CSV_PATH (optional) or CSV_BLOB_URL (optional) in .env or pass defaults below
  - python seed_logs_to_pg.py
"""

import os
import csv
import io
from datetime import datetime
from dateutil import parser as dateparser
from dotenv import load_dotenv
import requests
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

# DB env vars (expected)
PGHOST = os.environ.get("PGHOST")
PGUSER = os.environ.get("PGUSER")
PGPASSWORD = os.environ.get("PGPASSWORD")
PGDATABASE = os.environ.get("PGDATABASE")
PGPORT = os.environ.get("PGPORT", "5432")

# CSV source settings (use either CSV_PATH for local file or CSV_BLOB_URL for Azure SAS)
CSV_PATH = os.environ.get("CSV_PATH", "oring_log.csv")  # local fallback
CSV_BLOB_URL = os.environ.get("CSV_BLOB_URL")     # if provided, script will fetch from URL

# Option: create table if not exists (set to True if table might be missing)
CREATE_TABLE_IF_NOT_EXISTS = False

# Table/columns mapping - CSV header -> table column
CSV_TO_DB_COLUMNS = [
    ("Order Number", "order_number"),
    ("Employee ID", "employee_id"),
    ("Model", "model"),
    ("Stage", "stage"),
    ("Sub-task", "subtask"),
    ("Current O-Ring Quantity", "current_quantity"),
    ("Required O-Ring Quantity", "required_quantity"),
    ("Status", "status"),
    ("Original Image Path", "image_path"),
    ("Predicted Image Path", "predicted_image_path"),
    ("Date & Time", "created_at"),
]


def fetch_csv_from_url(url: str) -> io.StringIO:
    """Download CSV (SAS URL) and return StringIO (text)."""
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    # decode with utf-8-sig to handle BOM if present
    txt = r.content.decode("utf-8-sig")
    return io.StringIO(txt)


def open_csv_source():
    """Return file-like text object for csv.reader."""
    if CSV_BLOB_URL:
        print(f"Fetching CSV from blob URL: {CSV_BLOB_URL}")
        return fetch_csv_from_url(CSV_BLOB_URL)
    else:
        print(f"Reading CSV from local path: {CSV_PATH}")
        return open(CSV_PATH, "r", encoding="utf-8-sig")


def parse_row(row: dict) -> dict:
    """
    Convert CSV row to DB column dict:
     - parse ints
     - parse datetime
     - map header names to DB column names
    """
    out = {}
    for csv_header, db_col in CSV_TO_DB_COLUMNS:
        raw = row.get(csv_header, None)
        if raw is None or raw == "":
            out[db_col] = None
            continue

        # specific conversions
        if db_col in ("subtask", "current_quantity", "required_quantity"):
            try:
                out[db_col] = int(float(raw))  # safe cast (handles '1.0')
            except Exception:
                out[db_col] = None
        elif db_col == "created_at":
            try:
                # try dateutil parser (handles many formats)
                dt = dateparser.parse(raw)
                out[db_col] = dt
            except Exception:
                # fallback: try common formats
                for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M:%S"):
                    try:
                        out[db_col] = datetime.strptime(raw, fmt)
                        break
                    except Exception:
                        out[db_col] = None
        else:
            out[db_col] = raw.strip()
    return out


def create_table_if_needed(conn):
    """Create ipv_ai_logs table if flag is set and table doesn't exist."""
    create_sql = """
    CREATE TABLE IF NOT EXISTS ipv_ai_logs (
      id BIGSERIAL PRIMARY KEY,
      order_number TEXT NOT NULL,
      employee_id TEXT,
      model TEXT,
      stage TEXT,
      subtask INTEGER,
      current_quantity INTEGER,
      required_quantity INTEGER,
      status TEXT,
      image_path TEXT,
      predicted_image_path TEXT,
      created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    """
    with conn.cursor() as cur:
        cur.execute(create_sql)
        conn.commit()


def bulk_insert_rows(conn, rows):
    """
    Bulk insert list-of-dicts `rows` into ipv_ai_logs.
    If created_at is None, let DB use default (now()).
    """
    if not rows:
        print("No rows to insert.")
        return

    columns = [
        "order_number",
        "employee_id",
        "model",
        "stage",
        "subtask",
        "current_quantity",
        "required_quantity",
        "status",
        "image_path",
        "predicted_image_path",
        "created_at",
    ]

    # Prepare values in this exact order; psycopg2 will adapt Python datetimes
    values = []
    for r in rows:
        values.append(tuple(r.get(c) for c in columns))

    # Build SQL: we will use NULL for created_at if None
    template = "(" + ",".join(["%s"] * len(columns)) + ")"
    insert_sql = f"""
    INSERT INTO ipv_ai_logs ({', '.join(columns)})
    VALUES %s
    ON CONFLICT DO NOTHING
    """

    # If you want idempotency you need a unique constraint to use ON CONFLICT.
    # Current table has no unique constraint — ON CONFLICT DO NOTHING will do nothing
    # unless a constraint exists. If you want to skip duplicates on (order_number, subtask, created_at),
    # add a UNIQUE constraint to the table and adapt SQL.

    with conn.cursor() as cur:
        execute_values(cur, insert_sql, values, template=template)
    conn.commit()
    print(f"Inserted {len(values)} rows into ipv_ai_logs.")


def main():
    # Validate DB envs
    missing = [k for k in ("PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE") if not os.environ.get(k)]
    if missing:
        raise SystemExit(f"Missing DB env vars: {missing} (put them in .env)")

    # Open CSV
    try:
        csv_f = open_csv_source()
    except Exception as e:
        raise SystemExit(f"Failed to open CSV source: {e}")

    reader = csv.DictReader(csv_f)
    # Validate headers
    expected_headers = [h for h, _ in CSV_TO_DB_COLUMNS]
    for h in expected_headers:
        if h not in reader.fieldnames:
            print("Warning: expected CSV header missing:", h)
    parsed_rows = []
    for i, raw_row in enumerate(reader, start=1):
        try:
            parsed = parse_row(raw_row)
            # require order_number
            if not parsed.get("order_number"):
                print(f"Skipping row {i}: missing order_number")
                continue
            parsed_rows.append(parsed)
        except Exception as e:
            print(f"Failed parsing row {i}: {e}")

    if hasattr(csv_f, "close"):
        csv_f.close()

    if not parsed_rows:
        print("No valid rows parsed; exiting.")
        return

    # Connect to DB and insert
    conn = psycopg2.connect(
        host=PGHOST,
        dbname=PGDATABASE,
        user=PGUSER,
        password=PGPASSWORD,
        port=PGPORT,
    )
    try:
        if CREATE_TABLE_IF_NOT_EXISTS:
            create_table_if_needed(conn)
        bulk_insert_rows(conn, parsed_rows)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
