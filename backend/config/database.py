"""
Japan OCR Tool - Database Configuration

Manages the PostgreSQL connection pool and provides helpers for executing
queries and writes. Also owns the schema migration logic that creates all
application tables and indexes on first run.

Key Features:
- Connection pooling: thread-safe pool via psycopg2.pool.ThreadedConnectionPool
- Schema management: idempotent CREATE TABLE / CREATE INDEX migrations
- Query helpers: execute_query for SELECTs, execute_write for DML with RETURNING

Dependencies: psycopg2
Author: SHIRIN MIRZI M K
"""

import logging
import os
from contextlib import contextmanager

from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_connection_pool = None
SCHEMA = os.environ.get("POSTGRES_SCHEMA", "public")


def get_connection_pool():
    """
    Return the shared ThreadedConnectionPool, creating it on first call.

    Returns:
        psycopg2.pool.ThreadedConnectionPool configured from environment
        variables (POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, etc.).
    """
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.environ.get("POSTGRES_HOST", "localhost"),
            port=int(os.environ.get("POSTGRES_PORT", 5432)),
            dbname=os.environ.get("POSTGRES_DB", "invoice_processor"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", ""),
            sslmode=os.environ.get("POSTGRES_SSLMODE", "prefer"),
        )
        logger.info("PostgreSQL connection pool created")
    return _connection_pool


def close_connection_pool():
    """
    Close all connections in the pool and reset the module-level reference.

    Safe to call even if the pool was never initialised.
    """
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("PostgreSQL connection pool closed")


@contextmanager
def get_db_connection():
    """
    Context manager that yields an auto-committing database connection.

    Automatically sets the search_path to the configured schema on each
    checkout, commits on clean exit, and rolls back on exception.

    Raises:
        Exception: Re-raises any database or application error after rollback.
    """
    conn_pool = get_connection_pool()
    conn = conn_pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"SET search_path TO {SCHEMA}, public")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn_pool.putconn(conn)


def execute_query(sql: str, params=None):
    """
    Execute a SELECT statement and return all result rows.

    Args:
        sql: The SQL query string, using %s placeholders for parameters.
        params: Optional sequence or mapping of query parameters.

    Returns:
        List of RealDictRow objects; each row behaves like a dict.
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def execute_write(sql: str, params=None):
    """
    Execute an INSERT, UPDATE, or DELETE statement.

    Args:
        sql: The SQL DML string, using %s placeholders for parameters.
            Include a RETURNING clause to get back the affected row.
        params: Optional sequence or mapping of statement parameters.

    Returns:
        The first row returned by a RETURNING clause as a RealDictRow,
        or None when no rows are returned.
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            try:
                return cur.fetchone()
            except Exception:
                return None


def init_database():
    """
    Create all required tables, columns, and indexes if they do not exist.

    Idempotent — safe to call on every application startup. ALTER TABLE
    statements add missing columns to tables created before schema migrations
    were introduced, ensuring backward compatibility.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
            cur.execute(f"SET search_path TO {SCHEMA}, public")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    user_id TEXT,
                    status TEXT NOT NULL,
                    total_count INTEGER NOT NULL,
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    batch_name TEXT,
                    filenames JSONB NOT NULL,
                    results JSONB
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    error TEXT,
                    metadata JSONB,
                    user_id TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id SERIAL PRIMARY KEY,
                    job_id TEXT REFERENCES jobs(id),
                    filename TEXT NOT NULL,
                    invoice_number TEXT,
                    vendor_name TEXT,
                    vendor_address TEXT,
                    customer_name TEXT,
                    customer_address TEXT,
                    invoice_date TEXT,
                    due_date TEXT,
                    total_amount TEXT,
                    tax_amount TEXT,
                    subtotal TEXT,
                    currency TEXT,
                    line_items JSONB,
                    raw_text TEXT,
                    blob_url TEXT,
                    blob_path TEXT,
                    upload_folder TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    user_id TEXT,
                    customer_code TEXT,
                    order_number TEXT
                )
            """)

            # Add new columns to existing tables if they were created before this migration
            cur.execute(
                "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS customer_code TEXT"
            )
            cur.execute(
                "ALTER TABLE invoices ADD COLUMN IF NOT EXISTS order_number TEXT"
            )
            cur.execute(
                "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS current_file TEXT"
            )

            # Indexes for jobs
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_created_at "
                "ON jobs (created_at DESC)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs (user_id)")

            # Indexes for logs
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_timestamp "
                "ON logs (timestamp DESC)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_status ON logs (status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_filename ON logs (filename)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs (user_id)")

            # Indexes for invoices
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_job_id ON invoices (job_id)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_invoices_vendor_name "
                "ON invoices (vendor_name)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_invoices_invoice_number "
                "ON invoices (invoice_number)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices (status)")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_invoices_created_at "
                "ON invoices (created_at)"
            )
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices (user_id)")

            # Master data tables for invoice routing
            cur.execute("""
                CREATE TABLE IF NOT EXISTS daily_invoice_master (
                    id SERIAL PRIMARY KEY,
                    customer_cd TEXT NOT NULL,
                    destination_cd TEXT NOT NULL,
                    row_number INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS monthly_invoice_master (
                    id SERIAL PRIMARY KEY,
                    customer_cd TEXT NOT NULL,
                    destination_cd TEXT NOT NULL,
                    row_number INTEGER,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_master_customer_cd "
                "ON daily_invoice_master (customer_cd)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_monthly_master_customer_cd "
                "ON monthly_invoice_master (customer_cd)"
            )

            # GIN indexes on JSONB columns
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_filenames_gin "
                "ON jobs USING GIN (filenames)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_logs_metadata_gin "
                "ON logs USING GIN (metadata)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_invoices_line_items_gin "
                "ON invoices USING GIN (line_items)"
            )

        logger.info("Database initialized successfully")
