"""
API Configuration
"""
import os
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"

# Create output directory
OUTPUT_DIR.mkdir(exist_ok=True)

# Redis Configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Worker Configuration
MAX_WORKERS = int(os.getenv('MAX_WORKERS', 4))

# CORS Configuration
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')

# API Rate Limiting
RATE_LIMIT_REQUESTS = 10
RATE_LIMIT_PERIOD = "1 minute"

# Job Configuration
JOB_EXPIRE_TIME = 86400  # 24 hours
MAX_JOB_MEMORY = 1000

# Thread Pool for CPU-intensive tasks
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# Template Mapping
TEMPLATE_MAPPING = {
    # 일반 템플릿
    1: "template_1",
    2: "template_2", 
    3: "template_3",
    
    # 쇼츠 템플릿
    11: "template_1_shorts",
    12: "template_2_shorts",
    13: "template_3_shorts",
    
    # 스터디 클립
    31: "template_study_preview",
    32: "template_study_review",
    33: "template_study_shorts_preview",
    34: "template_study_shorts_review",
    35: "template_study_original",
    36: "template_study_shorts_original",
    
    # 교재형
    91: "template_textbook_basic",
    92: "template_textbook_advanced",
    93: "template_textbook_premium"
}