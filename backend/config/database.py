import os
import logging
from contextlib import contextmanager
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

_connection_pool = None
SCHEMA = os.environ.get("POSTGRES_SCHEMA", "public")


def get_connection_pool():
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
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("PostgreSQL connection pool closed")


@contextmanager
def get_db_connection():
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
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def execute_write(sql: str, params=None):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            try:
                return cur.fetchone()
            except Exception:
                return None


def init_database():
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
                    user_id TEXT
                )
            """)

            # Indexes for jobs
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs (created_at DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs (user_id)")

            # Indexes for logs
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs (timestamp DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_status ON logs (status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_filename ON logs (filename)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_user_id ON logs (user_id)")

            # Indexes for invoices
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_job_id ON invoices (job_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_vendor_name ON invoices (vendor_name)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_invoice_number ON invoices (invoice_number)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices (status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_created_at ON invoices (created_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_user_id ON invoices (user_id)")

            # GIN indexes on JSONB columns
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_filenames_gin ON jobs USING GIN (filenames)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_logs_metadata_gin ON logs USING GIN (metadata)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_invoices_line_items_gin ON invoices USING GIN (line_items)")

        logger.info("Database initialized successfully")
