import asyncio
import random
from enum import Enum
from src.utils.config import get_settings
from src.communication.message_passing import send_rpc_to_peer

class RaftState(Enum):
    FOLLOWER = 1
    CANDIDATE = 2
    LEADER = 3

class RaftConsensus:
    def __init__(self):
        self.settings = get_settings()
        self.state = RaftState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log = [] # List of {"term": int, "command": dict}
        self.commit_index = 0
        self.last_applied = 0
        self.leader_id = None
        
        # State Machine Callback
        self.on_apply_command = None 

        self.next_index = {}
        self.match_index = {}

        self._election_timer_task = None
        self._heartbeat_task = None
        self._commit_monitor_task = asyncio.create_task(self._commit_monitor())
        
        self._heartbeat_interval = 0.5
        self._min_election_timeout = 2.0
        self._max_election_timeout = 4.0

    def _get_last_log_index(self) -> int:
        return len(self.log)

    def _get_last_log_term(self) -> int:
        return self.log[-1]["term"] if self.log else 0

    async def _commit_monitor(self):
        """Monitor commit_index dan aplikasikan ke State Machine."""
        while True:
            try:
                if self.commit_index > self.last_applied:
                    self.last_applied += 1
                    entry = self.log[self.last_applied - 1]
                    if self.on_apply_command:
                        await self.on_apply_command(entry["command"])
                        print(f"[{self.settings.node_id}] Applied log index {self.last_applied}")
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Error in commit monitor: {e}")

    async def _transition_to_leader(self):
        print(f"[{self.settings.node_id}] ✨ BECOMING LEADER for Term {self.current_term} ✨")
        self.state = RaftState.LEADER
        self.leader_id = self.settings.node_id
        
        last_idx = self._get_last_log_index()
        for peer_url in self.settings.peers:
            peer_id = peer_url.split('//')[1].split(':')[0]
            self.next_index[peer_id] = last_idx + 1
            self.match_index[peer_id] = 0

        if self._election_timer_task:
            self._election_timer_task.cancel()

        async def leader_loop():
            while self.state == RaftState.LEADER:
                await self._send_append_entries()
                await asyncio.sleep(self._heartbeat_interval)

        self._heartbeat_task = asyncio.create_task(leader_loop())

    async def _send_append_entries(self):
        """Kirim heartbeats atau log entries ke semua peer."""
        total_nodes = len(self.settings.all_nodes)
        
        for peer_url in self.settings.peers:
            peer_id = peer_url.split('//')[1].split(':')[0]
            
            # Ambil entries baru jika next_index peer tertinggal
            prev_idx = self.next_index.get(peer_id, 1) - 1
            entries = self.log[prev_idx:] if len(self.log) > prev_idx else []
            prev_term = self.log[prev_idx-1]["term"] if prev_idx > 0 else 0

            payload = {
                "term": self.current_term,
                "leader_id": self.settings.node_id,
                "entries": entries,
                "prev_log_index": prev_idx,
                "prev_log_term": prev_term,
                "leader_commit": self.commit_index,
            }

            try:
                response = await send_rpc_to_peer(peer_url, "/raft/append-entries", payload)
                if response.get("term", 0) > self.current_term:
                    await self._transition_to_follower(response["term"])
                    return
                
                if response.get("success"):
                    self.next_index[peer_id] = prev_idx + len(entries) + 1
                    self.match_index[peer_id] = prev_idx + len(entries)
            except:
                pass

        # Update commit_index jika mayoritas sudah match
        for N in range(len(self.log), self.commit_index, -1):
            if self.log[N-1]["term"] == self.current_term:
                count = 1 # Self
                for peer_url in self.settings.peers:
                    p_id = peer_url.split('//')[1].split(':')[0]
                    if self.match_index.get(p_id, 0) >= N:
                        count += 1
                if count > (total_nodes // 2):
                    self.commit_index = N
                    break

    async def handle_append_entries(self, term, leader_id, entries, prev_log_index, prev_log_term, leader_commit):
        if term < self.current_term:
            return {"term": self.current_term, "success": False}
        
        self.reset_election_timer()
        self.leader_id = leader_id
        
        if term > self.current_term:
            await self._transition_to_follower(term)

        # Log Consistency Check
        if prev_log_index > 0:
            if prev_log_index > len(self.log) or self.log[prev_log_index-1]["term"] != prev_log_term:
                return {"term": self.current_term, "success": False}

        # Append entries
        if entries:
            self.log = self.log[:prev_log_index] + entries
        
        if leader_commit > self.commit_index:
            self.commit_index = min(leader_commit, len(self.log))
            
        return {"term": self.current_term, "success": True}

    async def append_log_entry(self, command: dict) -> bool:
        if self.state != RaftState.LEADER:
            return False
        self.log.append({"term": self.current_term, "command": command})
        return True

    # ... (Metode reset_election_timer, _transition_to_follower, dll tetap sama) ...
    def reset_election_timer(self):
        if self._election_timer_task:
            self._election_timer_task.cancel()
        if self.state != RaftState.LEADER:
            self._election_timer_task = asyncio.create_task(self._election_timeout_handler())

    async def _transition_to_follower(self, term):
        self.state = RaftState.FOLLOWER
        self.current_term = term
        self.voted_for = None
        self.reset_election_timer()