#!/bin/bash

# Stop production script for Video Clipping API

echo "Stopping Video Clipping API..."

# Find and kill gunicorn processes for clipping_api
pids=$(ps aux | grep -E "gunicorn.*clipping_api:app" | grep -v grep | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "No running API processes found."
    exit 0
fi

echo "Found processes: $pids"
echo "Killing processes..."

# Send SIGTERM for graceful shutdown
for pid in $pids; do
    kill -TERM $pid 2>/dev/null && echo "Sent SIGTERM to process $pid"
done

# Wait a bit for graceful shutdown
sleep 2

# Check if any processes are still running
remaining=$(ps aux | grep -E "gunicorn.*clipping_api:app" | grep -v grep | awk '{print $2}')

if [ ! -z "$remaining" ]; then
    echo "Some processes still running, forcing shutdown..."
    for pid in $remaining; do
        kill -9 $pid 2>/dev/null && echo "Force killed process $pid"
    done
fi

echo "API stopped successfully."