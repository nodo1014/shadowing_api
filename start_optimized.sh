#!/bin/bash

# AMD 5600G 최적화 시작 스크립트

# CPU 성능 모드 설정 (권한 필요시 주석 처리)
# echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor

# 환경 변수 설정
export MAX_WORKERS=6
export FFMPEG_THREADS=6
export OMP_NUM_THREADS=6
export MKL_NUM_THREADS=6

# Nice 값으로 우선순위 조정 (Proxmox 환경 최적화)
nice -n 10 ionice -c 2 -n 5 /home/kang/.local/bin/gunicorn main:app \
    --workers 6 \
    --threads 2 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8080 \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level info \
    --timeout 300 \
    --graceful-timeout 60 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --worker-tmp-dir /dev/shm