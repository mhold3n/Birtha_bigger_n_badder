# Health check script for Birtha + WrkHrs AI stack (PowerShell)
# Checks all services and provides status summary

param(
    [switch]$Quiet
)

# Service URLs
$API_URL = "http://localhost:8080"
$ROUTER_URL = "http://localhost:8000"
$GATEWAY_URL = "http://localhost:8080"
$MLFLOW_URL = "http://localhost:5000"
$GRAFANA_URL = "http://localhost:3000"
$PROMETHEUS_URL = "http://localhost:9090"
$QDRANT_URL = "http://localhost:6333"

# Function to check service health
function Test-ServiceHealth {
    param(
        [string]$Name,
        [string]$Url,
        [string]$Endpoint = "/health"
    )
    
    if (-not $Quiet) {
        Write-Host "Checking $Name... " -NoNewline
    }
    
    try {
        $response = Invoke-WebRequest -Uri "$Url$Endpoint" -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -eq 200) {
            if (-not $Quiet) {
                Write-Host "✓ Healthy" -ForegroundColor Green
            }
            return $true
        }
    }
    catch {
        if (-not $Quiet) {
            Write-Host "✗ Unhealthy" -ForegroundColor Red
        }
        return $false
    }
    
    return $false
}

# Function to check Docker service
function Test-DockerService {
    param(
        [string]$Name
    )
    
    if (-not $Quiet) {
        Write-Host "Checking Docker service $Name... " -NoNewline
    }
    
    try {
        $containers = docker ps --format "table {{.Names}}" 2>$null
        if ($containers -match "^$Name$") {
            if (-not $Quiet) {
                Write-Host "✓ Running" -ForegroundColor Green
            }
            return $true
        }
    }
    catch {
        if (-not $Quiet) {
            Write-Host "✗ Not running" -ForegroundColor Red
        }
        return $false
    }
    
    if (-not $Quiet) {
        Write-Host "✗ Not running" -ForegroundColor Red
    }
    return $false
}

if (-not $Quiet) {
    Write-Host "=== Birtha + WrkHrs AI Stack Health Check ===" -ForegroundColor Blue
    Write-Host ""
}

$totalServices = 0
$healthyServices = 0

# Core Birtha services
if (-not $Quiet) {
    Write-Host "Core Birtha Services:" -ForegroundColor Yellow
}
$coreServices = @("API", "Router", "queue", "prometheus", "grafana", "qdrant")
foreach ($service in $coreServices) {
    $totalServices++
    if ($service -eq "API" -or $service -eq "Router") {
        $url = if ($service -eq "API") { $API_URL } else { $ROUTER_URL }
        if (Test-ServiceHealth -Name $service -Url $url) {
            $healthyServices++
        }
    } else {
        if (Test-DockerService -Name $service) {
            $healthyServices++
        }
    }
}

if (-not $Quiet) {
    Write-Host ""
}

# WrkHrs AI services
if (-not $Quiet) {
    Write-Host "WrkHrs AI Services:" -ForegroundColor Yellow
}
$aiServices = @("wrkhrs-gateway", "wrkhrs-orchestrator", "wrkhrs-rag", "wrkhrs-asr", "wrkhrs-tool-registry", "wrkhrs-mcp")
foreach ($service in $aiServices) {
    $totalServices++
    if (Test-DockerService -Name $service) {
        $healthyServices++
    }
}

if (-not $Quiet) {
    Write-Host ""
}

# Platform services
if (-not $Quiet) {
    Write-Host "Platform Services:" -ForegroundColor Yellow
}
$platformServices = @("postgres", "minio", "loki", "tempo", "jaeger")
foreach ($service in $platformServices) {
    $totalServices++
    if (Test-DockerService -Name $service) {
        $healthyServices++
    }
}

# Check MLflow separately
$totalServices++
if (Test-ServiceHealth -Name "MLflow" -Url $MLFLOW_URL) {
    $healthyServices++
}

if (-not $Quiet) {
    Write-Host ""
}

# MCP servers
if (-not $Quiet) {
    Write-Host "MCP Servers:" -ForegroundColor Yellow
}
$mcpServices = @("mcp-github", "mcp-filesystem", "mcp-secrets", "mcp-vector-db")
foreach ($service in $mcpServices) {
    $totalServices++
    if (Test-DockerService -Name $service) {
        $healthyServices++
    }
}

if (-not $Quiet) {
    Write-Host ""
}

# Worker services (if running)
if (-not $Quiet) {
    Write-Host "Worker Services (GPU):" -ForegroundColor Yellow
}
try {
    $workerContainers = docker ps --format "table {{.Names}}" 2>$null
    if ($workerContainers -match "llm-runner") {
        $totalServices++
        if (Test-DockerService -Name "llm-runner") {
            $healthyServices++
        }
    } else {
        if (-not $Quiet) {
            Write-Host "Worker services not running (expected if not on GPU workstation)" -ForegroundColor Yellow
        }
    }
}
catch {
    if (-not $Quiet) {
        Write-Host "Worker services not running (expected if not on GPU workstation)" -ForegroundColor Yellow
    }
}

if (-not $Quiet) {
    Write-Host ""
}

# Summary
if (-not $Quiet) {
    Write-Host "=== Health Check Summary ===" -ForegroundColor Blue
    Write-Host "Healthy services: $healthyServices/$totalServices"
}

if ($healthyServices -eq $totalServices) {
    if (-not $Quiet) {
        Write-Host "All services are healthy! 🎉" -ForegroundColor Green
    }
    exit 0
}
elseif ($healthyServices -gt ($totalServices / 2)) {
    if (-not $Quiet) {
        Write-Host "Most services are healthy, but some issues detected." -ForegroundColor Yellow
    }
    exit 1
}
else {
    if (-not $Quiet) {
        Write-Host "Multiple services are unhealthy. Check logs for details." -ForegroundColor Red
    }
    exit 2
}











