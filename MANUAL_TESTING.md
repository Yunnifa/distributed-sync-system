# Manual Testing Guide - Step by Step

## ✅ Prerequisites Check
Anda sudah install dependencies dengan baik! Sekarang siap untuk testing.

---

## 🚀 Langkah 1: Start Docker Cluster

```powershell
# Masuk ke folder docker
cd C:\Users\USER\distributed-sync-system\docker

# Start semua services
docker-compose up -d

# Check status (tunggu sampai semua healthy)
docker-compose ps
```

**Output yang diharapkan:**
```
NAME             STATUS
docker-node1-1   Up (healthy)
docker-node2-1   Up (healthy)
docker-node3-1   Up (healthy)
docker-redis-1   Up (healthy)
```

**Tunggu 15-20 detik** untuk Raft leader election.

---

## 🔍 Langkah 2: Check Logs untuk Leader Election

```powershell
# Check logs node1
docker-compose logs node1 --tail 30

# Cari baris yang menunjukkan LEADER atau CANDIDATE
# Jika masih CANDIDATE terus, berarti ada masalah networking
```

**Jika melihat "LEADER"** = ✅ Bagus!  
**Jika stuck di "CANDIDATE"** = ⚠️ Raft networking issue (known problem)

---

## 🧪 Langkah 3: Test Basic Health Check

```powershell
# Kembali ke root folder
cd ..

# Test node 1
curl http://localhost:8001/

# Test node 2
curl http://localhost:8002/

# Test node 3
curl http://localhost:8003/
```

**Output yang diharapkan:**
```json
{
  "message": "Hello from Node node1",
  "port": 8001,
  "peers": ["http://node2:8002", "http://node3:8003"]
}
```

---

## 🔒 Langkah 4: Test Distributed Locks

### A. Check Lock Status (untuk lihat leader)
```powershell
curl http://localhost:8001/locks
```

**Output:**
```json
{
  "locks": {},
  "is_leader": true/false,
  "leader": "node1",
  "wait_for_graph": {}
}
```

### B. Acquire Exclusive Lock
```powershell
# PowerShell syntax (gunakan Invoke-WebRequest)
Invoke-WebRequest -Uri "http://localhost:8001/lock/mylock?lock_type=exclusive" -Method POST
```

**Atau gunakan curl dari Git Bash / WSL:**
```bash
curl -X POST "http://localhost:8001/lock/mylock?lock_type=exclusive"
```

**Output jika BERHASIL:**
```json
{
  "status": "lock acquired",
  "lock_name": "mylock",
  "lock_type": "exclusive",
  "owner": "node1"
}
```

**Output jika GAGAL (503):**
```json
{
  "detail": "No Raft leader available"
}
```
→ Ini berarti Raft leader election belum berhasil (known issue)

### C. Check Lock Status
```powershell
curl http://localhost:8001/lock/mylock
```

### D. Release Lock
```powershell
Invoke-WebRequest -Uri "http://localhost:8001/lock/mylock" -Method DELETE
```

---

## 📦 Langkah 5: Test Distributed Queue

### A. Produce Message
```powershell
# PowerShell
$body = '{"order_id": 123, "product": "laptop"}'
Invoke-WebRequest -Uri "http://localhost:8001/queue/orders" -Method POST -Body $body -ContentType "application/json"
```

### B. Consume Message
```powershell
curl http://localhost:8001/queue/orders
```

### C. Acknowledge Message
```powershell
$ackBody = '{"order_id": 123, "product": "laptop"}'
Invoke-WebRequest -Uri "http://localhost:8001/queue/ack/orders:processing" -Method POST -Body $ackBody -ContentType "application/json"
```

---

## 💾 Langkah 6: Test Distributed Cache

### A. Read from Cache (first time = miss)
```powershell
curl http://localhost:8001/cache/item:123
```

**Output:**
```json
{
  "key": "item:123",
  "data": "Ini adalah data untuk item 123",
  "source": "database (cached for future)"
}
```

### B. Read Again (cache hit)
```powershell
curl http://localhost:8001/cache/item:123
```

**Output:**
```json
{
  "key": "item:123",
  "data": "Ini adalah data untuk item 123",
  "source": "cache (LRU)",
  "cache_state": "S"
}
```

### C. Write to Cache
```powershell
$cacheBody = '{"data": "My custom value"}'
Invoke-WebRequest -Uri "http://localhost:8001/cache/item:999" -Method POST -Body $cacheBody -ContentType "application/json"
```

### D. Check Metrics
```powershell
curl http://localhost:8001/metrics
```

**Output:**
```json
{
  "cache_hits": 5,
  "cache_misses": 2,
  "cache_stats": {
    "size": 3,
    "maxsize": 128,
    "states": {
      "item:123": "S",
      "item:999": "M"
    }
  }
}
```

---

## 🛡️ Langkah 7: Test PBFT (Byzantine Fault Tolerance)

### A. Check PBFT Status
```powershell
curl http://localhost:8001/pbft/status
```

**Output:**
```json
{
  "view": 0,
  "sequence": 0,
  "primary": "node1",
  "is_primary": true,
  "f": 0,
  "quorum_size": 1,
  "byzantine_nodes": [],
  "suspicious_nodes": {}
}
```

### B. Submit PBFT Request
```powershell
$pbftBody = '{"operation": "transfer", "from": "Alice", "to": "Bob", "amount": 100}'
Invoke-WebRequest -Uri "http://localhost:8001/pbft/request" -Method POST -Body $pbftBody -ContentType "application/json"
```

### C. Simulate Byzantine Behavior
```powershell
Invoke-WebRequest -Uri "http://localhost:8002/pbft/simulate-byzantine?behavior_type=conflicting_prepare" -Method POST
```

---

## 🧪 Langkah 8: Run Automated Tests

### A. Run Unit Tests
```powershell
# Test Raft
pytest tests/unit/test_raft.py -v

# Test Utils
pytest tests/unit/test_utils.py -v

# Test PBFT
pytest tests/unit/test_pbft.py -v

# Run all unit tests
pytest tests/unit/ -v
```

### B. Run Integration Tests
```powershell
# Make sure cluster is running first!
python test_system.py
```

### C. Run Deadlock Detection Tests
```powershell
python test_deadlock.py
```

---

## 📊 Langkah 9: Run Load Tests (Optional)

```powershell
# Run Locust in headless mode
locust -f benchmarks/load_test_scenarios.py --headless -u 50 -r 5 -t 30s --host http://localhost:8001

# Or with Web UI (open browser to http://localhost:8089)
locust -f benchmarks/load_test_scenarios.py --host http://localhost:8001
```

---

## 🛑 Langkah 10: Stop Cluster

```powershell
cd docker
docker-compose down

# To also remove volumes (Redis data)
docker-compose down -v
```

---

## ⚠️ Known Issues & Troubleshooting

### Issue 1: Lock Returns 503 "No Raft leader available"

**Penyebab:** Raft leader election gagal karena Docker networking

**Solusi:**
1. Check logs: `docker-compose logs node1 --tail 50`
2. Jika stuck di CANDIDATE, coba restart: `docker-compose restart`
3. Atau run lokal tanpa Docker (lihat TESTING_GUIDE.md)

### Issue 2: "Connection refused" saat curl

**Solusi:**
```powershell
# Check apakah containers running
docker-compose ps

# Check logs untuk error
docker-compose logs
```

### Issue 3: Redis connection error

**Solusi:**
```powershell
# Restart Redis
docker-compose restart redis

# Check Redis logs
docker-compose logs redis
```

---

## 📝 Quick Test Commands (Copy-Paste)

```powershell
# Start cluster
cd C:\Users\USER\distributed-sync-system\docker
docker-compose up -d
Start-Sleep -Seconds 15

# Test health
cd ..
curl http://localhost:8001/
curl http://localhost:8002/
curl http://localhost:8003/

# Test locks (check status first)
curl http://localhost:8001/locks

# Test cache
curl http://localhost:8001/cache/item:123
curl http://localhost:8001/metrics

# Test PBFT
curl http://localhost:8001/pbft/status

# Run unit tests
pytest tests/unit/ -v

# Stop cluster
cd docker
docker-compose down
```

---

## ✅ Success Indicators

Anda berhasil jika:
- ✅ Semua 4 containers (3 nodes + redis) status "healthy"
- ✅ Health check return 200 OK
- ✅ Cache hit/miss tracking works
- ✅ Metrics menunjukkan data
- ✅ PBFT status accessible
- ✅ Unit tests passing

**Jika Raft locks tidak work (503 error):**
- Ini adalah known issue dengan Docker networking
- Sistem lainnya (queue, cache, PBFT) tetap berfungsi
- Untuk demo locks, bisa run lokal tanpa Docker

---

**Selamat Testing! 🎉**

Jika ada error, screenshot dan tanya saya!
