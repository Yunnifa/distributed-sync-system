# Distributed Synchronization System - Architecture

## System Overview

This is a distributed synchronization system implementing three core components:
1. **Distributed Lock Manager** using Raft consensus
2. **Distributed Queue System** using consistent hashing
3. **Distributed Cache Coherence** with LRU eviction and MESI-like protocol

## Architecture Diagram

```mermaid
graph TB
    Client[Client Applications]
    
    subgraph Cluster["Distributed Cluster"]
        Node1[Node 1<br/>Port 8001]
        Node2[Node 2<br/>Port 8002]
        Node3[Node 3<br/>Port 8003]
        
        subgraph Raft["Raft Consensus Layer"]
            Leader[Raft Leader]
            Follower1[Raft Follower]
            Follower2[Raft Follower]
        end
        
        Redis[(Redis<br/>Shared State)]
    end
    
    Client --> Node1
    Client --> Node2
    Client --> Node3
    
    Node1 --> Redis
    Node2 --> Redis
    Node3 --> Redis
    
    Node1 <-.Heartbeat.-> Node2
    Node2 <-.Heartbeat.-> Node3
    Node3 <-.Heartbeat.-> Node1
    
    Node1 -.->|Leader Election| Leader
    Node2 -.-> Follower1
    Node3 -.-> Follower2
```

## Component Architecture

### 1. Raft Consensus Module

**Location**: `src/consensus/raft.py`

**Purpose**: Provides distributed consensus for lock management and ensures consistency across nodes.

**Key Features**:
- Leader election with randomized timeouts (5-10 seconds)
- Log replication with consistency checks
- Heartbeat mechanism (1 second interval)
- Automatic failover on leader failure
- Support for log entry appending and commit tracking

**State Machine**:
```mermaid
stateDiagram-v2
    [*] --> FOLLOWER
    FOLLOWER --> CANDIDATE: Election Timeout
    CANDIDATE --> LEADER: Win Election
    CANDIDATE --> FOLLOWER: Discover Higher Term
    LEADER --> FOLLOWER: Discover Higher Term
    CANDIDATE --> CANDIDATE: Split Vote
```

**Data Structures**:
- `log`: List of log entries `[{"term": int, "command": dict}]`
- `current_term`: Current term number
- `voted_for`: Candidate ID voted for in current term
- `commit_index`: Index of highest log entry known to be committed
- `leader_id`: ID of the current leader

### 2. Distributed Lock Manager

**Location**: `src/nodes/lock_manager.py`

**Purpose**: Provides distributed locking with deadlock detection.

**Lock Types**:
- **Exclusive Lock**: Only one node can hold the lock
- **Shared Lock**: Multiple nodes can hold the lock simultaneously

**Deadlock Detection**:
- Uses wait-for graph to track dependencies
- Cycle detection algorithm (DFS-based)
- Rejects lock requests that would create cycles

**Lock Flow**:
```mermaid
sequenceDiagram
    participant Client
    participant Follower
    participant Leader
    participant LockTable
    
    Client->>Follower: POST /lock/mylock?lock_type=exclusive
    Follower->>Leader: Forward request
    Leader->>LockTable: Check if available
    alt Lock Available
        LockTable-->>Leader: Available
        Leader->>Leader: Check deadlock
        Leader->>LockTable: Grant lock
        Leader->>Raft: Append log entry
        Leader-->>Client: 200 OK (lock acquired)
    else Lock Held
        LockTable-->>Leader: Held by node2
        Leader->>Leader: Check deadlock
        Leader->>LockTable: Add to waiters
        Leader-->>Client: 423 Locked
    end
```

### 3. Distributed Queue System

**Location**: `src/nodes/queue_node.py`

**Purpose**: Provides distributed message queue with at-least-once delivery.

**Key Features**:
- Consistent hashing for queue distribution
- Message persistence via Redis
- At-least-once delivery guarantee
- Automatic request forwarding to responsible node

**Queue Distribution**:
```mermaid
graph LR
    Queue1[queue_orders] --> Node1
    Queue2[queue_payments] --> Node2
    Queue3[queue_notifications] --> Node3
    Queue4[queue_analytics] --> Node1
    
    subgraph "Consistent Hash Ring"
        Node1
        Node2
        Node3
    end
```

**Message Flow**:
1. Producer sends message to any node
2. Node uses consistent hashing to determine responsible node
3. If not responsible, forwards to correct node
4. Message stored in Redis list
5. Consumer retrieves message (moved to processing queue)
6. Consumer ACKs message (removed from processing queue)

### 4. Distributed Cache Coherence

**Location**: `src/nodes/cache_node.py`

**Purpose**: Provides distributed caching with coherence protocol.

**Cache States** (MESI-like):
- **M (Modified)**: Cache line is dirty, exclusive to this node
- **S (Shared)**: Cache line is clean, may exist in other caches
- **I (Invalid)**: Cache line is invalid

**Coherence Protocol**:
```mermaid
sequenceDiagram
    participant Node1
    participant Node2
    participant Node3
    participant DB
    
    Node1->>DB: Write(key1, "new value")
    Node1->>Node1: Update local cache (state=M)
    Node1->>Node2: Invalidate(key1)
    Node1->>Node3: Invalidate(key1)
    Node2->>Node2: Mark cache entry Invalid
    Node3->>Node3: Mark cache entry Invalid
    
    Note over Node2: Next read will fetch from DB
```

**LRU Eviction**:
- Uses `OrderedDict` to maintain access order
- Evicts least recently used entry when cache is full
- Thread-safe with locking

## Communication Patterns

### Inter-Node Communication

**Protocol**: HTTP/JSON over REST API

**Message Types**:
1. **Raft RPCs**:
   - `POST /raft/request-vote`: Request votes during election
   - `POST /raft/append-entries`: Heartbeat and log replication

2. **Lock Operations**:
   - `POST /lock/{name}`: Acquire lock
   - `DELETE /lock/{name}`: Release lock
   - `GET /lock/{name}`: Get lock status

3. **Queue Operations**:
   - `POST /queue/{name}`: Produce message
   - `GET /queue/{name}`: Consume message
   - `POST /queue/ack/{processing_queue}`: Acknowledge message

4. **Cache Operations**:
   - `GET /cache/{key}`: Read from cache
   - `POST /cache/{key}`: Write to cache
   - `POST /cache/invalidate/{key}`: Invalidate cache entry

### Failure Handling

**Leader Failure**:
1. Followers stop receiving heartbeats
2. Election timeout triggers (5-10 seconds)
3. Follower transitions to candidate
4. New election begins
5. New leader elected within ~10-15 seconds

**Node Failure**:
- Queue messages persist in Redis
- Cache entries lost on failed node
- Locks held by failed node remain until timeout (future enhancement)

**Network Partition**:
- Raft ensures only one leader per term
- Minority partition cannot make progress
- Majority partition continues operating
- Partitions reconcile when network heals

## Data Flow

### Write Path (Cache)
```
Client → Node → Update Local Cache (M) → Update DB → Broadcast Invalidate → Other Nodes Mark Invalid
```

### Read Path (Cache)
```
Client → Node → Check Local Cache → (Hit) Return → (Miss) Fetch from DB → Store in Cache (S) → Return
```

### Lock Acquisition Path
```
Client → Any Node → Forward to Leader → Check Availability → Check Deadlock → Grant/Deny → Replicate via Raft
```

### Queue Message Path
```
Producer → Any Node → Hash(queue_name) → Forward to Responsible Node → Store in Redis → Consumer Retrieves → ACK
```

## Performance Characteristics

**Raft Consensus**:
- Leader election: 5-15 seconds
- Heartbeat interval: 1 second
- Log replication: Synchronous to majority

**Distributed Locks**:
- Acquisition latency: ~10-50ms (leader) or ~50-200ms (follower with forwarding)
- Deadlock detection: O(N) where N = number of nodes

**Distributed Queue**:
- Throughput: ~1000-5000 messages/second (limited by Redis)
- Latency: ~5-20ms (same node) or ~20-100ms (forwarded)

**Distributed Cache**:
- Hit latency: ~1-5ms
- Miss latency: ~10-50ms
- Invalidation propagation: ~50-200ms

## Scalability

**Horizontal Scaling**:
- Add more nodes to the cluster
- Update `ALL_NODES` environment variable
- Restart cluster for consistent hashing to redistribute

**Limitations**:
- Raft requires majority for progress (odd number of nodes recommended)
- All nodes must be able to communicate with each other
- Redis is a single point of failure (can be clustered separately)

## Security Considerations

**Current Implementation**:
- No authentication or encryption
- Suitable for trusted internal networks only

**Future Enhancements**:
- TLS for inter-node communication
- JWT-based authentication
- RBAC for lock and queue access
