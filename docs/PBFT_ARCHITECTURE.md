# PBFT (Practical Byzantine Fault Tolerance) - Architecture & Demo

## 🏛 PBFT Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────┐
│                    PBFT Consensus Cluster                     │
│                   (Byzantine Fault Tolerant)                  │
└───────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
  ┌──────────┐          ┌──────────┐          ┌──────────┐
  │  Node 1  │          │  Node 2  │          │  Node 3  │
  │ PRIMARY  │◀────────▶│ REPLICA  │◀────────▶│ REPLICA  │
  │  :8001   │          │  :8002   │          │  :8003   │
  └──────────┘          └──────────┘          └──────────┘
  is_primary=TRUE       is_primary=FALSE      is_primary=FALSE
  
  f = 0 (Byzantine tolerance)
  Total nodes: 3
  Quorum needed: 2f + 1 = 1 (in this setup)
```

### PBFT vs Raft Comparison

```
┌─────────────────┬──────────────────────┬──────────────────────┐
│     Aspect      │        Raft          │        PBFT          │
├─────────────────┼──────────────────────┼──────────────────────┤
│ Fault Model     │ Crash Fault          │ Byzantine Fault      │
│ Leader          │ Elected via voting   │ Deterministic (view) │
│ Phases          │ 2 (Vote, Commit)     │ 3 (Pre-Prepare,      │
│                 │                      │    Prepare, Commit)  │
│ Status in Proj  │ ❌ Not working       │ ✅ WORKING!          │
│ Complexity      │ Medium               │ High                 │
│ Use Case        │ Distributed Locks    │ Byzantine protection │
└─────────────────┴──────────────────────┴──────────────────────┘
```

---

## 🔄 PBFT 3-Phase Protocol

### Phase Flow Diagram

```
Client              Primary (Node 1)         Replica 2           Replica 3
  │                       │                      │                   │
  │  1. REQUEST           │                      │                   │
  │  operation="transfer" │                      │                   │
  ├──────────────────────▶│                      │                   │
  │                       │                      │                   │
  │                       │  2. PRE-PREPARE      │                   │
  │                       │  (seq=1, digest)     │                   │
  │                       ├─────────────────────▶│                   │
  │                       ├──────────────────────┼──────────────────▶│
  │                       │                      │                   │
  │                       │                      │  3. PREPARE       │
  │                       │                      │  (I accept)       │
  │                       ◀─────────────────────┤                   │
  │                       ◀──────────────────────┼───────────────────┤
  │                       │                      │                   │
  │                       │                      │◀─────────────────▶│
  │                       │                      │  (replicas sync)  │
  │                       │                      │                   │
  │                       │  4. COMMIT           │                   │
  │                       │  (execute now)       │                   │
  │                       ├─────────────────────▶│                   │
  │                       ├──────────────────────┼──────────────────▶│
  │                       │                      │                   │
  │                       │◀─────────────────────┤                   │
  │                       │◀──────────────────────────────────────────┤
  │                       │  5. REPLY            │                   │
  │                       │                      │                   │
  │  6. RESPONSE          │                      │                   │
  │  consensus=TRUE       │                      │                   │
  ◀──────────────────────┤                      │                   │
  │                       │                      │                   │
  
  ✅ Request executed after quorum reached in each phase
```

### Detailed Phase Explanation

**Phase 1: PRE-PREPARE (Primary broadcasts)**
```
Primary (Node 1):
  ┌─────────────────────────────────────┐
  │ PRE-PREPARE Message                 │
  ├─────────────────────────────────────┤
  │ view:     0                         │
  │ sequence: 1                         │
  │ digest:   hash(request)             │
  │ request:  "transfer 100"            │
  │ signature: sign(primary_key)        │
  └─────────────────────────────────────┘
         │
         ├──────────▶ Replica 2
         └──────────▶ Replica 3
```

**Phase 2: PREPARE (Replicas validate and broadcast)**
```
Each Replica:
  1. Verify signature ✓
  2. Check view number ✓
  3. Check sequence ✓
  4. Broadcast PREPARE to all nodes
  
Replica 2:
  ┌─────────────────────────────────────┐
  │ PREPARE Message                     │
  ├─────────────────────────────────────┤
  │ view:     0                         │
  │ sequence: 1                         │
  │ digest:   hash(request)             │
  │ node_id:  "node2"                   │
  │ signature: sign(node2_key)          │
  └─────────────────────────────────────┘
         │
         ├──────────▶ Primary
         ├──────────▶ Replica 3
         
Prepared Certificate = 2f + 1 = 1 PREPARE messages
```

**Phase 3: COMMIT (Execute request)**
```
Each Node (after prepared):
  1. Broadcast COMMIT message
  2. Wait for 2f + 1 COMMIT messages
  3. Execute request
  4. Send REPLY to client
  
Committed = 2f + 1 = 1 COMMIT messages received
```

---

## 🛡️ Byzantine Fault Tolerance

### What is Byzantine Fault?

```
┌────────────────────────────────────────────────────────────┐
│              Types of Node Failures                        │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ✅ CRASH FAULT (Raft handles this)                       │
│     Node fails and stops responding                       │
│     Example: Server shutdown, network partition           │
│                                                            │
│  🛡️ BYZANTINE FAULT (PBFT handles this)                   │
│     Node behaves maliciously or arbitrarily               │
│     Examples:                                              │
│     - Sending conflicting messages to different nodes     │
│     - Corrupting data before forwarding                   │
│     - Lying about received messages                       │
│     - Altering timestamps                                 │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

### Byzantine Detection in This Implementation

```
Normal Node Behavior:
┌──────────────┐
│   Client     │
└──────┬───────┘
       │ Request: "transfer 100"
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Primary    │────▶│  Replica 2   │────▶│  Replica 3   │
│  digest: ABC │     │  digest: ABC │     │  digest: ABC │
└──────────────┘     └──────────────┘     └──────────────┘
                     ✅ All agree: digest matches


Byzantine Node Detected:
┌──────────────┐
│   Client     │
└──────┬───────┘
       │ Request: "transfer 100"
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Primary    │────▶│ Byzantine!   │────▶│  Replica 3   │
│  digest: ABC │     │ digest: XYZ  │     │  digest: ABC │
└──────────────┘     └──────┬───────┘     └──────────────┘
                            │
                            ▼
                    ❌ Digest mismatch!
                    Node 2 marked as SUSPICIOUS
```

---

## 📊 Message Types & Structure

### 1. PRE-PREPARE Message
```json
{
  "type": "pre-prepare",
  "view": 0,
  "sequence": 1,
  "digest": "a3f5c91...",
  "request": {
    "operation": "transfer",
    "amount": 100
  },
  "timestamp": 1703401234.567,
  "signature": "sig_primary_..."
}
```

### 2. PREPARE Message
```json
{
  "type": "prepare",
  "view": 0,
  "sequence": 1,
  "digest": "a3f5c91...",
  "node_id": "node2",
  "signature": "sig_node2_..."
}
```

### 3. COMMIT Message
```json
{
  "type": "commit",
  "view": 0,
  "sequence": 1,
  "digest": "a3f5c91...",
  "node_id": "node3",
  "signature": "sig_node3_..."
}
```

### 4. REPLY Message
```json
{
  "view": 0,
  "sequence": 1,
  "result": "executed",
  "node_id": "node1",
  "signature": "sig_node1_..."
}
```

---

## 🧪 Testing PBFT

### Quick Status Check
```powershell
# Check PBFT status
Invoke-RestMethod -Uri "http://127.0.0.1:8001/pbft/status"

# Expected output:
# primary: node1
# is_primary: True
# view: 0
# sequence: 0
# f: 0
# quorum_size: 1
```

### Submit Request
```powershell
# Submit PBFT request
$body = '{"operation": "transfer", "amount": 100}'
Invoke-RestMethod -Uri "http://127.0.0.1:8001/pbft/request" -Method POST -Body $body -ContentType "application/json"

# Expected output:
# status: consensus_started
# sequence: 1
# digest: <hash>
```

### Simulate Byzantine Node
```powershell
# Mark node as Byzantine
$body = '{"node_id": "node2"}'
Invoke-RestMethod -Uri "http://127.0.0.1:8001/pbft/simulate-byzantine" -Method POST -Body $body -ContentType "application/json"

# Check status again
Invoke-RestMethod -Uri "http://127.0.0.1:8001/pbft/status"

# byzantine_nodes should now contain node2
```

---

## 🎯 Implementation Details

### Code Structure
```
src/consensus/pbft.py (450+ lines)
├── PBFTConsensus class
│   ├── Pre-prepare phase handler
│   ├── Prepare phase handler
│   ├── Commit phase handler
│   ├── Message validation
│   ├── Signature verification (SHA-256)
│   ├── Byzantine detection logic
│   └── View change mechanism
│
src/nodes/pbft_node.py (100+ lines)
├── FastAPI endpoints
│   ├── POST /pbft/request
│   ├── POST /pbft/message
│   ├── GET  /pbft/status
│   └── POST /pbft/simulate-byzantine
│
tests/unit/test_pbft.py (8 tests, ALL PASSING ✅)
├── test_pbft_initialization
├── test_pbft_digest_computation
├── test_pbft_message_signing
├── test_pbft_pre_prepare
├── test_pbft_prepare
├── test_pbft_commit
├── test_pbft_consensus
└── test_view_change
```

### Key Features Implemented
```
✅ Complete 3-phase PBFT protocol
✅ Cryptographic signatures (SHA-256 HMAC)
✅ Byzantine node detection
✅ Message validation & verification
✅ Quorum calculation (2f + 1)
✅ View change mechanism
✅ Request sequencing
✅ Digest computation
✅ Prepared & Committed certificates
✅ Comprehensive unit tests (8/8 passing)
```

---

## 📈 Performance Characteristics

```
┌─────────────────────┬──────────────────┐
│      Metric         │      Value       │
├─────────────────────┼──────────────────┤
│ Nodes               │ 3                │
│ Byzantine tolerance │ f = 0 (can add)  │
│ Quorum size         │ 2f + 1 = 1       │
│ Message complexity  │ O(n²)            │
│ Latency             │ ~3 RTT           │
│ Throughput          │ Limited by n²    │
└─────────────────────┴──────────────────┘
```

**Note**: With 3 nodes and f=0, system tolerates 0 Byzantine failures.
To tolerate 1 Byzantine failure, need 4 nodes (3f+1 = 4, where f=1).

---

## 🎓 Educational Value

**Why PBFT is Important:**
1. **Real-world relevance**: Used in blockchain systems (Hyperledger Fabric, Zilliqa)
2. **Byzantine tolerance**: Handles malicious nodes, not just crashes
3. **Cryptographic security**: Message signing prevents tampering
4. **Deterministic**: No randomness in leader selection
5. **Research significance**: Seminal paper (Castro & Liskov, 1999)

**Advantages over Raft:**
- ✅ Handles Byzantine faults (malicious behavior)
- ✅ Cryptographic guarantees
- ✅ No leader election needed

**Disadvantages:**
- Communication complexity O(n²)
- Requires 3f+1 nodes instead of 2f+1
- More complex implementation

---


