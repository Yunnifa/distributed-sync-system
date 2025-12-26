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
lock_table = {}
# Graf untuk deteksi deadlock
wait_for_graph = {}

# --- 1. STATE MACHINE CALLBACK (The Core of Consistency) ---

async def apply_lock_command(command: dict):
    """
    Callback ini dipanggil oleh module Raft melalui commit_monitor setelah Quorum tercapai.
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
        
        if requester not in lock_table[lock_name]["owners"]:
            lock_table[lock_name]["owners"].append(requester)
            lock_table[lock_name]["type"] = l_type
        
        # Bersihkan graf jika sebelumnya node ini menunggu
        if requester in wait_for_graph:
            current_owners = lock_table[lock_name]["owners"]
            wait_for_graph[requester] = [n for n in wait_for_graph[requester] if n not in current_owners]
            if not wait_for_graph[requester]:
                del wait_for_graph[requester]

    elif cmd_type == "release_lock":
        if lock_name in lock_table and requester in lock_table[lock_name]["owners"]:
            lock_table[lock_name]["owners"].remove(requester)
            
            # FIFO: Berikan ke waiter berikutnya jika owner kosong
            if not lock_table[lock_name]["owners"] and lock_table[lock_name]["waiters"]:
                next_node, next_type = lock_table[lock_name]["waiters"].pop(0)
                # Secara rekursif panggil apply untuk memberikan lock ke waiter
                await apply_lock_command({
                    "type": "acquire_lock",
                    "lock_name": lock_name,
                    "lock_type": next_type,
                    "requester": next_node
                })

# --- 2. HELPER FUNCTIONS ---

def detect_deadlock(requesting_node: str, current_owners: list) -> bool:
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
    if lock_name not in lock_table or not lock_table[lock_name]["owners"]:
        return True
    current = lock_table[lock_name]
    if requester in current["owners"]:
        return True
    if lock_type == "shared" and current["type"] == "shared":
        return True
    return False

async def forward_to_leader(request: Request):
    settings = get_settings()
    if not raft_instance.leader_id:
        raise HTTPException(status_code=503, detail="Leader belum terpilih")
    
    leader_url = next((url for url in settings.all_nodes if raft_instance.leader_id in url), None)
    
    if not leader_url:
        raise HTTPException(status_code=503, detail="URL Leader tidak ditemukan")

    async with httpx.AsyncClient() as client:
        try:
            fwd_url = f"{leader_url}{request.url.path}"
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
    raft_instance.on_apply_command = apply_lock_command

    @app.on_event("startup")
    async def startup_raft():
        # --- UPDATE TERBARU: AKTIFKAN BACKGROUND TASKS ---
        raft_instance.activate() 
        
        await asyncio.sleep(3.0)
        raft_instance.reset_election_timer()

    @app.post("/lock/{lock_name}")
    async def acquire_lock(lock_name: str, request: Request, lock_type: str = "exclusive"):
        settings = get_settings()
        requester = settings.node_id

        if raft_instance.state != RaftState.LEADER:
            return await forward_to_leader(request)

        if lock_type not in ["shared", "exclusive"]:
            raise HTTPException(status_code=400, detail="Tipe lock harus 'shared' atau 'exclusive'")

        if can_grant_lock(lock_name, lock_type, requester):
            owners = lock_table.get(lock_name, {}).get("owners", [])
            if detect_deadlock(requester, owners):
                raise HTTPException(status_code=409, detail="Deadlock terdeteksi!")

            command = {
                "type": "acquire_lock",
                "lock_name": lock_name,
                "lock_type": lock_type,
                "requester": requester
            }
            
            success = await raft_instance.append_log_entry(command)
            if not success:
                raise HTTPException(status_code=500, detail="Gagal mereplikasi log")

            # Polling sampai committed
            for _ in range(50): 
                if requester in lock_table.get(lock_name, {}).get("owners", []):
                    return {
                        "status": "success",
                        "node": requester,
                        "term": raft_instance.current_term
                    }
                await asyncio.sleep(0.1)
            
            return {"status": "pending"}

        else:
            # Masukkan ke waiters (hanya di memori Leader)
            if lock_name not in lock_table:
                lock_table[lock_name] = {"type": lock_type, "owners": [], "waiters": []}
            
            lock_table[lock_name]["waiters"].append((requester, lock_type))
            
            if requester not in wait_for_graph:
                wait_for_graph[requester] = []
            wait_for_graph[requester].extend(lock_table[lock_name]["owners"])
            
            raise HTTPException(status_code=423, detail="Lock sibuk, Anda masuk antrean.")

    @app.delete("/lock/{lock_name}")
    async def release_lock(lock_name: str, request: Request):
        if raft_instance.state != RaftState.LEADER:
            return await forward_to_leader(request)

        if lock_name not in lock_table or raft_instance.settings.node_id not in lock_table[lock_name]["owners"]:
            raise HTTPException(status_code=404, detail="Lock tidak ditemukan atau bukan milik Anda")

        command = {
            "type": "release_lock",
            "lock_name": lock_name,
            "requester": raft_instance.settings.node_id
        }
        
        await raft_instance.append_log_entry(command)
        return {"status": "success", "message": "Pelepasan lock direplikasi"}

    @app.get("/locks")
    async def get_all_status():
        return {
            "node_id": raft_instance.settings.node_id,
            "raft_state": raft_instance.state.name,
            "current_leader": raft_instance.leader_id,
            "lock_table": lock_table,
            "wait_for_graph": wait_for_graph
        }