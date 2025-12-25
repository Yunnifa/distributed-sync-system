import asyncio
import httpx
import copy
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from src.consensus.raft import RaftConsensus, RaftState
from src.utils.config import get_settings

# --- Inisialisasi Global ---
raft_instance = RaftConsensus()

# State Machine: HANYA dimodifikasi melalui callback apply_lock_command
# Format: {lock_name: {"type": str, "owners": list, "waiters": list}}
lock_table = {}

# Graf untuk deteksi deadlock: {node_id: list_of_node_ids_it_is_waiting_for}
wait_for_graph = {}

# --- 1. STATE MACHINE CALLBACK (The Core of Consistency) ---

async def apply_lock_command(command: dict):
    """
    Callback ini dipanggil oleh module Raft setelah entry log mencapai COMMIT status.
    Ini menjamin semua node memiliki isi lock_table yang identik.
    """
    global lock_table, wait_for_graph
    
    cmd_type = command.get("type")
    lock_name = command.get("lock_name")
    requester = command.get("requester")
    l_type = command.get("lock_type", "exclusive")

    print(f"[State Machine] Applying: {cmd_type} | Lock: {lock_name} | Node: {requester}")

    if cmd_type == "acquire_lock":
        if lock_name not in lock_table:
            lock_table[lock_name] = {"type": l_type, "owners": [], "waiters": []}
        
        # Tambahkan ke owner jika belum ada
        if requester not in lock_table[lock_name]["owners"]:
            lock_table[lock_name]["owners"].append(requester)
            lock_table[lock_name]["type"] = l_type
        
        # Jika node ini tadinya menunggu, hapus dari wait-for graph
        if requester in wait_for_graph:
            # Hapus ketergantungan pada owner lock ini
            current_owners = lock_table[lock_name]["owners"]
            wait_for_graph[requester] = [n for n in wait_for_graph[requester] if n not in current_owners]
            if not wait_for_graph[requester]:
                del wait_for_graph[requester]

    elif cmd_type == "release_lock":
        if lock_name in lock_table and requester in lock_table[lock_name]["owners"]:
            lock_table[lock_name]["owners"].remove(requester)
            
            # Jika lock sekarang kosong dan ada yang antre (waiters)
            if not lock_table[lock_name]["owners"] and lock_table[lock_name]["waiters"]:
                # Ambil waiter pertama (FIFO)
                next_node, next_type = lock_table[lock_name]["waiters"].pop(0)
                
                # Rekursif: Berikan lock ke waiter berikutnya
                await apply_lock_command({
                    "type": "acquire_lock",
                    "lock_name": lock_name,
                    "lock_type": next_type,
                    "requester": next_node
                })

# --- 2. HELPER FUNCTIONS ---

def detect_deadlock(requesting_node: str, current_owners: list) -> bool:
    """
    Mendeteksi siklus (cycle) pada wait-for graph menggunakan DFS.
    """
    # Simulasi graf jika request ini ditambahkan
    temp_graph = copy.deepcopy(wait_for_graph)
    if requesting_node not in temp_graph:
        temp_graph[requesting_node] = []
    
    for owner in current_owners:
        if owner != requesting_node:
            temp_graph[requesting_node].append(owner)

    def has_cycle(node, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        
        for neighbor in temp_graph.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True
        
        rec_stack.remove(node)
        return False

    visited = set()
    rec_stack = set()
    for node in list(temp_graph.keys()):
        if node not in visited:
            if has_cycle(node, visited, rec_stack):
                return True
    return False

def can_grant_lock(lock_name: str, lock_type: str, requester: str) -> bool:
    """
    Mengecek kompatibilitas lock (Shared vs Exclusive).
    """
    if lock_name not in lock_table or not lock_table[lock_name]["owners"]:
        return True
    
    current = lock_table[lock_name]
    
    # Re-entrancy check
    if requester in current["owners"]:
        return True
    
    # Shared lock can be granted if current is also Shared
    if lock_type == "shared" and current["type"] == "shared":
        return True
        
    return False

async def forward_to_leader(request: Request):
    """
    Meneruskan HTTP Request ke node yang saat ini menjadi Leader.
    """
    settings = get_settings()
    if not raft_instance.leader_id:
        raise HTTPException(status_code=503, detail="Leader belum terpilih")
    
    # Cari URL leader berdasarkan ID
    leader_url = None
    for url in settings.all_nodes:
        if raft_instance.leader_id in url:
            leader_url = url
            break
    
    if not leader_url:
        raise HTTPException(status_code=503, detail="URL Leader tidak ditemukan")

    async with httpx.AsyncClient() as client:
        try:
            url_path = request.url.path
            fwd_url = f"{leader_url}{url_path}"
            print(f"[Proxy] Forwarding ke Leader: {fwd_url}")
            
            fwd_resp = await client.request(
                method=request.method,
                url=fwd_url,
                params=request.query_params,
                headers=dict(request.headers),
                content=await request.body(),
                timeout=10.0
            )
            return JSONResponse(content=fwd_resp.json(), status_code=fwd_resp.status_code)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Gagal menghubungi leader: {e}")

# --- 3. API ROUTES ---

def add_lock_routes(app: FastAPI):
    # Daftarkan State Machine ke Raft
    raft_instance.on_apply_command = apply_lock_command

    @app.on_event("startup")
    async def startup_raft():
        # Delay agar semua container docker siap
        await asyncio.sleep(3.0)
        raft_instance.reset_election_timer()

    @app.post("/lock/{lock_name}")
    async def acquire_lock(lock_name: str, request: Request, lock_type: str = "exclusive"):
        settings = get_settings()
        requester = settings.node_id

        # 1. Jika bukan leader, forward request
        if raft_instance.state != RaftState.LEADER:
            return await forward_to_leader(request)

        # 2. Validasi Lock Type
        if lock_type not in ["shared", "exclusive"]:
            raise HTTPException(status_code=400, detail="Tipe lock harus 'shared' atau 'exclusive'")

        # 3. Cek apakah lock tersedia
        if can_grant_lock(lock_name, lock_type, requester):
            # Cek Deadlock
            owners = lock_table.get(lock_name, {}).get("owners", [])
            if detect_deadlock(requester, owners):
                raise HTTPException(status_code=409, detail="Deadlock terdeteksi! Request dibatalkan.")

            # Buat perintah untuk direplikasi
            command = {
                "type": "acquire_lock",
                "lock_name": lock_name,
                "lock_type": lock_type,
                "requester": requester
            }
            
            # Kirim ke Raft Log
            success = await raft_instance.append_log_entry(command)
            if not success:
                raise HTTPException(status_code=500, detail="Gagal mereplikasi log ke Quorum")

            # 4. Polling: Tunggu sampai State Machine lokal meng-apply log tersebut
            # Ini memastikan client mendapat respon SETELAH data aman/committed
            for _ in range(50): 
                if requester in lock_table.get(lock_name, {}).get("owners", []):
                    return {
                        "status": "success",
                        "message": f"Lock {lock_name} didapatkan",
                        "node": requester,
                        "term": raft_instance.current_term
                    }
                await asyncio.sleep(0.1)
            
            return {"status": "pending", "message": "Log sedang direplikasi"}

        else:
            # Jika lock sedang dipakai, masukkan ke waiters (Hanya di memori Leader)
            if lock_name not in lock_table:
                lock_table[lock_name] = {"type": lock_type, "owners": [], "waiters": []}
            
            lock_table[lock_name]["waiters"].append((requester, lock_type))
            
            # Update wait-for graph untuk deteksi deadlock di masa depan
            if requester not in wait_for_graph:
                wait_for_graph[requester] = []
            wait_for_graph[requester].extend(lock_table[lock_name]["owners"])
            
            raise HTTPException(
                status_code=423, 
                detail=f"Lock {lock_name} sedang dikunci oleh {lock_table[lock_name]['owners']}. Anda masuk antrean."
            )

    @app.delete("/lock/{lock_name}")
    async def release_lock(lock_name: str, request: Request):
        settings = get_settings()
        requester = settings.node_id

        if raft_instance.state != RaftState.LEADER:
            return await forward_to_leader(request)

        if lock_name not in lock_table or requester not in lock_table[lock_name]["owners"]:
            raise HTTPException(status_code=404, detail="Anda tidak memiliki lock ini atau lock tidak ada")

        command = {
            "type": "release_lock",
            "lock_name": lock_name,
            "requester": requester
        }
        
        await raft_instance.append_log_entry(command)
        return {"status": "success", "message": f"Proses pelepasan lock {lock_name} dimulai"}

    @app.get("/locks")
    async def get_all_status():
        """Endpoint monitoring untuk melihat status internal cluster."""
        return {
            "node_id": raft_instance.settings.node_id,
            "raft_state": raft_instance.state.name,
            "current_leader": raft_instance.leader_id,
            "lock_table": lock_table,
            "wait_for_graph": wait_for_graph
        }