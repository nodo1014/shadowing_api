#!/bin/bash

# Production startup script for Video Clipping API

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Create required directories
mkdir -p ${OUTPUT_DIR:-output}
mkdir -p logs

# Check FFmpeg installation
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: FFmpeg is not installed"
    exit 1
fi

# Start with gunicorn for production
echo "Starting Video Clipping API in production mode..."

# Check if gunicorn is in PATH, otherwise use local installation
if command -v gunicorn &> /dev/null; then
    GUNICORN_CMD="gunicorn"
elif [ -f "$HOME/.local/bin/gunicorn" ]; then
    GUNICORN_CMD="$HOME/.local/bin/gunicorn"
else
    echo "Error: gunicorn not found. Please install it with: pip install gunicorn"
    exit 1
fi

# Using gunicorn with uvicorn workers
$GUNICORN_CMD clipping_api:app \
    --workers ${WORKERS:-4} \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind ${HOST:-0.0.0.0}:${PORT:-8080} \
    --access-logfile logs/access.log \
    --error-logfile logs/error.log \
    --log-level ${LOG_LEVEL:-info} \
    --timeout 300 \
    --graceful-timeout 60 \
    --max-requests 1000 \
    --max-requests-jitter 50