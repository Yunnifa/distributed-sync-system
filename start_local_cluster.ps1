# Script untuk menjalankan semua 3 nodes sekaligus
# Akan membuka 3 PowerShell windows terpisah

Write-Host "Starting 3-node local cluster..." -ForegroundColor Green
Write-Host "This will open 3 new PowerShell windows" -ForegroundColor Yellow
Write-Host ""

# Get the current directory
$scriptPath = $PSScriptRoot
if (-not $scriptPath) {
    $scriptPath = Get-Location
}

# Start Node 1 in new window
Write-Host "Starting Node 1 on port 8001..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath'; .\.venv\Scripts\Activate.ps1; .\run_node1.ps1"

# Wait a bit before starting next node
Start-Sleep -Seconds 2

# Start Node 2 in new window
Write-Host "Starting Node 2 on port 8002..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath'; .\.venv\Scripts\Activate.ps1; .\run_node2.ps1"

# Wait a bit before starting next node
Start-Sleep -Seconds 2

# Start Node 3 in new window
Write-Host "Starting Node 3 on port 8003..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$scriptPath'; .\.venv\Scripts\Activate.ps1; .\run_node3.ps1"

Write-Host ""
Write-Host "All 3 nodes starting..." -ForegroundColor Green
Write-Host ""
Write-Host "Waiting 15 seconds for Raft leader election..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host ""
Write-Host "Testing cluster..." -ForegroundColor Green

# Test health
Write-Host "Testing Node 1 health..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/" -UseBasicParsing
    Write-Host "Node 1 is responding" -ForegroundColor Green
}
catch {
    Write-Host "Node 1 not responding" -ForegroundColor Red
}

# Test leader status
Write-Host "Checking Raft leader status..." -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8001/locks" -UseBasicParsing
    $data = $response.Content | ConvertFrom-Json
    if ($data.is_leader) {
        Write-Host "Node 1 is LEADER" -ForegroundColor Green
    }
    else {
        Write-Host "Node 1 is FOLLOWER" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Could not determine leader status" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "You can now test distributed locks:" -ForegroundColor Green
Write-Host "  Invoke-WebRequest -Uri 'http://localhost:8001/lock/mylock?lock_type=exclusive' -Method POST" -ForegroundColor White
Write-Host "  curl http://localhost:8001/locks" -ForegroundColor White
Write-Host ""
Write-Host "Or run automated tests:" -ForegroundColor Green
Write-Host "  python test_deadlock.py" -ForegroundColor White
Write-Host "  python test_system.py" -ForegroundColor White
Write-Host ""
Write-Host "To stop all nodes, close the 3 PowerShell windows" -ForegroundColor Yellow
