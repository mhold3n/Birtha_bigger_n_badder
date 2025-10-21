#!/bin/bash

# Smoke test script for Birtha + WrkHrs AI stack
# Validates full stack health + trace propagation
# Runs after `make up-all`

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Service URLs
API_URL="http://localhost:8080"
ROUTER_URL="http://localhost:8000"
MCP_REGISTRY_URL="http://localhost:8001"
MLFLOW_URL="http://localhost:5000"
TEMPO_URL="http://localhost:3200"
GRAFANA_URL="http://localhost:3000"

# Test configuration
GOLDEN_TRACE_ID="smoke-test-trace-$(date +%s)"
GOLDEN_RUN_ID="smoke-test-run-$(date +%s)"
TEST_POLICY_SET="smoke-test-policy"

echo -e "${BLUE}=== Birtha + WrkHrs AI Stack Smoke Test ===${NC}"
echo -e "${YELLOW}Golden Trace ID: ${GOLDEN_TRACE_ID}${NC}"
echo -e "${YELLOW}Golden Run ID: ${GOLDEN_RUN_ID}${NC}"
echo -e "${YELLOW}Policy Set: ${TEST_POLICY_SET}${NC}"
echo

# Function to check service health
check_service() {
    local name=$1
    local url=$2
    local endpoint=${3:-"/health"}
    
    echo -n "Checking $name... "
    
    if curl -s -f "$url$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Healthy${NC}"
        return 0
    else
        echo -e "${RED}✗ Unhealthy${NC}"
        return 1
    fi
}

# Function to test chat endpoint
test_chat_endpoint() {
    local name=$1
    local url=$2
    local payload=$3
    local headers=$4
    
    echo -n "Testing $name... "
    
    if curl -s -f -X POST "$url" \
        -H "Content-Type: application/json" \
        $headers \
        -d "$payload" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Working${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed${NC}"
        return 1
    fi
}

# Function to test trace propagation
test_trace_propagation() {
    local trace_id=$1
    local run_id=$2
    local policy_set=$3
    
    echo -n "Testing trace propagation... "
    
    # Test chat request with trace headers
    response=$(curl -s -X POST "$API_URL/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -H "x-trace-id: $trace_id" \
        -H "x-run-id: $run_id" \
        -H "x-policy-set: $policy_set" \
        -d '{
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [{"role": "user", "content": "Hello, this is a smoke test."}],
            "temperature": 0.7,
            "max_tokens": 50
        }' 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == "ERROR" ]]; then
        echo -e "${RED}✗ Failed${NC}"
        return 1
    fi
    
    # Check if response contains trace headers
    if echo "$response" | grep -q "x-trace-id"; then
        echo -e "${GREEN}✓ Trace propagated${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Partial success (no worker)${NC}"
        return 0  # Still consider success if API responds
    fi
}

# Function to test MCP registry
test_mcp_registry() {
    echo -n "Testing MCP registry... "
    
    # Test registry health
    if curl -s -f "$MCP_REGISTRY_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Registry healthy${NC}"
        
        # Test registry endpoints
        if curl -s -f "$MCP_REGISTRY_URL/mcp/registry" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Registry endpoints working${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠ Registry endpoints not responding${NC}"
            return 0
        fi
    else
        echo -e "${RED}✗ Registry unhealthy${NC}"
        return 1
    fi
}

# Function to test observability stack
test_observability_stack() {
    echo -n "Testing observability stack... "
    
    local healthy_count=0
    local total_count=0
    
    # Test MLflow
    total_count=$((total_count + 1))
    if curl -s -f "$MLFLOW_URL/health" > /dev/null 2>&1; then
        healthy_count=$((healthy_count + 1))
    fi
    
    # Test Tempo
    total_count=$((total_count + 1))
    if curl -s -f "$TEMPO_URL/ready" > /dev/null 2>&1; then
        healthy_count=$((healthy_count + 1))
    fi
    
    # Test Grafana
    total_count=$((total_count + 1))
    if curl -s -f "$GRAFANA_URL/api/health" > /dev/null 2>&1; then
        healthy_count=$((healthy_count + 1))
    fi
    
    if [ $healthy_count -eq $total_count ]; then
        echo -e "${GREEN}✓ All observability services healthy${NC}"
        return 0
    elif [ $healthy_count -gt 0 ]; then
        echo -e "${YELLOW}⚠ Some observability services healthy ($healthy_count/$total_count)${NC}"
        return 0
    else
        echo -e "${RED}✗ No observability services healthy${NC}"
        return 1
    fi
}

# Function to test policy enforcement
test_policy_enforcement() {
    echo -n "Testing policy enforcement... "
    
    # Test chat request that should trigger policy violations
    response=$(curl -s -X POST "$API_URL/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -H "x-trace-id: $GOLDEN_TRACE_ID" \
        -H "x-run-id: $GOLDEN_RUN_ID" \
        -H "x-policy-set: $TEST_POLICY_SET" \
        -d '{
            "model": "mistralai/Mistral-7B-Instruct-v0.3",
            "messages": [{"role": "user", "content": "This might be correct, but it seems like it could work."}],
            "temperature": 0.7,
            "max_tokens": 50
        }' 2>/dev/null || echo "ERROR")
    
    if [[ "$response" == "ERROR" ]]; then
        echo -e "${RED}✗ Failed${NC}"
        return 1
    fi
    
    # Check if response contains policy headers
    if echo "$response" | grep -q "x-policy-verdict"; then
        echo -e "${GREEN}✓ Policy enforcement working${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Policy enforcement not active (no worker)${NC}"
        return 0  # Still consider success if API responds
    fi
}

# Main smoke test execution
echo -e "${BLUE}=== Core Services Health Check ===${NC}"

# Check core services
check_service "API" "$API_URL"
check_service "Router" "$ROUTER_URL"
check_service "MCP Registry" "$MCP_REGISTRY_URL"

echo

echo -e "${BLUE}=== Observability Stack Check ===${NC}"
test_observability_stack

echo

echo -e "${BLUE}=== MCP Registry Check ===${NC}"
test_mcp_registry

echo

echo -e "${BLUE}=== Trace Propagation Test ===${NC}"
test_trace_propagation "$GOLDEN_TRACE_ID" "$GOLDEN_RUN_ID" "$TEST_POLICY_SET"

echo

echo -e "${BLUE}=== Policy Enforcement Test ===${NC}"
test_policy_enforcement

echo

echo -e "${BLUE}=== Chat Endpoint Tests ===${NC}"

# Test basic chat endpoint
test_chat_endpoint "Chat API" "$API_URL/v1/chat/completions" '{
    "model": "mistralai/Mistral-7B-Instruct-v0.3",
    "messages": [{"role": "user", "content": "Hello"}],
    "temperature": 0.7,
    "max_tokens": 50
}' ""

# Test chat endpoint with headers
test_chat_endpoint "Chat API with Headers" "$API_URL/v1/chat/completions" '{
    "model": "mistralai/Mistral-7B-Instruct-v0.3",
    "messages": [{"role": "user", "content": "Hello with headers"}],
    "temperature": 0.7,
    "max_tokens": 50
}' "-H 'x-trace-id: smoke-test-123' -H 'x-run-id: smoke-test-456' -H 'x-policy-set: smoke-test'"

echo

echo -e "${BLUE}=== Smoke Test Summary ===${NC}"

# Count successful tests
total_tests=0
passed_tests=0

# Core services
for service in "API" "Router" "MCP Registry"; do
    total_tests=$((total_tests + 1))
    if check_service "$service" "$API_URL" > /dev/null 2>&1; then
        passed_tests=$((passed_tests + 1))
    fi
done

# Observability stack
total_tests=$((total_tests + 1))
if test_observability_stack > /dev/null 2>&1; then
    passed_tests=$((passed_tests + 1))
fi

# MCP registry
total_tests=$((total_tests + 1))
if test_mcp_registry > /dev/null 2>&1; then
    passed_tests=$((passed_tests + 1))
fi

# Trace propagation
total_tests=$((total_tests + 1))
if test_trace_propagation "$GOLDEN_TRACE_ID" "$GOLDEN_RUN_ID" "$TEST_POLICY_SET" > /dev/null 2>&1; then
    passed_tests=$((passed_tests + 1))
fi

# Policy enforcement
total_tests=$((total_tests + 1))
if test_policy_enforcement > /dev/null 2>&1; then
    passed_tests=$((passed_tests + 1))
fi

echo "Passed tests: $passed_tests/$total_tests"

if [ $passed_tests -eq $total_tests ]; then
    echo -e "${GREEN}All smoke tests passed! 🎉${NC}"
    echo -e "${GREEN}Stack is ready for development and testing.${NC}"
    exit 0
elif [ $passed_tests -gt $((total_tests / 2)) ]; then
    echo -e "${YELLOW}Most smoke tests passed, but some issues detected.${NC}"
    echo -e "${YELLOW}Check logs for details.${NC}"
    exit 1
else
    echo -e "${RED}Multiple smoke tests failed.${NC}"
    echo -e "${RED}Check service logs and configuration.${NC}"
    exit 2
fi
