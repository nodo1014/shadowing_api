#!/usr/bin/env python3
"""
Database migration script: clipping_type -> template_number
"""

import sqlite3
import os

def migrate_database():
    """Migrate database schema from clipping_type to template_number"""
    
    db_path = "clipping.db"
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if clipping_type column exists
        cursor.execute("PRAGMA table_info(clipping_jobs)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'clipping_type' in column_names and 'template_number' not in column_names:
            print("Migrating clipping_jobs table...")
            
            # SQLite doesn't support direct column rename, so we need to:
            # 1. Create new table with correct schema
            # 2. Copy data
            # 3. Drop old table
            # 4. Rename new table
            
            cursor.execute("""
                CREATE TABLE clipping_jobs_new (
                    id VARCHAR PRIMARY KEY,
                    created_at DATETIME,
                    updated_at DATETIME,
                    status VARCHAR,
                    progress INTEGER,
                    message TEXT,
                    error_message TEXT,
                    media_path VARCHAR,
                    media_filename VARCHAR,
                    template_number INTEGER,
                    start_time FLOAT,
                    end_time FLOAT,
                    duration FLOAT,
                    text_eng TEXT,
                    text_kor TEXT,
                    note TEXT,
                    keywords JSON,
                    output_file VARCHAR,
                    output_size INTEGER,
                    individual_clips JSON,
                    user_id VARCHAR,
                    client_ip VARCHAR
                )
            """)
            
            # Copy data from old table to new table
            cursor.execute("""
                INSERT INTO clipping_jobs_new 
                SELECT id, created_at, updated_at, status, progress, message, error_message,
                       media_path, media_filename, clipping_type, start_time, end_time, duration,
                       text_eng, text_kor, note, keywords, output_file, output_size,
                       individual_clips, user_id, client_ip
                FROM clipping_jobs
            """)
            
            # Drop old table
            cursor.execute("DROP TABLE clipping_jobs")
            
            # Rename new table
            cursor.execute("ALTER TABLE clipping_jobs_new RENAME TO clipping_jobs")
            
            print("✓ clipping_jobs table migrated successfully")
        
        # Check batch_jobs table
        cursor.execute("PRAGMA table_info(batch_jobs)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'clipping_type' in column_names and 'template_number' not in column_names:
            print("Migrating batch_jobs table...")
            
            cursor.execute("""
                CREATE TABLE batch_jobs_new (
                    id VARCHAR PRIMARY KEY,
                    created_at DATETIME,
                    updated_at DATETIME,
                    status VARCHAR,
                    progress INTEGER,
                    total_clips INTEGER,
                    completed_clips INTEGER,
                    media_path VARCHAR,
                    template_number INTEGER,
                    output_files JSON,
                    user_id VARCHAR,
                    client_ip VARCHAR
                )
            """)
            
            cursor.execute("""
                INSERT INTO batch_jobs_new
                SELECT id, created_at, updated_at, status, progress, total_clips,
                       completed_clips, media_path, clipping_type, output_files,
                       user_id, client_ip
                FROM batch_jobs
            """)
            
            cursor.execute("DROP TABLE batch_jobs")
            cursor.execute("ALTER TABLE batch_jobs_new RENAME TO batch_jobs")
            
            print("✓ batch_jobs table migrated successfully")
        
        conn.commit()
        print("\nDatabase migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()