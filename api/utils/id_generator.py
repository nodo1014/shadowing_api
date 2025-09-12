"""
ID Generator for Job Management
Provides date-based sequential IDs (001, 002, etc per day)
"""
import os
import json
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

class DateBasedIDGenerator:
    """Thread-safe date-based sequential ID generator"""
    
    def __init__(self, counter_file: str = "daily_job_counters.json"):
        self.counter_file = Path(counter_file)
        self._lock = threading.Lock()
        self._counters = self._load_counters()
    
    def _load_counters(self) -> Dict[str, int]:
        """Load counters from file"""
        if self.counter_file.exists():
            try:
                with open(self.counter_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_counters(self):
        """Save counters to file"""
        try:
            with open(self.counter_file, 'w') as f:
                json.dump(self._counters, f, indent=2)
        except Exception as e:
            import logging
            logging.warning(f"Failed to save counter file: {e}")
    
    def get_next_id(self, date_str: Optional[str] = None) -> str:
        """Get next sequential ID for given date"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        with self._lock:
            # Get current counter for this date
            current = self._counters.get(date_str, 0)
            current += 1
            self._counters[date_str] = current
            self._save_counters()
            
            # Return as 3-digit zero-padded string
            return f"{current:03d}"
    
    def get_current_count(self, date_str: Optional[str] = None) -> int:
        """Get current count for date without incrementing"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
        
        with self._lock:
            return self._counters.get(date_str, 0)
    
    def reset_date(self, date_str: str):
        """Reset counter for specific date"""
        with self._lock:
            if date_str in self._counters:
                del self._counters[date_str]
                self._save_counters()
    
    def cleanup_old_dates(self, days_to_keep: int = 30):
        """Remove counters older than specified days"""
        from datetime import timedelta
        
        cutoff = datetime.now() - timedelta(days=days_to_keep)
        
        with self._lock:
            dates_to_remove = []
            for date_str in self._counters.keys():
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    if date_obj < cutoff:
                        dates_to_remove.append(date_str)
                except:
                    continue
            
            for date_str in dates_to_remove:
                del self._counters[date_str]
            
            if dates_to_remove:
                self._save_counters()

# Global instance
id_generator = DateBasedIDGenerator()

def get_next_folder_id(date_str: Optional[str] = None) -> str:
    """Get next folder ID for the given date"""
    return id_generator.get_next_id(date_str)

def get_job_folder_path(base_dir: Path, job_id: str) -> Path:
    """Get full folder path for job"""
    # job_id is actually the folder ID (001, 002, etc)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return base_dir / date_str / job_id