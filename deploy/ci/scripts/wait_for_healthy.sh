#!/bin/bash
set -euo pipefail

# Wait for service to be healthy
# Usage: ./wait_for_healthy.sh <service> <port> <timeout_seconds>

SERVICE=${1:-api}
PORT=${2:-8080}
TIMEOUT=${3:-60}
INTERVAL=2

echo "⏳ Waiting for $SERVICE to be healthy on port $PORT (timeout: ${TIMEOUT}s)..."

start_time=$(date +%s)
end_time=$((start_time + TIMEOUT))

while [ $(date +%s) -lt $end_time ]; do
    if curl -sSf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
        echo "✅ $SERVICE is healthy!"
        exit 0
    fi
    
    echo "⏳ $SERVICE not ready yet, waiting ${INTERVAL}s..."
    sleep $INTERVAL
done

echo "❌ $SERVICE failed to become healthy within ${TIMEOUT}s"
exit 1
