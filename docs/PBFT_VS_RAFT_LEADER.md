# PBFT vs Raft: Leader Selection Mechanisms

## 🎯 Konsep "Leader" di PBFT vs Raft

### Perbedaan Fundamental

```
┌────────────────────────────────────────────────────────────────┐
│                  RAFT LEADER ELECTION                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Mekanisme: VOTING-BASED (Democratic)                         │
│                                                                │
│  Step 1: Node timeout → becomes CANDIDATE                     │
│  Step 2: Sends RequestVote to all peers                       │
│  Step 3: Nodes vote based on:                                 │
│          - Term number (higher wins)                          │
│          - Log completeness (more complete wins)              │
│  Step 4: Candidate with MAJORITY becomes LEADER               │
│                                                                │
│  Formula: Need (n/2) + 1 votes                                │
│                                                                │
│  Randomness: YES (random election timeouts 5-10s)             │
│  Predictability: LOW (depends on network timing)              │
│                                                                │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│                PBFT PRIMARY SELECTION                          │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Mekanisme: DETERMINISTIC (Formula-based)                     │
│                                                                │
│  Formula: primary_id = view % num_nodes                       │
│                                                                │
│  Example with 3 nodes (node0, node1, node2):                  │
│    View 0: primary = 0 % 3 = 0 → node0                        │
│    View 1: primary = 1 % 3 = 1 → node1                        │
│    View 2: primary = 2 % 3 = 2 → node2                        │
│    View 3: primary = 3 % 3 = 0 → node0 (cycles)               │
│                                                                │
│  Randomness: NONE (completely predictable)                    │
│  Predictability: HIGH (always same for given view)            │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Primary Selection in PBFT

### Deterministic Formula

```python
# In our implementation (src/consensus/pbft.py)

def get_primary_for_view(view: int, all_nodes: List[str]) -> str:
    """
    Primary is determined by view number.
    No voting needed - it's a mathematical calculation!
    """
    primary_index = view % len(all_nodes)
    return all_nodes[primary_index]

# Example:
all_nodes = ["node1", "node2", "node3"]

# View 0:
primary = all_nodes[0 % 3] = all_nodes[0] = "node1" ✓

# View 1:
primary = all_nodes[1 % 3] = all_nodes[1] = "node2" ✓

# View 2:
primary = all_nodes[2 % 3] = all_nodes[2] = "node3" ✓
```

### Current Implementation Status

In our system (`node_id = "node1"` di port 8001):

```
┌──────────────────────────────────────────┐
│  PBFT Current State                      │
├──────────────────────────────────────────┤
│  view:        0                          │
│  all_nodes:   ["node1", "node2", "node3"]│
│  primary:     node1  (0 % 3 = 0)         │
│  is_primary:  TRUE                       │
│                                          │
│  ✅ node1 is PRIMARY in view 0          │
└──────────────────────────────────────────┘
```

---

## 🔁 View Change: How PBFT Changes Primary

Unlike Raft (which re-elects), PBFT uses **VIEW CHANGE** protocol:

```
Scenario: Primary (node1) is Byzantine or unresponsive

Step 1: TIMEOUT
┌──────────┐      ┌──────────┐      ┌──────────┐
│  node1   │      │  node2   │      │  node3   │
│ PRIMARY  │      │ REPLICA  │      │ REPLICA  │
│ (silent) │      │          │      │          │
└──────────┘      └────┬─────┘      └────┬─────┘
                       │                  │
                       │ Timeout! No msgs │
                       ▼                  ▼
                   Trigger VIEW-CHANGE


Step 2: BROADCAST VIEW-CHANGE
┌──────────┐      ┌──────────┐      ┌──────────┐
│  node1   │      │  node2   │      │  node3   │
│          │      │          │      │          │
│          │◀─────┤          │◀─────┤          │
│          │      │          │      │          │
└──────────┘      └────┬─────┘      └────┬─────┘
                       │                  │
              VIEW-CHANGE(view=1) VIEW-CHANGE(view=1)
              

Step 3: NEW VIEW
After 2f+1 VIEW-CHANGE messages:
┌──────────┐      ┌──────────┐      ┌──────────┐
│  node1   │      │  node2   │      │  node3   │
│ REPLICA  │      │ PRIMARY  │      │ REPLICA  │
│          │      │ (new)    │      │          │
└──────────┘      └──────────┘      └──────────┘

New primary = view % 3 = 1 % 3 = 1 → node2 ✓
```

---

## 📊 Comparison Table

### PBFT Primary vs Raft Leader

| Feature | Raft LEADER | PBFT PRIMARY |
|---------|-------------|--------------|
| **Selection Method** | Voting-based election | Deterministic formula |
| **Formula** | Majority (n/2 + 1) votes | view % num_nodes |
| **Requires Voting** | ✅ Yes (RequestVote RPC) | ❌ No voting needed |
| **Random Component** | ✅ Yes (random timeouts) | ❌ Completely deterministic |
| **Predictable** | ❌ No (timing-dependent) | ✅ Yes (formula-based) |
| **Change Mechanism** | Re-election (new term) | View change (new view) |
| **All nodes know who?** | After election completes | **Immediately** (can calculate) |
| **Network overhead** | O(n) RequestVote messages | O(n²) in view change |
| **Time to select** | ~RoundTripTime x 2 | **Instant** (no messages) |

### When Leadership Changes

**Raft:**
```
Triggers:
- Leader crash/network partition
- Election timeout (no heartbeat)
- Higher term discovered

Process:
1. Follower timeout → CANDIDATE
2. Increment term
3. Send RequestVote
4. Collect votes
5. If majority → LEADER

Time: 5-10 seconds (election timeout)
```

**PBFT:**
```
Triggers:
- Primary unresponsive (timeout)
- Primary detected as Byzantine
- Explicit view change request

Process:
1. Replica timeout → send VIEW-CHANGE
2. Wait for 2f+1 VIEW-CHANGE messages
3. Calculate new primary: (view+1) % n
4. New primary sends NEW-VIEW
5. All nodes adopt new view

Time: ~3 network round trips
```

---

## 🎓 Why Different Approaches?

### Raft's Voting Approach
**Goal**: Ensure log consistency across crashes
**Problem**: Need to choose node with most up-to-date log
**Solution**: Let nodes vote based on log completeness
**Trade-off**: Randomness needed to avoid split votes

### PBFT's Deterministic Approach
**Goal**: Tolerate Byzantine (malicious) nodes
**Problem**: Byzantine nodes could lie in votes!
**Solution**: Don't trust votes - use formula ALL nodes agree on
**Trade-off**: Need view change protocol for failures

---

## 💡 Practical Implications

### Raft Leader Election
```
Advantages:
✅ Flexible - best node can become leader
✅ Considers log completeness
✅ Simpler protocol (just 2 RPCs)

Disadvantages:
❌ Unpredictable timing
❌ Possible split votes
❌ Randomness required
❌ Our implementation: FAILS (timing bug)
```

### PBFT Primary Selection
```
Advantages:
✅ Instant - no waiting for votes
✅ Predictable - everyone knows who's primary
✅ Fair rotation - all nodes get turns
✅ Byzantine-proof - can't manipulate formula
✅ Our implementation: WORKS! ✅

Disadvantages:
❌ Can't choose "best" node
❌ Fixed rotation regardless of node quality
❌ View change is complex (O(n²) messages)
```

---

## 🔬 In Our Implementation

### PBFT Primary Status
```powershell
# Check current primary
Invoke-RestMethod -Uri "http://127.0.0.1:8001/pbft/status"

# Output:
# view: 0
# primary: "node1"
# is_primary: True

# This is DETERMINISTIC - no voting happened!
# node1 is primary because: 0 % 3 = 0 = node1
```

### Raft Leader Status
```powershell
# Check current leader
Invoke-RestMethod -Uri "http://127.0.0.1:8001/locks"

# Output:
# leader: null
# is_leader: False

# This FAILED - voting mechanism has bug
```

---

## 📝 Summary

**Question: "Apakah di PBFT juga bisa memilih leader?"**

**Answer:**
1. **Ya**, PBFT punya "leader" yang disebut **PRIMARY**
2. **Tidak**, PRIMARY tidak "dipilih" melalui voting
3. PRIMARY ditentukan **secara otomatis** dengan formula: `view % num_nodes`
4. Semua node bisa **langsung tahu** siapa PRIMARY tanpa komunikasi
5. Jika PRIMARY fail/Byzantine → **VIEW CHANGE** protocol (bukan re-election)

**Analogi:**
- **Raft**: Seperti pemilu demokratis (vote for best candidate)
- **PBFT**: Seperti sistem rotasi bergilir (giliran based on formula)

**In practice:**
- ✅ PBFT: PRIMARY selection **ALWAYS WORKS** (deterministic)
- ❌ Raft: Leader election **FAILED** in our env (timing bug)

---

## 🎯 For Presentation

**Key Talking Point:**
"PBFT tidak butuh election karena menggunakan formula matematis untuk tentukan primary. Ini lebih robust terhadap Byzantine nodes yang bisa manipulasi votes. Formula `view % num_nodes` guarantee semua honest nodes setuju siapa primary-nya."
