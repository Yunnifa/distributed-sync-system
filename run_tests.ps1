# Quick Test Script - Run All Integration Tests
# Usage: .\run_tests.ps1

Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host "DISTRIBUTED SYNC SYSTEM - INTEGRATION TESTS" -ForegroundColor Cyan
Write-Host "======================================================================`n" -ForegroundColor Cyan

# Check if Docker is running
Write-Host "Checking Docker..." -ForegroundColor Yellow
$dockerRunning = docker ps 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}
Write-Host "✓ Docker is running`n" -ForegroundColor Green

# Check if cluster is running
Write-Host "Checking cluster status..." -ForegroundColor Yellow
cd docker
$services = docker-compose ps --services --filter "status=running"
$runningCount = ($services | Measure-Object -Line).Lines

if ($runningCount -lt 4) {
    Write-Host "Cluster is not fully running. Starting cluster..." -ForegroundColor Yellow
    docker-compose up -d
    
    Write-Host "Waiting 15 seconds for services to start..." -ForegroundColor Yellow
    Start-Sleep -Seconds 15
} else {
    Write-Host "✓ Cluster is already running`n" -ForegroundColor Green
}

cd ..

# Run integration tests
Write-Host "`nRunning integration tests...`n" -ForegroundColor Yellow
python test_system.py

$exitCode = $LASTEXITCODE

# Print final message
if ($exitCode -eq 0) {
    Write-Host "`n======================================================================" -ForegroundColor Green
    Write-Host "ALL TESTS PASSED! 🎉" -ForegroundColor Green
    Write-Host "======================================================================`n" -ForegroundColor Green
} else {
    Write-Host "`n======================================================================" -ForegroundColor Red
    Write-Host "SOME TESTS FAILED ⚠️" -ForegroundColor Red
    Write-Host "======================================================================`n" -ForegroundColor Red
}

exit $exitCode
