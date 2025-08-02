#!/bin/bash

# Start the server in background using nohup
echo "Starting server in background..."

# Kill any existing processes on port 8080
lsof -ti:8080 | xargs kill -9 2>/dev/null

# Start with nohup
nohup python -m uvicorn clipping_api:app --host 0.0.0.0 --port 8080 > server.log 2>&1 &

# Save PID
echo $! > server.pid

echo "Server started with PID: $(cat server.pid)"
echo "Check server.log for output"
echo ""
echo "To stop the server: kill $(cat server.pid)"
echo "To check status: curl http://localhost:8080/health"