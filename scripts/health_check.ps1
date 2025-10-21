# Health check script for Birtha + WrkHrs AI stack (PowerShell)
# Checks all services and provides status summary

param(
    [switch]$Verbose
)

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"
$White = "White"

# Service URLs
$API_URL = "http://localhost:8080"
$ROUTER_URL = "http://localhost:8000"
$GATEWAY_URL = "http://localhost:8080"
$MLFLOW_URL = "http://localhost:5000"
$GRAFANA_URL = "http://localhost:3000"
$PROMETHEUS_URL = "http://localhost:9090"
$QDRANT_URL = "http://localhost:6333"
$MCP_REGISTRY_URL = "http://localhost:8001"
$TEMPO_URL = "http://localhost:3200"
$LOKI_URL = "http://localhost:3100"

# Function to check service health
function Test-ServiceHealth {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Endpoint = "/health"
    )
    
    Write-Host "Checking $Name... " -NoNewline
    
    try {
        $response = Invoke-WebRequest -Uri "$Url$Endpoint" -Method GET -TimeoutSec 10 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ Healthy" -ForegroundColor $Green
            return $true
        } else {
            Write-Host "✗ Unhealthy (Status: $($response.StatusCode))" -ForegroundColor $Red
            return $false
        }
    } catch {
        Write-Host "✗ Unhealthy (Error: $($_.Exception.Message))" -ForegroundColor $Red
        return $false
    }
}

# Function to check Docker service
function Test-DockerService {
    param(
        [string]$Name
    )
    
    Write-Host "Checking Docker service $Name... " -NoNewline
    
    try {
        $containers = docker ps --format "table {{.Names}}" | Select-String "^${Name}$"
        if ($containers) {
            Write-Host "✓ Running" -ForegroundColor $Green
            return $true
        } else {
            Write-Host "✗ Not running" -ForegroundColor $Red
            return $false
        }
    } catch {
        Write-Host "✗ Error checking Docker" -ForegroundColor $Red
        return $false
    }
}

Write-Host "=== Birtha + WrkHrs AI Stack Health Check ===" -ForegroundColor $Blue
Write-Host ""

# Core Birtha services
Write-Host "Core Birtha Services:" -ForegroundColor $Yellow
$coreServices = @()
$coreServices += Test-ServiceHealth "API" $API_URL
$coreServices += Test-ServiceHealth "Router" $ROUTER_URL
$coreServices += Test-DockerService "queue"
$coreServices += Test-DockerService "prometheus"
$coreServices += Test-DockerService "grafana"
$coreServices += Test-DockerService "qdrant"

Write-Host ""

# WrkHrs AI services
Write-Host "WrkHrs AI Services:" -ForegroundColor $Yellow
$aiServices = @()
$aiServices += Test-DockerService "wrkhrs-gateway"
$aiServices += Test-DockerService "wrkhrs-orchestrator"
$aiServices += Test-DockerService "wrkhrs-rag"
$aiServices += Test-DockerService "wrkhrs-asr"
$aiServices += Test-DockerService "wrkhrs-tool-registry"
$aiServices += Test-DockerService "wrkhrs-mcp"

Write-Host ""

# Platform services
Write-Host "Platform Services:" -ForegroundColor $Yellow
$platformServices = @()
$platformServices += Test-ServiceHealth "MLflow" $MLFLOW_URL
$platformServices += Test-ServiceHealth "MCP Registry" $MCP_REGISTRY_URL
$platformServices += Test-ServiceHealth "Tempo" $TEMPO_URL
$platformServices += Test-ServiceHealth "Loki" $LOKI_URL
$platformServices += Test-DockerService "postgres"
$platformServices += Test-DockerService "minio"
$platformServices += Test-DockerService "loki"
$platformServices += Test-DockerService "tempo"
$platformServices += Test-DockerService "jaeger"

Write-Host ""

# MCP servers
Write-Host "MCP Servers:" -ForegroundColor $Yellow
$mcpServices = @()
$mcpServices += Test-DockerService "mcp-github"
$mcpServices += Test-DockerService "mcp-filesystem"
$mcpServices += Test-DockerService "mcp-secrets"
$mcpServices += Test-DockerService "mcp-vector-db"

Write-Host ""

# Worker services (if running)
Write-Host "Worker Services (GPU):" -ForegroundColor $Yellow
$workerServices = @()
try {
    $llmRunner = docker ps --format "table {{.Names}}" | Select-String "llm-runner"
    if ($llmRunner) {
        $workerServices += Test-DockerService "llm-runner"
    } else {
        Write-Host "Worker services not running (expected if not on GPU workstation)" -ForegroundColor $Yellow
    }
} catch {
    Write-Host "Worker services not running (expected if not on GPU workstation)" -ForegroundColor $Yellow
}

Write-Host ""

# Summary
Write-Host "=== Health Check Summary ===" -ForegroundColor $Blue

# Count healthy services
$allServices = $coreServices + $aiServices + $platformServices + $mcpServices + $workerServices
$totalServices = $allServices.Count
$healthyServices = ($allServices | Where-Object { $_ -eq $true }).Count

Write-Host "Healthy services: $healthyServices/$totalServices"

if ($healthyServices -eq $totalServices) {
    Write-Host "All services are healthy! 🎉" -ForegroundColor $Green
    exit 0
} elseif ($healthyServices -gt ($totalServices / 2)) {
    Write-Host "Most services are healthy, but some issues detected." -ForegroundColor $Yellow
    exit 1
} else {
    Write-Host "Multiple services are unhealthy. Check logs for details." -ForegroundColor $Red
    exit 2
}