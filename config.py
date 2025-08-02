"""
Configuration file for Shadowing API
설정 파일
"""
import os
from pathlib import Path

# 서버 설정
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8080'))
WORKERS = int(os.getenv('WORKERS', '4'))
MAX_WORKERS = int(os.getenv('MAX_WORKERS', '4'))

# 디렉토리 설정
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', '/mnt/ssd1t/output'))
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', '/media'))

# Redis 설정
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# 보안 설정
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*')
ALLOWED_MEDIA_ROOTS = [
    Path('/mnt/qnap/media_eng/indexed_media'),
    Path('/mnt/qnap/media_kor'),
    MEDIA_ROOT,
    Path(__file__).parent / 'media',  # Local media directory for testing
]

# 추가 미디어 루트
if os.getenv('ADDITIONAL_MEDIA_ROOTS'):
    for root in os.getenv('ADDITIONAL_MEDIA_ROOTS').split(':'):
        ALLOWED_MEDIA_ROOTS.append(Path(root))

# 작업 설정
JOB_EXPIRE_TIME = 86400  # 24시간
MAX_JOB_MEMORY = 1000  # 메모리에 저장할 최대 작업 수
PROCESS_TIMEOUT = 300  # FFmpeg 작업 타임아웃 (초)
MAX_CONCURRENT_JOBS = int(os.getenv('MAX_CONCURRENT_JOBS', '10'))  # 동시 작업 수 제한
CLEANUP_INTERVAL = 3600  # 정리 작업 실행 간격 (초)

# API 제한
RATE_LIMIT_PER_MINUTE = 60  # 분당 요청 수 제한
RATE_LIMIT_PER_HOUR = 1000  # 시간당 요청 수 제한

# 로깅 설정
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# SSL 설정
USE_SSL = os.getenv('USE_SSL', 'false').lower() == 'true'
SSL_KEYFILE = os.getenv('SSL_KEYFILE', 'ssl/key.pem')
SSL_CERTFILE = os.getenv('SSL_CERTFILE', 'ssl/cert.pem')

# 데이터베이스 설정
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clipping.db")

# 비디오 처리 설정
VIDEO_PROCESSING = {
    "max_input_duration": 600,  # 최대 입력 비디오 길이 (초)
    "max_output_size": 500 * 1024 * 1024,  # 최대 출력 파일 크기 (500MB)
    "allowed_extensions": [".mp4", ".avi", ".mov", ".mkv", ".webm"],
    "temp_cleanup_delay": 300,  # 임시 파일 정리 지연 시간 (초)
}

# FFmpeg 설정
FFMPEG_ENCODING_SETTINGS = {
    "no_subtitle": {
        "video_codec": "libx264",
        "preset": "medium",
        "crf": "16",
        "profile": "high",
        "level": "4.1",
        "pix_fmt": "yuv420p",
        "width": "1920",
        "height": "1080",
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "x264opts": "keyint=240:min-keyint=24:scenecut=40",
        "tune": "film"
    },
    "with_subtitle": {
        "video_codec": "libx264",
        "preset": "medium",
        "crf": "16",
        "profile": "high",
        "level": "4.1",
        "pix_fmt": "yuv420p",
        "width": "1920",
        "height": "1080",
        "audio_codec": "aac",
        "audio_bitrate": "192k",
        "x264opts": "keyint=240:min-keyint=24:scenecut=40",
        "tune": "film"
    }
}

# Shadowing 패턴 (legacy)
SHADOWING_PATTERN = {
    "no_subtitle": 2,
    "korean_with_note": 2,
    "both_subtitle": 2
}

# 성능 최적화 설정
PERFORMANCE = {
    "enable_caching": os.getenv('ENABLE_CACHING', 'true').lower() == 'true',
    "cache_ttl": 3600,  # 캐시 유효 시간 (초)
    "enable_parallel_processing": os.getenv('ENABLE_PARALLEL', 'true').lower() == 'true',
    "batch_size": int(os.getenv('BATCH_SIZE', '5')),  # 배치 처리 크기
}

# 모니터링 설정
MONITORING = {
    "enable_metrics": os.getenv('ENABLE_METRICS', 'false').lower() == 'true',
    "metrics_port": int(os.getenv('METRICS_PORT', '9090')),
    "health_check_interval": 60,  # 헬스 체크 간격 (초)
}