"""
Database connection management
"""
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = Path("./clipping.db")


@contextmanager
def get_db_connection():
    """Get database connection context manager"""
    conn = None
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()


def init_database():
    """Initialize database with tables"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Create jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                message TEXT,
                error TEXT,
                media_path TEXT,
                start_time REAL,
                end_time REAL,
                text_eng TEXT,
                text_kor TEXT,
                note TEXT,
                keywords TEXT,
                clipping_type INTEGER,
                template_number INTEGER,
                individual_clips BOOLEAN DEFAULT 0,
                output_file TEXT,
                results TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)
        
        # Create batch_jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_jobs (
                id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                clip_index INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                output_file TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (batch_id) REFERENCES jobs (id) ON DELETE CASCADE
            )
        """)
        
        # Create indexes (with error handling for existing tables)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at)")
        except sqlite3.OperationalError:
            pass
        
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_batch_job_id ON batch_jobs(batch_id)")
        except sqlite3.OperationalError:
            pass
        
        conn.commit()
        logger.info("Database initialized successfully")


def execute_query(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """Execute SELECT query and return results"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        return [dict(zip(columns, row)) for row in rows]


def execute_update(query: str, params: Optional[tuple] = None) -> int:
    """Execute INSERT/UPDATE/DELETE query and return affected rows"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        conn.commit()
        return cursor.rowcount


def execute_insert(query: str, params: Optional[tuple] = None) -> Optional[int]:
    """Execute INSERT query and return last row id"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        conn.commit()
        return cursor.lastrowid