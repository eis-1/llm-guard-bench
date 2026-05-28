# ============================================================================
# LLM Guard Bench: Docker Validation & Execution Script
# ============================================================================
# Purpose: Clean startup, schema validation, benchmark execution, result count
# Usage: .\validate_and_run.ps1
# ============================================================================

param(
    [string]$TargetModel = "llama3.2:3b",
    [int]$Concurrency = 2,
    [string[]]$Categories = @("DAN"),
    [switch]$Clean = $false,
    [switch]$Verbose = $false
)

# ============================================================================
# Configuration
# ============================================================================
$ProjectRoot = "c:\projects\Best\llm-guard-bench"
$ResultsDir = "$ProjectRoot\llm-guard-bench\results"
$DbPath = "$ResultsDir\guard_bench.db"

# ============================================================================
# Logging Functions
# ============================================================================
function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 80) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 80) -ForegroundColor Cyan
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "[✓] $Message" -ForegroundColor Green
}

function Write-Error_ {
    param([string]$Message)
    Write-Host "[✗] $Message" -ForegroundColor Red
}

function Write-Warning_ {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Info {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Cyan
}

# ============================================================================
# Step 1: Pre-flight Checks
# ============================================================================
Write-Header "PRE-FLIGHT CHECKS"

# Check Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error_ "Docker not found. Install Docker Desktop first."
    exit 1
}
Write-Success "Docker CLI available"

# Check Docker Compose
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Error_ "Docker Compose not found. Install Docker Desktop first."
    exit 1
}
Write-Success "Docker Compose available"

# Check Docker daemon
try {
    docker ps > $null 2>&1
    Write-Success "Docker daemon running"
}
catch {
    Write-Error_ "Docker daemon not running. Start Docker Desktop."
    exit 1
}

# ============================================================================
# Step 2: Database Cleanup (if requested)
# ============================================================================
if ($Clean) {
    Write-Header "CLEANING OLD DATA"
    
    if (Test-Path $DbPath) {
        Remove-Item $DbPath -Force
        Write-Success "Removed old database: $DbPath"
    }
    
    $BackupPath = "$DbPath.backup"
    if (Test-Path $BackupPath) {
        Remove-Item $BackupPath -Force
        Write-Success "Removed database backup: $BackupPath"
    }
    
    $JsonlFiles = Get-ChildItem "$ResultsDir\session_*.jsonl" -ErrorAction SilentlyContinue
    if ($JsonlFiles) {
        Remove-Item $JsonlFiles -Force
        Write-Success "Removed session JSONL files"
    }
}
else {
    Write-Header "INCREMENTAL MODE"
    Write-Info "Using existing database (if present)"
    Write-Info "To clean: .\validate_and_run.ps1 -Clean"
}

# ============================================================================
# Step 3: Docker Build & Start
# ============================================================================
Write-Header "DOCKER BUILD & START"

Set-Location $ProjectRoot

# Build fresh image
Write-Info "Building Docker image (this may take a minute on first run)..."
$buildOutput = docker compose build --no-cache 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error_ "Docker build failed"
    Write-Host $buildOutput
    exit 1
}
Write-Success "Docker image built successfully"

# Start container
Write-Info "Starting container..."
docker compose up -d --build 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Error_ "Failed to start container"
    exit 1
}

# Wait for container to be ready
Write-Info "Waiting for container to stabilize (5 seconds)..."
Start-Sleep -Seconds 5

$ContainerStatus = docker compose ps --services --filter "status=running" 2>&1
if ($ContainerStatus -notcontains "llm-guard-bench") {
    Write-Error_ "Container failed to start. Check logs:"
    docker compose logs llm-guard-bench
    exit 1
}
Write-Success "Container running"

# ============================================================================
# Step 4: Schema Validation
# ============================================================================
Write-Header "DATABASE SCHEMA VALIDATION"

Write-Info "Checking database tables..."
$tableCheckCmd = @"
import sqlite3
try:
    conn = sqlite3.connect('/app/results/guard_bench.db')
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    print('Tables:', ','.join(tables))
    conn.close()
except Exception as e:
    print('ERROR:', str(e))
"@

$tableOutput = docker compose run --rm llm-guard-bench python -c $tableCheckCmd 2>&1 | Select-String "Tables:"

if (-not $tableOutput) {
    Write-Error_ "Database not initialized. Forcing initialization..."
    
    # Force migrations
    $initCmd = @"
import asyncio
from db.db import DatabaseManager

async def init():
    db = DatabaseManager()
    await db.initialize()

asyncio.run(init())
"@
    docker compose run --rm llm-guard-bench python -c $initCmd 2>&1 | Out-Null
    
    Start-Sleep -Seconds 2
    $tableOutput = docker compose run --rm llm-guard-bench python -c $tableCheckCmd 2>&1 | Select-String "Tables:"
}

Write-Success "Schema check: $tableOutput"

# Verify required tables
if ($tableOutput -match "test_results.*sessions.*attack_definitions") {
    Write-Success "All required v3.0 tables present"
}
else {
    Write-Error_ "Schema validation FAILED. Missing required tables."
    Write-Host $tableOutput
    docker compose down
    exit 1
}

# ============================================================================
# Step 5: Ollama Connectivity Check
# ============================================================================
Write-Header "OLLAMA CONNECTIVITY TEST"

$ollamaTest = docker compose exec -T llm-guard-bench curl -s http://host.docker.internal:11434 2>&1
if ($LASTEXITCODE -eq 0 -and $ollamaTest -match "Ollama") {
    Write-Success "Container can reach Ollama on host"
}
else {
    Write-Warning_ "Ollama connectivity check inconclusive (may be offline)"
    Write-Info "Ensure Ollama is running: ollama serve"
    Write-Info "Pull model: ollama pull $TargetModel"
}

# ============================================================================
# Step 6: Run Benchmark
# ============================================================================
Write-Header "BENCHMARK EXECUTION"

Write-Info "Target Model: $TargetModel"
Write-Info "Concurrency: $Concurrency"
Write-Info "Categories: $($Categories -join ', ')"
Write-Info ""
Write-Info "Running benchmark... (this may take several minutes)"

$benchmarkCmd = "python main.py run --models $TargetModel --concurrency $Concurrency --categories $($Categories -join ' ')"

if ($Verbose) {
    Write-Info "Command: $benchmarkCmd"
}

$benchmarkOutput = docker compose run --rm llm-guard-bench $benchmarkCmd 2>&1

Write-Host $benchmarkOutput

if ($LASTEXITCODE -ne 0) {
    Write-Error_ "Benchmark execution failed"
    exit 1
}

# ============================================================================
# Step 7: Result Validation & Row Count
# ============================================================================
Write-Header "RESULT VALIDATION & ROW COUNT"

Start-Sleep -Seconds 2

$rowCountCmd = @"
import sqlite3
try:
    conn = sqlite3.connect('/app/results/guard_bench.db')
    cur = conn.cursor()
    
    # Total rows
    cur.execute('SELECT COUNT(*) FROM test_results')
    total = cur.fetchone()[0]
    
    # Breakdown by status
    cur.execute('''
        SELECT evaluation_status, COUNT(*) 
        FROM test_results 
        GROUP BY evaluation_status 
        ORDER BY evaluation_status
    ''')
    breakdown = cur.fetchall()
    
    print(f'TOTAL_ROWS: {total}')
    for status, count in breakdown:
        print(f'{status}: {count}')
    
    conn.close()
except Exception as e:
    print(f'ERROR: {str(e)}')
"@

$rowOutput = docker compose run --rm llm-guard-bench python -c $rowCountCmd 2>&1

$totalLine = $rowOutput | Select-String "TOTAL_ROWS:"
if ($totalLine) {
    $total = [int]($totalLine -split ":" | Select-Object -Last 1).Trim()
    Write-Success "Database results persisted successfully!"
    Write-Host ""
    Write-Host "Row Count Summary:" -ForegroundColor Cyan
    Write-Host "─────────────────────" -ForegroundColor Cyan
    Write-Host $rowOutput
}
else {
    Write-Error_ "Failed to retrieve row count"
    Write-Host $rowOutput
}

# ============================================================================
# Step 8: Results on Host
# ============================================================================
Write-Header "RESULTS ON HOST MACHINE"

if (Test-Path $DbPath) {
    $dbSize = (Get-Item $DbPath).Length / 1KB
    Write-Success "Database file: $DbPath ($([math]::Round($dbSize, 2)) KB)"
}

$jsonlFiles = Get-ChildItem "$ResultsDir\session_*.jsonl" -ErrorAction SilentlyContinue
if ($jsonlFiles) {
    Write-Success "JSONL files created:"
    foreach ($file in $jsonlFiles) {
        $size = $file.Length / 1KB
        Write-Host "  - $($file.Name) ($([math]::Round($size, 2)) KB)"
    }
}

# ============================================================================
# Step 9: Cleanup & Summary
# ============================================================================
Write-Header "EXECUTION COMPLETE"

Write-Success "Benchmark execution finished successfully"
Write-Info "Container status:"
docker compose ps

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  • View logs: docker compose logs -f llm-guard-bench"
Write-Host "  • Interactive shell: docker compose run --rm -it llm-guard-bench /bin/bash"
Write-Host "  • Stop container: docker compose stop"
Write-Host "  • Clean restart: .\validate_and_run.ps1 -Clean"
Write-Host ""

Write-Success "Test complete!"
exit 0
