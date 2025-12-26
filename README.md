# Sistem Sinkronisasi Terdistribusi

Proyek ini mengimplementasikan sistem sinkronisasi terdistribusi yang mensimulasikan bagaimana beberapa node dalam sistem terdistribusi dapat berkomunikasi dan menjaga konsistensi data melalui beberapa komponen inti:

1. **Distributed Lock Manager** (Raft Consensus)
2. **Distributed Queue System** (Consistent Hashing)
3. **Distributed Cache Coherence** (MESI Protocol)

Sistem ini dijalankan dalam lingkungan Docker dengan dukungan Redis sebagai penyimpanan status global. Tujuannya adalah untuk mensimulasikan skenario real-world dari sistem terdistribusi dengan fokus pada konsistensi, fault tolerance, dan performa.

---

## ⚙️ Teknologi yang Digunakan

| Komponen | Teknologi |
|----------|-----------|
| Bahasa | Python 3.11+ |
| Komunikasi | asyncio, aiohttp |
| Penyimpanan status | Redis 6 |
| Orkestrasi | Docker & Docker Compose |
| Load Testing | Locust / Python Benchmark Script |
| Monitoring | Metrics internal (latency, throughput) |

---

## 🚀 Cara Menjalankan

### 1. Install Dependency

```bash
pip install -e .
```

### 2. Jalankan Redis

```bash
docker run -d -p 6379:6379 redis:6-alpine
```

### 3. Jalankan Virtual Environment

```bash
.venv/Scripts/activate  # Windows
```

### 4. Build Docker Images (Pertama kali)

```bash
cd docker
docker-compose up --build
```

### 5. Jalankan Sistem (Sudah Build)

```bash
cd docker
docker-compose up
```

### 6. Verifikasi Sistem

Setelah semua container berjalan, pastikan sistem aktif:

```bash
docker ps
```

Akses node via browser atau curl:

```bash
curl http://localhost:8001/
curl http://localhost:8002/
curl http://localhost:8003/
```

---

## 📹 Video Demonstration

**YouTube**: 

---

## 📡 API Examples

### Distributed Locks

```bash
# Acquire lock
curl -X POST "http://localhost:8001/lock/mylock?lock_type=exclusive"

# Release lock
curl -X DELETE http://localhost:8001/lock/mylock

# Get status
curl http://localhost:8001/locks
```

### Distributed Queue

```bash
# Produce message
curl -X POST http://localhost:8001/queue/orders \
  -H "Content-Type: application/json" \
  -d '{"order_id": 123, "product": "laptop"}'

# Consume message
curl http://localhost:8001/queue/orders
```

### Distributed Cache

```bash
# Read cache
curl http://localhost:8001/cache/item:123

# Write cache
curl -X POST http://localhost:8001/cache/item:999 \
  -H "Content-Type: application/json" \
  -d '{"data": "My cached value"}'
```

### PBFT Consensus (BONUS)

```bash
# Check PBFT status
curl http://localhost:8001/pbft/status

# Submit PBFT request
curl -X POST http://localhost:8001/pbft/request \
  -H "Content-Type: application/json" \
  -d '{"operation": "transfer", "amount": 100}'

# Simulate Byzantine node (for testing)
curl -X POST http://localhost:8001/pbft/simulate-byzantine \
  -H "Content-Type: application/json" \
  -d '{"node_id": "node2"}'
```

---

## 🧪 Testing

```bash
# Unit tests (all components)
pytest tests/unit/ -v

# PBFT specific tests
pytest tests/unit/test_pbft.py -v

# Load testing
locust -f benchmarks/load_test_scenarios.py --host http://localhost:8001

# PBFT comprehensive demo
./demo_pbft.ps1
```

---

## 📁 Project Structure

```
distributed-sync-system/
├── src/
│   ├── consensus/
│   │   ├── raft.py            # Raft consensus
│   │   └── pbft.py            # PBFT consensus (BONUS)
│   ├── nodes/
│   │   ├── lock_manager.py    # Distributed locks
│   │   ├── queue_node.py      # Distributed queue
│   │   ├── cache_node.py      # Distributed cache
│   │   └── pbft_node.py       # PBFT endpoints (BONUS)
│   └── utils/
│       ├── hashing.py         # Consistent hashing
│       └── config.py          # Configuration
├── docker/
│   ├── Dockerfile.node
│   └── docker-compose.yml
├── tests/
│   ├── unit/
│   │   └── test_pbft.py       # PBFT tests (8/8 passing)
│   └── integration/
├── docs/
│   ├── PBFT_ARCHITECTURE.md   # PBFT detailed docs
│   └── pbft_guide.md          # PBFT usage guide
└── demo_pbft.ps1              # PBFT demo script
```