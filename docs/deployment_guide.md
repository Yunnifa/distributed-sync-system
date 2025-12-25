# Deployment Guide - Distributed Synchronization System

## Prerequisites

### Required Software
- **Docker** (version 20.10+) and **Docker Compose** (version 2.0+)
- **Python** 3.8+ (for local development)
- **Git** (for cloning the repository)

### System Requirements
- **RAM**: Minimum 2GB, recommended 4GB
- **CPU**: Minimum 2 cores, recommended 4 cores
- **Disk**: Minimum 1GB free space
- **Network**: All nodes must be able to communicate with each other

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/distributed-sync-system.git
cd distributed-sync-system
```

### 2. Environment Configuration

The system uses `.env` files for configuration. Example files are provided:

```bash
# Copy example files (already exist as .env.node1, .env.node2, .env.node3)
# Review and modify if needed
cat .env.node1
```

**Environment Variables**:
- `PORT`: Port number for this node (8001, 8002, 8003)
- `NODE_ID`: Unique identifier for this node (node1, node2, node3)
- `ALL_NODES`: Comma-separated list of all nodes in the cluster
- `REDIS_HOST`: Redis hostname (default: redis)
- `REDIS_PORT`: Redis port (default: 6379)

## Deployment Options

### Option 1: Docker Compose (Recommended)

This is the easiest way to deploy the entire cluster.

#### Start the Cluster

```bash
cd docker
docker-compose up -d
```

This will start:
- 1 Redis instance (port 6379)
- 3 Node instances (ports 8001, 8002, 8003)

#### Check Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# View logs for specific node
docker-compose logs -f node1
```

#### Stop the Cluster

```bash
docker-compose down

# To also remove volumes (Redis data)
docker-compose down -v
```

### Option 2: Local Development

For development and testing, you can run nodes locally without Docker.

#### Install Dependencies

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install Redis locally and run:
redis-server
```

#### Start Nodes

Open 3 terminal windows and run:

```bash
# Terminal 1 - Node 1
$env:PORT=8001
$env:NODE_ID="node1"
$env:ALL_NODES="http://localhost:8001,http://localhost:8002,http://localhost:8003"
$env:REDIS_HOST="localhost"
python -m src.main

# Terminal 2 - Node 2
$env:PORT=8002
$env:NODE_ID="node2"
$env:ALL_NODES="http://localhost:8001,http://localhost:8002,http://localhost:8003"
$env:REDIS_HOST="localhost"
python -m src.main

# Terminal 3 - Node 3
$env:PORT=8003
$env:NODE_ID="node3"
$env:ALL_NODES="http://localhost:8001,http://localhost:8002,http://localhost:8003"
$env:REDIS_HOST="localhost"
python -m src.main
```

## Verification

### 1. Check Node Health

```bash
# Check each node
curl http://localhost:8001/
curl http://localhost:8002/
curl http://localhost:8003/
```

Expected response:
```json
{
  "message": "Hello from Node node1",
  "port": 8001,
  "peers": ["http://node2:8002", "http://node3:8003"]
}
```

### 2. Check Raft Leader Election

Wait ~10-15 seconds for leader election, then check logs:

```bash
docker-compose logs | grep "LEADER"
```

You should see one node transitioning to LEADER.

### 3. Test Distributed Lock

```bash
# Acquire exclusive lock
curl -X POST "http://localhost:8001/lock/test-lock?lock_type=exclusive"

# Check lock status
curl http://localhost:8001/lock/test-lock

# Release lock
curl -X DELETE http://localhost:8001/lock/test-lock
```

### 4. Test Distributed Queue

```bash
# Produce message
curl -X POST http://localhost:8001/queue/test-queue \
  -H "Content-Type: application/json" \
  -d '{"data": "Hello World"}'

# Consume message
curl http://localhost:8001/queue/test-queue
```

### 5. Test Distributed Cache

```bash
# Read from cache (will fetch from DB)
curl http://localhost:8001/cache/item:123

# Write to cache
curl -X POST http://localhost:8001/cache/item:999 \
  -H "Content-Type: application/json" \
  -d '{"data": "New cached value"}'

# Read again (should be cached)
curl http://localhost:8001/cache/item:999
```

## Scaling

### Adding More Nodes

1. Create new `.env.nodeX` file:
```bash
PORT=8004
NODE_ID=node4
ALL_NODES=http://node1:8001,http://node2:8002,http://node3:8003,http://node4:8004
REDIS_HOST=redis
REDIS_PORT=6379
```

2. Add service to `docker-compose.yml`:
```yaml
  node4:
    build:
      context: ..
      dockerfile: docker/Dockerfile.node
    env_file:
      - ../.env.node4
    ports:
      - "8004:8004"
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8004/"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 10s
    restart: unless-stopped
```

3. Update `ALL_NODES` in all existing `.env` files

4. Restart the cluster:
```bash
docker-compose down
docker-compose up -d
```

## Monitoring

### View Metrics

```bash
curl http://localhost:8001/metrics
```

Response:
```json
{
  "cache_hits": 150,
  "cache_misses": 50,
  "cache_stats": {
    "size": 45,
    "maxsize": 128,
    "states": {...}
  }
}
```

### View All Locks

```bash
curl http://localhost:8001/locks
```

### Docker Health Checks

```bash
# Check health status
docker-compose ps

# All services should show "healthy" status
```

## Troubleshooting

### Issue: No Leader Elected

**Symptoms**: Logs show repeated elections, no stable leader

**Solutions**:
1. Check network connectivity between nodes
2. Ensure all nodes have same `ALL_NODES` configuration
3. Check for clock skew between nodes
4. Increase election timeout if network is slow

### Issue: Redis Connection Failed

**Symptoms**: `❌ Node X GAGAL terhubung ke Redis`

**Solutions**:
1. Verify Redis is running: `docker-compose ps redis`
2. Check Redis logs: `docker-compose logs redis`
3. Verify `REDIS_HOST` and `REDIS_PORT` in `.env` files
4. Ensure Redis container is healthy before nodes start

### Issue: Lock Request Returns 503

**Symptoms**: `503 Service Unavailable` when acquiring lock

**Solutions**:
1. Wait for leader election to complete (~10-15 seconds after startup)
2. Check which node is leader: `docker-compose logs | grep LEADER`
3. Verify Raft is running: Check for heartbeat messages in logs

### Issue: Queue Messages Not Found

**Symptoms**: `404 Queue is empty` immediately after producing

**Solutions**:
1. Check if request was forwarded to correct node (check logs)
2. Verify consistent hashing is working: All nodes should have same `ALL_NODES`
3. Check Redis data: `docker exec -it <redis-container> redis-cli KEYS "*"`

### Issue: Cache Not Invalidating

**Symptoms**: Stale data returned after write

**Solutions**:
1. Check network connectivity between nodes
2. Verify invalidation broadcast in logs: Look for "INVALIDATE diterima"
3. Check cache state: `curl http://localhost:8001/metrics`

### Issue: Docker Build Fails

**Symptoms**: `ERROR: failed to solve: dockerfile.node: not found`

**Solutions**:
1. Ensure `docker-compose.yml` references `Dockerfile.node` (capital D)
2. Verify file exists: `ls docker/Dockerfile.node`
3. Check file permissions

## Performance Tuning

### Raft Timeouts

Edit `src/consensus/raft.py`:
```python
self._heartbeat_interval = 1.0  # Reduce for faster failure detection
self._min_election_timeout = 5.0  # Reduce for faster elections
self._max_election_timeout = 10.0
```

### Cache Size

Edit `src/nodes/cache_node.py`:
```python
cache_store = CacheStore(maxsize=256)  # Increase for more caching
```

### Redis Persistence

Edit `docker-compose.yml` to add Redis persistence options:
```yaml
redis:
  command: redis-server --appendonly yes --appendfsync everysec
```

## Security Hardening

### Production Deployment

1. **Use TLS**: Configure HTTPS for all endpoints
2. **Add Authentication**: Implement JWT or API keys
3. **Network Isolation**: Use Docker networks or VPNs
4. **Redis Password**: Set Redis password in configuration
5. **Rate Limiting**: Add rate limiting to prevent abuse

### Example: Adding Redis Password

1. Update `docker-compose.yml`:
```yaml
redis:
  command: redis-server --requirepass mypassword
```

2. Update `.env` files:
```bash
REDIS_PASSWORD=mypassword
```

3. Update `src/nodes/queue_node.py`:
```python
redis_client = redis.Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password,
    db=0,
    decode_responses=True
)
```

## Backup and Recovery

### Backup Redis Data

```bash
# Create backup
docker exec <redis-container> redis-cli SAVE
docker cp <redis-container>:/data/dump.rdb ./backup/

# Restore backup
docker cp ./backup/dump.rdb <redis-container>:/data/
docker-compose restart redis
```

### Backup Configuration

```bash
# Backup all .env files
tar -czf config-backup.tar.gz .env.*
```

## Next Steps

- Run load tests: See `benchmarks/load_test_scenarios.py`
- Review architecture: See `docs/architecture.md`
- Check API documentation: See `docs/api_spec.yaml`
- Run unit tests: `pytest tests/unit/`
