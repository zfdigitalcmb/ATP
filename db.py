# db.py
import os
from contextlib import contextmanager
import psycopg2
import psycopg2.extras
from psycopg2 import pool
from dotenv import load_dotenv
load_dotenv()

DB_MINCONN = int(os.environ.get("DB_MINCONN", 1))
DB_MAXCONN = int(os.environ.get("DB_MAXCONN", 10))

_pg_pool = None

def init_db_pool():
    global _pg_pool
    if _pg_pool is None:
        _pg_pool = pool.SimpleConnectionPool(
            DB_MINCONN,
            DB_MAXCONN,
            host=os.environ["PGHOST"],
            port=int(os.environ.get("PGPORT", 5432)),
            database=os.environ["PGDATABASE"],
            user=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"]
        )
    return _pg_pool

@contextmanager
def get_conn_cursor(dict_cursor=True):
    """Yields (conn, cursor) and automatically commits/rolls-back and returns connection."""
    global _pg_pool
    if _pg_pool is None:
        init_db_pool()
    conn = _pg_pool.getconn()
    try:
        if dict_cursor:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cur = conn.cursor()
        try:
            yield conn, cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        _pg_pool.putconn(conn)
