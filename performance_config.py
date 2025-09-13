"""
Performance Configuration for AMD 5600G
AMD 5600G CPU에 최적화된 성능 설정
"""

import os
import multiprocessing

# CPU 정보
CPU_CORES = multiprocessing.cpu_count()  # 12 스레드
PHYSICAL_CORES = 6  # 물리 코어 수

# Worker 설정 - CPU 집약적 작업에 최적화
MAX_WORKERS = min(PHYSICAL_CORES, 6)  # 물리 코어 수 기준
FFMPEG_THREADS = PHYSICAL_CORES  # FFmpeg 스레드 수

# 메모리 최적화
CACHE_SIZE = 2048  # MB
BUFFER_SIZE = 4096  # KB

# FFmpeg 최적화 설정
FFMPEG_OPTIMIZATION = {
    # CPU 최적화
    'threads': str(FFMPEG_THREADS),
    'thread_type': 'slice',  # 병렬 처리 최적화
    
    # x264 CPU 최적화 옵션
    'x264_params': [
        'threads=6',
        'lookahead_threads=2',
        'sliced_threads=0',
        'nr=0',  # noise reduction 비활성화로 속도 향상
        'me=dia',  # 빠른 motion estimation
        'subme=1',  # 빠른 subpixel motion estimation
        'trellis=0',  # trellis 비활성화
        'ref=1',  # reference frame 감소
        'mixed_ref=0',
        'me_range=16',
        'chroma_me=0',
        'b_adapt=0',
        'rc_lookahead=20',
        'weightp=0',
        'weightb=0',
        'scenecut=0',
        'mbtree=0'
    ]
}

# 환경 변수 설정
os.environ['FFMPEG_THREADS'] = str(FFMPEG_THREADS)
os.environ['OMP_NUM_THREADS'] = str(PHYSICAL_CORES)
os.environ['MKL_NUM_THREADS'] = str(PHYSICAL_CORES)

# Proxmox 환경 최적화
PROXMOX_OPTIMIZATIONS = {
    'nice_level': 10,  # 낮은 우선순위로 시스템 영향 최소화
    'ionice_class': 2,  # Best effort I/O
    'ionice_level': 5
}