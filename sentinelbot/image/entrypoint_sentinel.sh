#!/bin/bash
set -e

echo ""
echo "🛡️  SentinelBot is starting..."
echo "   API:    http://localhost:8502/docs"
echo ""

exec python -m uvicorn sentinel.sentinel_server:app \
    --host 0.0.0.0 \
    --port 8502 \
    --log-level info
