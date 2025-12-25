# Script untuk menjalankan Node 3
# Jalankan di Terminal/PowerShell window ketiga

Write-Host "Starting Node 3..." -ForegroundColor Green

# Set environment variables - use 127.0.0.1 instead of localhost
$env:PORT = "8003"
$env:NODE_ID = "node3"
$env:ALL_NODES = "http://127.0.0.1:8001,http://127.0.0.1:8002,http://127.0.0.1:8003"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"

# Run the application
python -m src.main
