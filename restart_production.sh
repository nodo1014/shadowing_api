#!/bin/bash

# Restart production script for Video Clipping API

echo "Restarting Video Clipping API..."

# Stop the API
./stop_production.sh

# Wait a moment
echo "Waiting 2 seconds before starting..."
sleep 2

# Start the API
echo "Starting API..."
./start_production.sh