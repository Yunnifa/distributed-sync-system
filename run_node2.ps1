# Script untuk menjalankan Node 2
# Jalankan di Terminal/PowerShell window kedua

Write-Host "Starting Node 2..." -ForegroundColor Green

# Set environment variables - use 127.0.0.1 instead of localhost
$env:PORT = "8002"
$env:NODE_ID = "node2"
$env:ALL_NODES = "http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"

# Run the application
python -m src.main
