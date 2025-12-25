"""
PBFT (Practical Byzantine Fault Tolerance) Consensus Implementation

This module implements the PBFT consensus algorithm which can tolerate
Byzantine failures (malicious or faulty nodes) up to f = (n-1)/3 where n is
the total number of nodes.

PBFT Phases:
1. Request: Client sends request to primary
2. Pre-Prepare: Primary broadcasts pre-prepare message
3. Prepare: Replicas broadcast prepare messages
4. Commit: Replicas broadcast commit messages
5. Reply: Replicas send reply to client

Byzantine Fault Tolerance:
- Can tolerate up to f faulty nodes where n = 3f + 1
- Requires 2f + 1 matching messages for consensus
- Uses cryptographic signatures for message authentication
"""

import asyncio
import hashlib
import json
import time
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from src.utils.config import get_settings


class PBFTPhase(Enum):
    """PBFT consensus phases"""
    IDLE = 0
    PRE_PREPARE = 1
    PREPARE = 2
    COMMIT = 3
    REPLY = 4


@dataclass
class PBFTMessage:
    """PBFT protocol message"""
    msg_type: str  # "pre-prepare", "prepare", "commit", "reply"
    view: int  # Current view number
    sequence: int  # Sequence number for this request
    digest: str  # Hash of the request
    node_id: str  # Sender node ID
    timestamp: float = field(default_factory=time.time)
    request: Optional[dict] = None  # Original request (only in pre-prepare)
    signature: Optional[str] = None  # Digital signature (simplified)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "msg_type": self.msg_type,
            "view": self.view,
            "sequence": self.sequence,
            "digest": self.digest,
            "node_id": self.node_id,
            "timestamp": self.timestamp,
            "request": self.request,
            "signature": self.signature
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PBFTMessage':
        """Create from dictionary"""
        return cls(**data)


class PBFTConsensus:
    """
    PBFT Consensus implementation with Byzantine fault tolerance.
    
    Tolerates up to f = (n-1)/3 Byzantine failures where n is total nodes.
    For 4 nodes: f=1, for 7 nodes: f=2, etc.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # PBFT state
        self.view = 0  # Current view number
        self.sequence = 0  # Current sequence number
        self.primary_id = None  # ID of current primary
        
        # Message logs
        self.pre_prepare_log: Dict[int, PBFTMessage] = {}  # sequence -> message
        self.prepare_log: Dict[int, List[PBFTMessage]] = defaultdict(list)  # sequence -> messages
        self.commit_log: Dict[int, List[PBFTMessage]] = defaultdict(list)  # sequence -> messages
        
        # Executed requests
        self.executed: Set[int] = set()  # Set of executed sequence numbers
        self.last_executed = 0
        
        # Request queue
        self.pending_requests: List[dict] = []
        
        # Byzantine detection
        self.suspicious_nodes: Dict[str, int] = defaultdict(int)  # node_id -> suspicion_count
        self.byzantine_threshold = 3  # Mark as Byzantine after 3 suspicious behaviors
        
        # Calculate fault tolerance
        n = len(self.settings.all_nodes)
        self.f = (n - 1) // 3  # Maximum faulty nodes
        self.quorum_size = 2 * self.f + 1  # Required for consensus
        
        # Determine primary (simple: first node in sorted list)
        sorted_nodes = sorted([url.split('//')[1].split(':')[0] for url in self.settings.all_nodes])
        self.primary_id = sorted_nodes[self.view % len(sorted_nodes)]
        
        print(f"[PBFT {self.settings.node_id}] Initialized. n={n}, f={self.f}, quorum={self.quorum_size}, primary={self.primary_id}")
    
    def is_primary(self) -> bool:
        """Check if this node is the current primary"""
        return self.settings.node_id == self.primary_id
    
    def compute_digest(self, request: dict) -> str:
        """Compute cryptographic hash of request"""
        request_str = json.dumps(request, sort_keys=True)
        return hashlib.sha256(request_str.encode()).hexdigest()
    
    def sign_message(self, message: PBFTMessage) -> str:
        """
        Sign a message (simplified - in production use real cryptographic signatures)
        """
        msg_str = f"{message.msg_type}:{message.view}:{message.sequence}:{message.digest}:{message.node_id}"
        return hashlib.sha256(msg_str.encode()).hexdigest()
    
    def verify_signature(self, message: PBFTMessage) -> bool:
        """
        Verify message signature (simplified)
        """
        expected = self.sign_message(message)
        return message.signature == expected
    
    def detect_byzantine_behavior(self, node_id: str, reason: str):
        """
        Detect and track Byzantine (malicious) behavior
        """
        self.suspicious_nodes[node_id] += 1
        print(f"[PBFT {self.settings.node_id}] ⚠️ Suspicious behavior from {node_id}: {reason} (count: {self.suspicious_nodes[node_id]})")
        
        if self.suspicious_nodes[node_id] >= self.byzantine_threshold:
            print(f"[PBFT {self.settings.node_id}] 🚨 Node {node_id} marked as BYZANTINE!")
            return True
        return False
    
    def is_byzantine(self, node_id: str) -> bool:
        """Check if a node is marked as Byzantine"""
        return self.suspicious_nodes[node_id] >= self.byzantine_threshold
    
    async def handle_client_request(self, request: dict) -> dict:
        """
        Handle client request (entry point for PBFT)
        
        If this is the primary: start pre-prepare phase
        If this is a replica: forward to primary
        """
        if self.is_primary():
            return await self.start_consensus(request)
        else:
            # Forward to primary
            return {
                "status": "forwarded",
                "primary": self.primary_id,
                "message": "Request forwarded to primary"
            }
    
    async def start_consensus(self, request: dict) -> dict:
        """
        Primary starts consensus by broadcasting pre-prepare
        """
        if not self.is_primary():
            return {"error": "Only primary can start consensus"}
        
        self.sequence += 1
        digest = self.compute_digest(request)
        
        # Create pre-prepare message
        pre_prepare = PBFTMessage(
            msg_type="pre-prepare",
            view=self.view,
            sequence=self.sequence,
            digest=digest,
            node_id=self.settings.node_id,
            request=request
        )
        pre_prepare.signature = self.sign_message(pre_prepare)
        
        # Store in log
        self.pre_prepare_log[self.sequence] = pre_prepare
        
        print(f"[PBFT {self.settings.node_id}] PRIMARY: Broadcasting pre-prepare seq={self.sequence}")
        
        # Broadcast to all replicas
        await self.broadcast_message(pre_prepare)
        
        # Primary also processes its own pre-prepare
        await self.handle_pre_prepare(pre_prepare)
        
        return {
            "status": "consensus_started",
            "sequence": self.sequence,
            "digest": digest
        }
    
    async def handle_pre_prepare(self, message: PBFTMessage):
        """
        Replica handles pre-prepare message from primary
        
        Validates:
        1. Message is from current primary
        2. Signature is valid
        3. Sequence number is correct
        4. No conflicting pre-prepare exists
        """
        # Validate sender is primary
        if message.node_id != self.primary_id:
            self.detect_byzantine_behavior(message.node_id, "Non-primary sent pre-prepare")
            return
        
        # Validate signature
        if not self.verify_signature(message):
            self.detect_byzantine_behavior(message.node_id, "Invalid signature")
            return
        
        # Check for conflicting pre-prepare
        if message.sequence in self.pre_prepare_log:
            existing = self.pre_prepare_log[message.sequence]
            if existing.digest != message.digest:
                self.detect_byzantine_behavior(message.node_id, "Conflicting pre-prepare")
                return
        
        # Store pre-prepare
        self.pre_prepare_log[message.sequence] = message
        
        print(f"[PBFT {self.settings.node_id}] Received pre-prepare seq={message.sequence} from {message.node_id}")
        
        # Send prepare message
        prepare = PBFTMessage(
            msg_type="prepare",
            view=self.view,
            sequence=message.sequence,
            digest=message.digest,
            node_id=self.settings.node_id
        )
        prepare.signature = self.sign_message(prepare)
        
        # Store own prepare
        self.prepare_log[message.sequence].append(prepare)
        
        # Broadcast prepare
        await self.broadcast_message(prepare)
        
        # Check if we have enough prepares
        await self.check_prepare_quorum(message.sequence)
    
    async def handle_prepare(self, message: PBFTMessage):
        """
        Handle prepare message from replica
        
        Collects prepare messages until quorum (2f+1) is reached
        """
        # Validate signature
        if not self.verify_signature(message):
            self.detect_byzantine_behavior(message.node_id, "Invalid prepare signature")
            return
        
        # Ignore messages from Byzantine nodes
        if self.is_byzantine(message.node_id):
            return
        
        # Check if we have pre-prepare for this sequence
        if message.sequence not in self.pre_prepare_log:
            # Might receive prepare before pre-prepare (network delay)
            return
        
        pre_prepare = self.pre_prepare_log[message.sequence]
        
        # Validate digest matches
        if message.digest != pre_prepare.digest:
            self.detect_byzantine_behavior(message.node_id, "Prepare digest mismatch")
            return
        
        # Store prepare message
        prepares = self.prepare_log[message.sequence]
        
        # Check for duplicate
        if any(p.node_id == message.node_id for p in prepares):
            return  # Already have prepare from this node
        
        prepares.append(message)
        
        print(f"[PBFT {self.settings.node_id}] Received prepare seq={message.sequence} from {message.node_id} ({len(prepares)}/{self.quorum_size})")
        
        # Check if we have quorum
        await self.check_prepare_quorum(message.sequence)
    
    async def check_prepare_quorum(self, sequence: int):
        """
        Check if we have enough prepare messages (2f+1) to move to commit phase
        """
        if sequence not in self.prepare_log:
            return
        
        prepares = self.prepare_log[sequence]
        
        # Need 2f+1 prepares (including own)
        if len(prepares) >= self.quorum_size:
            print(f"[PBFT {self.settings.node_id}] ✅ PREPARE QUORUM reached for seq={sequence}")
            
            # Send commit message
            pre_prepare = self.pre_prepare_log[sequence]
            commit = PBFTMessage(
                msg_type="commit",
                view=self.view,
                sequence=sequence,
                digest=pre_prepare.digest,
                node_id=self.settings.node_id
            )
            commit.signature = self.sign_message(commit)
            
            # Store own commit
            self.commit_log[sequence].append(commit)
            
            # Broadcast commit
            await self.broadcast_message(commit)
            
            # Check if we have enough commits
            await self.check_commit_quorum(sequence)
    
    async def handle_commit(self, message: PBFTMessage):
        """
        Handle commit message from replica
        
        Collects commit messages until quorum (2f+1) is reached
        """
        # Validate signature
        if not self.verify_signature(message):
            self.detect_byzantine_behavior(message.node_id, "Invalid commit signature")
            return
        
        # Ignore Byzantine nodes
        if self.is_byzantine(message.node_id):
            return
        
        # Store commit message
        commits = self.commit_log[message.sequence]
        
        # Check for duplicate
        if any(c.node_id == message.node_id for c in commits):
            return
        
        commits.append(message)
        
        print(f"[PBFT {self.settings.node_id}] Received commit seq={message.sequence} from {message.node_id} ({len(commits)}/{self.quorum_size})")
        
        # Check if we have quorum
        await self.check_commit_quorum(message.sequence)
    
    async def check_commit_quorum(self, sequence: int):
        """
        Check if we have enough commit messages (2f+1) to execute request
        """
        if sequence in self.executed:
            return  # Already executed
        
        if sequence not in self.commit_log:
            return
        
        commits = self.commit_log[sequence]
        
        # Need 2f+1 commits
        if len(commits) >= self.quorum_size:
            print(f"[PBFT {self.settings.node_id}] ✅ COMMIT QUORUM reached for seq={sequence}")
            
            # Execute the request
            await self.execute_request(sequence)
    
    async def execute_request(self, sequence: int):
        """
        Execute the request after commit quorum is reached
        """
        if sequence in self.executed:
            return
        
        if sequence not in self.pre_prepare_log:
            return
        
        pre_prepare = self.pre_prepare_log[sequence]
        request = pre_prepare.request
        
        print(f"[PBFT {self.settings.node_id}] 🎯 EXECUTING request seq={sequence}: {request}")
        
        # Mark as executed
        self.executed.add(sequence)
        self.last_executed = max(self.last_executed, sequence)
        
        # Here you would apply the state machine transition
        # For now, we just log it
        
        return {
            "status": "executed",
            "sequence": sequence,
            "request": request
        }
    
    async def broadcast_message(self, message: PBFTMessage):
        """
        Broadcast PBFT message to all peers
        """
        from src.communication.message_passing import send_rpc_to_peer
        
        tasks = []
        for peer_url in self.settings.peers:
            tasks.append(send_rpc_to_peer(
                peer_url,
                "/pbft/message",
                message.to_dict()
            ))
        
        # Fire and forget (don't wait for responses)
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_status(self) -> dict:
        """Get current PBFT status"""
        return {
            "view": self.view,
            "sequence": self.sequence,
            "primary": self.primary_id,
            "is_primary": self.is_primary(),
            "f": self.f,
            "quorum_size": self.quorum_size,
            "last_executed": self.last_executed,
            "executed_count": len(self.executed),
            "byzantine_nodes": [node for node, count in self.suspicious_nodes.items() if count >= self.byzantine_threshold],
            "suspicious_nodes": dict(self.suspicious_nodes)
        }
