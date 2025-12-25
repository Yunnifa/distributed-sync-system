# Files to Remove or Hide from Submission
# (These are extra/debug files not required by assignment)

## Extra Documentation (Redundant)
- docs/ARSITEKTUR_VISUAL.md          # Redundant (keep architecture.md)
- docs/PBFT_VS_RAFT_LEADER.md        # Extra comparison doc
- docs/ARCHITECTURE_CHECKLIST.md     # Internal checklist
- TESTING_GUIDE.md                   # Extra guide

## Debug/Test Scripts (Not Required)
- debug_config.py                    # Debug script
- debug_leader_election.py           # Debug script
- test_rpc.py                        # Test helper
- test_manual_vote.py                # Test helper
- test_deadlock.py                   # Can move to tests/ or remove
- test_system.py                     # Can move to tests/ or remove
- quick_check.py                     # Quick status check
- check_*.py                         # Any check scripts

## Temporary/Emergency Files
- emergency_fix.txt                  # Temporary notes
- raft_election_fix.txt              # Temporary notes

## Extra PowerShell Scripts
- restart_cluster.ps1                # Extra utility
- watch_logs.ps1                     # Extra utility

## Setup Files (Optional)
- setup.py                           # Not required
- pyproject.toml                     # Not required (have requirements.txt)

---

## KEEP THESE FILES (Assignment Requirements)

### Core Source Code
✓ src/nodes/lock_manager.py
✓ src/nodes/queue_node.py  
✓ src/nodes/cache_node.py
✓ src/nodes/pbft_node.py (BONUS)
✓ src/consensus/raft.py
✓ src/consensus/pbft.py (BONUS)
✓ src/communication/message_passing.py
✓ src/utils/config.py
✓ src/utils/metrics.py
✓ src/main.py

### Tests
✓ tests/unit/*.py (all)
✓ tests/integration/*.py (all if exists)

### Docker
✓ docker/Dockerfile.node
✓ docker-compose.yml

### Benchmarks
✓ benchmarks/load_test_scenarios.py

### Documentation (Required)
✓ README.md
✓ FINAL_REPORT.md
✓ docs/architecture.md
✓ docs/api_spec.yaml
✓ docs/deployment_guide.md

### Documentation (BONUS - PBFT)
✓ docs/pbft_guide.md
✓ docs/PBFT_ARCHITECTURE.md

### Scripts (Essential)
✓ run_node1.ps1
✓ run_node2.ps1
✓ run_node3.ps1
✓ start_local_cluster.ps1
✓ run_tests.ps1
✓ demo_pbft.ps1 (BONUS demo)

### Configuration
✓ requirements.txt
✓ .env.example
✓ .gitignore

---

## Actions to Clean Repository

```powershell
# Move extra docs to backup (optional)
mkdir .backup
mv docs/ARSITEKTUR_VISUAL.md .backup/
mv docs/PBFT_VS_RAFT_LEADER.md .backup/
mv docs/ARCHITECTURE_CHECKLIST.md .backup/
mv TESTING_GUIDE.md .backup/

# Remove debug scripts
rm debug_*.py
rm test_rpc.py
rm test_manual_vote.py
rm quick_check.py
rm emergency_fix.txt
rm raft_election_fix.txt

# Remove extra scripts
rm restart_cluster.ps1
rm watch_logs.ps1

# Commit clean version
git add .
git commit -m "Clean repository for submission - keep only required + PBFT bonus"
```

---

## Final Repository Structure

```
distributed-sync-system/
├── src/                          # ✓ REQUIRED
│   ├── nodes/
│   │   ├── lock_manager.py       # ✓ Lock Manager
│   │   ├── queue_node.py         # ✓ Queue System
│   │   ├── cache_node.py         # ✓ Cache Coherence
│   │   └── pbft_node.py          # ✓ BONUS
│   ├── consensus/
│   │   ├── raft.py               # ✓ Raft Consensus
│   │   └── pbft.py               # ✓ BONUS PBFT
│   ├── communication/
│   │   └── message_passing.py    # ✓ Inter-node comm
│   └── utils/
│       ├── config.py             # ✓ Configuration
│       └── metrics.py            # ✓ Metrics
├── tests/                        # ✓ REQUIRED
│   └── unit/                     # ✓ Unit tests
├── docker/                       # ✓ REQUIRED
│   ├── Dockerfile.node           # ✓ Docker config
│   └── docker-compose.yml        # ✓ Orchestration
├── docs/                         # ✓ REQUIRED
│   ├── architecture.md           # ✓ Main architecture
│   ├── api_spec.yaml             # ✓ API documentation
│   ├── deployment_guide.md       # ✓ Deployment guide
│   ├── pbft_guide.md             # ✓ BONUS - PBFT guide
│   └── PBFT_ARCHITECTURE.md      # ✓ BONUS - PBFT arch
├── benchmarks/                   # ✓ REQUIRED
│   └── load_test_scenarios.py    # ✓ Load tests
├── requirements.txt              # ✓ REQUIRED
├── .env.example                  # ✓ REQUIRED
├── .gitignore                    # ✓ REQUIRED
├── README.md                     # ✓ REQUIRED
├── FINAL_REPORT.md               # ✓ REQUIRED
├── run_node1.ps1                 # ✓ Node scripts
├── run_node2.ps1                 # ✓ Node scripts
├── run_node3.ps1                 # ✓ Node scripts
├── start_local_cluster.ps1       # ✓ Cluster startup
├── run_tests.ps1                 # ✓ Test runner
└── demo_pbft.ps1                 # ✓ BONUS demo
```

**Total: Clean, professional, submission-ready repository!** ✅
