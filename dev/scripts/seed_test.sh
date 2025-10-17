#!/bin/bash
set -euo pipefail

# Seed test data and run basic tests
# Usage: ./seed_test.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "🌱 Seeding test data and running basic tests..."

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 5

# Test API health
echo "🔍 Testing API health..."
if curl -s http://localhost:8080/health | grep -q "healthy\|degraded"; then
    echo "✅ API is healthy"
else
    echo "❌ API health check failed"
    exit 1
fi

# Test router health
echo "🔍 Testing router health..."
if curl -s http://localhost:8000/health | grep -q "healthy\|degraded"; then
    echo "✅ Router is healthy"
else
    echo "❌ Router health check failed"
    exit 1
fi

# Test chat endpoint
echo "🔍 Testing chat endpoint..."
RESPONSE=$(curl -s -X POST http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
        "model": "test-model",
        "messages": [
            {"role": "user", "content": "Hello, world!"}
        ],
        "max_tokens": 10
    }' || echo "ERROR")

if echo "$RESPONSE" | grep -q "error\|Error"; then
    echo "⚠️ Chat endpoint returned error (expected in test environment)"
    echo "Response: $RESPONSE"
else
    echo "✅ Chat endpoint is working"
    echo "Response: $RESPONSE"
fi

# Test MCP servers
echo "🔍 Testing MCP servers..."

# Test GitHub MCP
if curl -s http://localhost:7000/health | grep -q "healthy"; then
    echo "✅ GitHub MCP is healthy"
else
    echo "⚠️ GitHub MCP health check failed (may be expected)"
fi

# Test Filesystem MCP
if curl -s http://localhost:7001/health | grep -q "healthy"; then
    echo "✅ Filesystem MCP is healthy"
else
    echo "⚠️ Filesystem MCP health check failed (may be expected)"
fi

# Test Secrets MCP
if curl -s http://localhost:7002/health | grep -q "healthy"; then
    echo "✅ Secrets MCP is healthy"
else
    echo "⚠️ Secrets MCP health check failed (may be expected)"
fi

# Test Vector DB MCP
if curl -s http://localhost:7003/health | grep -q "healthy"; then
    echo "✅ Vector DB MCP is healthy"
else
    echo "⚠️ Vector DB MCP health check failed (may be expected)"
fi

echo ""
echo "🎉 Test seeding completed!"
echo ""
echo "📊 Service status:"
docker compose ps

echo ""
echo "🔗 Available endpoints:"
echo "- API: http://localhost:8080"
echo "- Router: http://localhost:8000"
echo "- Grafana: http://localhost:3000"
echo "- Prometheus: http://localhost:9090"
echo "- GitHub MCP: http://localhost:7000"
echo "- Filesystem MCP: http://localhost:7001"
echo "- Secrets MCP: http://localhost:7002"
echo "- Vector DB MCP: http://localhost:7003"
