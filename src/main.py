import uvicorn
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Muat environment variables
load_dotenv() 

from src.utils.config import get_settings
from src.nodes.queue_node import add_queue_routes
from src.nodes.cache_node import add_cache_routes
from src.nodes.pbft_node import add_pbft_routes
# Kita ambil raft_instance yang sudah dibuat di lock_manager
from src.nodes.lock_manager import add_lock_routes, raft_instance

# 1. Inisialisasi Settings
settings = get_settings()

# 2. Inisialisasi FastAPI
app = FastAPI(
    title=f"Distributed Sync System Node: {settings.node_id}",
    description="Sistem Terdistribusi: Raft Consensus, PBFT, Lock Manager, Queue, & Cache"
)

# --- 3. RAFT RPC ENDPOINTS ---
# Ini adalah "kabel komunikasi" antar node untuk menjalankan algoritma Raft

@app.post("/raft/request-vote")
async def raft_request_vote(request: Request):
    """Endpoint untuk menerima permintaan suara dari Candidate."""
    data = await request.json()
    result = await raft_instance.handle_request_vote(
        term=data["term"],
        candidate_id=data["candidate_id"],
        last_log_index=data["last_log_index"],
        last_log_term=data["last_log_term"]
    )
    return result

@app.post("/raft/append-entries")
async def raft_append_entries(request: Request):
    """Endpoint untuk menerima Heartbeat atau Replikasi Log dari Leader."""
    data = await request.json()
    result = await raft_instance.handle_append_entries(
        term=data["term"],
        leader_id=data["leader_id"],
        entries=data["entries"],
        prev_log_index=data["prev_log_index"],
        prev_log_term=data["prev_log_term"],
        leader_commit=data["leader_commit"]
    )
    return result

# --- 4. HUBUNGKAN RUTE MODUL ---
add_queue_routes(app)
add_cache_routes(app)
add_lock_routes(app) # Di dalamnya sudah ada activate() untuk Raft
add_pbft_routes(app)

# --- 5. HEALTH CHECK ---
@app.get("/")
def read_root():
    return {
        "status": "online",
        "node_id": settings.node_id,
        "raft_state": raft_instance.state.name,
        "current_leader": raft_instance.leader_id,
        "term": raft_instance.current_term,
        "peers_count": len(settings.peers)
    }

# --- 6. RUNNER ---
if __name__ == "__main__":
    server_port = int(os.getenv("PORT", settings.port))
    
    # Gunakan format string agar uvicorn bisa menangani signal dengan baik di Docker
    print(f"🚀 Node '{settings.node_id}' siap di http://0.0.0.0:{server_port}")
    
    uvicorn.run(
        "src.main:app", 
        host="0.0.0.0", 
        port=server_port,
        reload=False
    )