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
        
        # Callback untuk State Machine (misal: Lock Manager)
        self.on_apply_command = None 

        self.next_index = {}
        self.match_index = {}

        # Inisialisasi task sebagai None untuk menghindari "no running event loop"
        self._election_timer_task = None
        self._heartbeat_task = None
        self._commit_monitor_task = None
        
        self._heartbeat_interval = 0.5
        self._min_election_timeout = 2.0
        self._max_election_timeout = 4.0

    def activate(self):
        """Memulai background tasks setelah event loop tersedia (Startup FastAPI)."""
        if self._commit_monitor_task is None:
            self._commit_monitor_task = asyncio.create_task(self._commit_monitor())
            print(f"[{self.settings.node_id}] Raft Tasks Activated.")

    def _get_last_log_index(self) -> int:
        return len(self.log)

    def _get_last_log_term(self) -> int:
        return self.log[-1]["term"] if self.log else 0

    # --- CORE RAFT LOGIC: COMMIT MONITOR ---
    async def _commit_monitor(self):
        """Menerapkan command ke State Machine setelah konsensus tercapai."""
        while True:
            try:
                if self.commit_index > self.last_applied:
                    self.last_applied += 1
                    entry = self.log[self.last_applied - 1]
                    if self.on_apply_command:
                        await self.on_apply_command(entry["command"])
                        print(f"[{self.settings.node_id}] State Machine Applied index: {self.last_applied}")
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Commit Monitor Error: {e}")

    # --- CORE RAFT LOGIC: ELECTION ---
    def reset_election_timer(self):
        """Reset timer pemilihan pemimpin."""
        if self._election_timer_task:
            self._election_timer_task.cancel()
        if self.state != RaftState.LEADER:
            self._election_timer_task = asyncio.create_task(self._election_timeout_handler())

    async def _election_timeout_handler(self):
        """Menangani transisi ke Candidate jika timeout habis."""
        timeout = random.uniform(self._min_election_timeout, self._max_election_timeout)
        try:
            await asyncio.sleep(timeout)
            if self.state != RaftState.LEADER:
                print(f"[{self.settings.node_id}] Timeout! Memulai Election.")
                await self._transition_to_candidate()
        except asyncio.CancelledError:
            pass

    async def _transition_to_candidate(self):
        """Mencalonkan diri sebagai pemimpin."""
        self.state = RaftState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.settings.node_id
        self.reset_election_timer()
        
        votes_received = 1 # Suara dari diri sendiri
        total_nodes = len(self.settings.all_nodes)
        
        print(f"[{self.settings.node_id}] Menjadi CANDIDATE untuk Term {self.current_term}")

        for peer_url in self.settings.peers:
            payload = {
                "term": self.current_term,
                "candidate_id": self.settings.node_id,
                "last_log_index": self._get_last_log_index(),
                "last_log_term": self._get_last_log_term()
            }
            try:
                resp = await send_rpc_to_peer(peer_url, "/raft/request-vote", payload)
                if resp.get("vote_granted"):
                    votes_received += 1
                elif resp.get("term", 0) > self.current_term:
                    await self._transition_to_follower(resp["term"])
                    return
            except:
                continue

        if votes_received > (total_nodes // 2):
            await self._transition_to_leader()

    async def handle_request_vote(self, term, candidate_id, last_log_index, last_log_term):
        """Dipanggil oleh node lain yang meminta suara."""
        if term < self.current_term:
            return {"term": self.current_term, "vote_granted": False}

        if term > self.current_term:
            await self._transition_to_follower(term)

        # Safety: Pastikan log kandidat minimal se-up-to-date log lokal
        log_ok = (last_log_term > self._get_last_log_term()) or \
                 (last_log_term == self._get_last_log_term() and last_log_index >= self._get_last_log_index())

        if (self.voted_for is None or self.voted_for == candidate_id) and log_ok:
            self.voted_for = candidate_id
            self.reset_election_timer()
            return {"term": self.current_term, "vote_granted": True}

        return {"term": self.current_term, "vote_granted": False}

    # --- CORE RAFT LOGIC: LEADER ---
    async def _transition_to_leader(self):
        self.state = RaftState.LEADER
        self.leader_id = self.settings.node_id
        print(f"[{self.settings.node_id}] ✨ LEADER ELECTED untuk Term {self.current_term} ✨")
        
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
        total_nodes = len(self.settings.all_nodes)
        for peer_url in self.settings.peers:
            peer_id = peer_url.split('//')[1].split(':')[0]
            p_idx = self.next_index.get(peer_id, 1) - 1
            entries = self.log[p_idx:]
            p_term = self.log[p_idx-1]["term"] if p_idx > 0 else 0

            payload = {
                "term": self.current_term,
                "leader_id": self.settings.node_id,
                "entries": entries,
                "prev_log_index": p_idx,
                "prev_log_term": p_term,
                "leader_commit": self.commit_index,
            }
            try:
                resp = await send_rpc_to_peer(peer_url, "/raft/append-entries", payload)
                if resp.get("term", 0) > self.current_term:
                    await self._transition_to_follower(resp["term"])
                    return
                
                if resp.get("success"):
                    self.next_index[peer_id] = p_idx + len(entries) + 1
                    self.match_index[peer_id] = p_idx + len(entries)
                else:
                    self.next_index[peer_id] = max(1, self.next_index[peer_id] - 1)
            except:
                continue

        # Update commit_index jika mayoritas sudah match
        for n in range(len(self.log), self.commit_index, -1):
            if self.log[n-1]["term"] == self.current_term:
                count = 1 
                for p_url in self.settings.peers:
                    p_id = p_url.split('//')[1].split(':')[0]
                    if self.match_index.get(p_id, 0) >= n:
                        count += 1
                if count > (total_nodes // 2):
                    self.commit_index = n
                    break

    async def handle_append_entries(self, term, leader_id, entries, prev_log_index, prev_log_term, leader_commit):
        if term < self.current_term:
            return {"term": self.current_term, "success": False}
        
        self.reset_election_timer()
        self.leader_id = leader_id
        if term > self.current_term:
            await self._transition_to_follower(term)

        # Consistency Check
        if prev_log_index > 0:
            if prev_log_index > len(self.log) or (len(self.log) >= prev_log_index and self.log[prev_log_index-1]["term"] != prev_log_term):
                return {"term": self.current_term, "success": False}

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

    async def _transition_to_follower(self, term):
        self.state = RaftState.FOLLOWER
        self.current_term = term
        self.voted_for = None
        self.reset_election_timer()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()