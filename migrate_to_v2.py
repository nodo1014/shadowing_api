#!/usr/bin/env python3
"""
Database Migration Script - Migrate to Schema V2
Safely migrates existing data to the new schema while preserving all information
"""

import sqlite3
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self, db_path="clipping.db", backup_dir="db_backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        self.conn = None
        
    def backup_database(self):
        """Create a backup of the current database"""
        os.makedirs(self.backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(self.backup_dir, f"clipping_backup_{timestamp}.db")
        
        logger.info(f"Creating database backup at {backup_path}")
        shutil.copy2(self.db_path, backup_path)
        return backup_path
        
    def connect(self):
        """Connect to the database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            
    def get_existing_tables(self):
        """Get list of existing tables"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        return [row[0] for row in cursor.fetchall()]
        
    def migrate_jobs_table(self):
        """Migrate existing clipping_jobs to new jobs table"""
        logger.info("Migrating jobs table...")
        
        cursor = self.conn.cursor()
        
        # Check if old table exists
        if 'clipping_jobs' not in self.get_existing_tables():
            logger.warning("No existing clipping_jobs table found")
            return
            
        # Create new jobs table if not exists
        with open('database/schema_v2.sql', 'r') as f:
            schema = f.read()
            # Execute only the jobs table creation
            jobs_schema = schema.split('-- 2. Templates table')[0].split('-- 1. Jobs table')[1]
            self.conn.executescript(jobs_schema)
        
        # Migrate data
        cursor.execute("""
            INSERT INTO jobs (
                id, created_at, updated_at, status, progress, message, error_message,
                job_type, api_endpoint, client_ip, template_id, start_time, end_time,
                duration, user_id, metadata
            )
            SELECT 
                id, created_at, updated_at, status, progress, message, error_message,
                'single' as job_type,  -- Default to single
                '/api/clip' as api_endpoint,  -- Default endpoint
                client_ip,
                template_number as template_id,
                start_time, end_time, duration,
                user_id,
                json_object(
                    'text_eng', text_eng,
                    'text_kor', text_kor,
                    'note', note,
                    'keywords', keywords,
                    'media_path', media_path,
                    'output_file', output_file,
                    'individual_clips', individual_clips
                ) as metadata
            FROM clipping_jobs
        """)
        
        self.conn.commit()
        logger.info(f"Migrated {cursor.rowcount} jobs")
        
    def create_output_videos_from_jobs(self):
        """Create output_videos entries from existing jobs"""
        logger.info("Creating output_videos entries...")
        
        cursor = self.conn.cursor()
        
        # Get all jobs with output files
        cursor.execute("""
            SELECT id, output_file, output_size, individual_clips, template_number
            FROM clipping_jobs 
            WHERE output_file IS NOT NULL
        """)
        
        jobs = cursor.fetchall()
        video_count = 0
        
        for job in jobs:
            job_id = job['id']
            output_file = job['output_file']
            output_size = job['output_size']
            template_id = job['template_number']
            
            # Insert final video
            if output_file and os.path.exists(output_file):
                cursor.execute("""
                    INSERT INTO output_videos (
                        job_id, video_type, file_path, file_name, file_size,
                        effect_type, subtitle_mode
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    job_id, 'final', output_file, os.path.basename(output_file),
                    output_size, self._guess_effect_type(output_file), 'both'
                ))
                video_count += 1
            
            # Insert individual clips
            if job['individual_clips']:
                try:
                    clips = json.loads(job['individual_clips'])
                    for i, clip_path in enumerate(clips):
                        if os.path.exists(clip_path):
                            cursor.execute("""
                                INSERT INTO output_videos (
                                    job_id, video_type, clip_index, file_path, file_name,
                                    file_size, effect_type, subtitle_mode
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                job_id, 'individual', i, clip_path, 
                                os.path.basename(clip_path),
                                os.path.getsize(clip_path) if os.path.exists(clip_path) else 0,
                                self._guess_effect_type(clip_path),
                                self._guess_subtitle_mode(clip_path)
                            ))
                            video_count += 1
                except (json.JSONDecodeError, TypeError):
                    pass
                    
        self.conn.commit()
        logger.info(f"Created {video_count} output_video entries")
        
    def _guess_effect_type(self, file_path):
        """Guess effect type from filename"""
        if 'blur' in file_path:
            return 'blur'
        elif 'crop' in file_path:
            return 'crop'
        elif 'fit' in file_path:
            return 'fit'
        return 'none'
        
    def _guess_subtitle_mode(self, file_path):
        """Guess subtitle mode from filename"""
        if 'nosub' in file_path:
            return 'nosub'
        elif 'korean' in file_path:
            return 'korean'
        elif 'both' in file_path:
            return 'both'
        return 'both'  # Default
        
    def create_subtitles_from_jobs(self):
        """Create subtitles entries from existing jobs"""
        logger.info("Creating subtitles entries...")
        
        cursor = self.conn.cursor()
        
        cursor.execute("""
            INSERT INTO subtitles (
                job_id, text_eng, text_kor, note, keywords, start_time, end_time
            )
            SELECT 
                id, text_eng, text_kor, note, keywords, start_time, end_time
            FROM clipping_jobs
            WHERE text_eng IS NOT NULL OR text_kor IS NOT NULL
        """)
        
        self.conn.commit()
        logger.info(f"Created {cursor.rowcount} subtitle entries")
        
    def populate_templates_table(self):
        """Populate templates table with known templates"""
        logger.info("Populating templates table...")
        
        # Read templates from templates/shadowing_patterns.json
        templates_file = "templates/shadowing_patterns.json"
        if os.path.exists(templates_file):
            with open(templates_file, 'r') as f:
                templates_data = json.load(f)
                
            cursor = self.conn.cursor()
            
            for template in templates_data.get('templates', []):
                cursor.execute("""
                    INSERT OR IGNORE INTO templates (
                        id, name, category, resolution_width, resolution_height, config
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    template['number'],
                    template.get('name', f"Template {template['number']}"),
                    'shorts' if template.get('is_shorts') else 'general',
                    1080 if template.get('is_shorts') else 1920,
                    1920 if template.get('is_shorts') else 1080,
                    json.dumps(template)
                ))
                
            self.conn.commit()
            logger.info(f"Populated {cursor.rowcount} templates")
            
    def create_indexes(self):
        """Create all necessary indexes"""
        logger.info("Creating indexes...")
        
        # Read and execute index creation from schema
        with open('database/schema_v2.sql', 'r') as f:
            schema = f.read()
            
        # Extract and execute CREATE INDEX statements
        for line in schema.split('\n'):
            if line.strip().startswith('CREATE INDEX'):
                try:
                    self.conn.execute(line)
                except sqlite3.OperationalError as e:
                    # Index might already exist
                    logger.debug(f"Index creation skipped: {e}")
                    
        self.conn.commit()
        logger.info("Indexes created")
        
    def run_migration(self):
        """Run the complete migration"""
        try:
            # Backup first
            backup_path = self.backup_database()
            logger.info(f"Backup created at {backup_path}")
            
            # Connect to database
            self.connect()
            
            # Create new schema
            logger.info("Creating new schema...")
            with open('database/schema_v2.sql', 'r') as f:
                schema = f.read()
                self.conn.executescript(schema)
            
            # Migrate data
            self.migrate_jobs_table()
            self.create_output_videos_from_jobs()
            self.create_subtitles_from_jobs()
            self.populate_templates_table()
            
            # Create indexes
            self.create_indexes()
            
            logger.info("Migration completed successfully!")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise
        finally:
            self.close()
            
    def verify_migration(self):
        """Verify the migration was successful"""
        self.connect()
        cursor = self.conn.cursor()
        
        # Check table counts
        tables = ['jobs', 'output_videos', 'subtitles', 'templates']
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            logger.info(f"{table}: {count} records")
            
        self.close()

if __name__ == "__main__":
    import sys
    
    # Check if database exists
    if not os.path.exists("clipping.db"):
        logger.error("Database file 'clipping.db' not found!")
        exit(1)
        
    # Create database directory if not exists
    os.makedirs("database", exist_ok=True)
    
    # Run migration
    migrator = DatabaseMigrator()
    
    print("=" * 60)
    print("Database Migration to Schema V2")
    print("=" * 60)
    print("\nThis will:")
    print("1. Backup your current database")
    print("2. Create new tables with enhanced schema")
    print("3. Migrate existing data")
    print("4. Create indexes for better performance")
    print("\nYour original database will be backed up.")
    
    # Check for command line argument to skip confirmation
    if len(sys.argv) > 1 and sys.argv[1] == "--yes":
        response = "yes"
    else:
        try:
            response = input("\nProceed with migration? (yes/no): ")
        except EOFError:
            response = "yes"  # Default to yes in non-interactive mode
            
    if response.lower() == 'yes':
        migrator.run_migration()
        print("\n" + "=" * 60)
        print("Migration Summary:")
        migrator.verify_migration()
    else:
        print("Migration cancelled.")