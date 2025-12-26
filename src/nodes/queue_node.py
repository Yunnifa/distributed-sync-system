import redis
import httpx
import json
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from src.utils.config import get_settings
from src.utils.hashing import ConsistentHasher

# 1. Inisialisasi Settings & Client
settings = get_settings()

# Inisialisasi Redis dengan Error Handling yang baik
try:
    redis_client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=0,
        decode_responses=True 
    )
    redis_client.ping()
    print(f"✅ Node {settings.node_id}: Connected to Redis at {settings.redis_host}:{settings.port}")
except redis.exceptions.ConnectionError:
    print(f"❌ Node {settings.node_id}: Failed to connect to Redis.")
    redis_client = None

# 2. Setup Consistent Hashing
# Mengambil daftar node ID dari konfigurasi URL (misal: node1, node2, node3)
node_ids = [url.split('//')[1].split(':')[0] for url in settings.all_nodes]
hasher = ConsistentHasher(nodes=node_ids)

# --- HELPER FUNCTIONS ---

async def forward_request(node_id: str, request: Request):
    """Meneruskan request ke node yang bertanggung jawab berdasarkan Consistent Hashing."""
    node_url = next((url for url in settings.all_nodes if node_id in url), None)
    if not node_url:
        raise HTTPException(status_code=500, detail="Target node URL not found")

    async with httpx.AsyncClient() as client:
        try:
            url_path = request.url.path
            fwd_url = f"{node_url}{url_path}"
            
            fwd_response = await client.request(
                method=request.method,
                url=fwd_url,
                headers=dict(request.headers),
                content=await request.body(),
                timeout=10.0
            )
            # Kembalikan response asli dari node target
            return fwd_response.json(), fwd_response.status_code
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Forwarding error to {node_id}: {e}")

# --- API ROUTES ---

def add_queue_routes(app: FastAPI):
    
    @app.post("/queue/{queue_name}")
    async def produce(queue_name: str, message: dict, request: Request):
        """
        Menambahkan pesan ke antrean. 
        Menjamin pesan disimpan di node yang benar via Consistent Hashing.
        """
        if not redis_client:
            raise HTTPException(status_code=503, detail="Redis unavailable")
        
        responsible_node = hasher.get_node(queue_name)
        
        # Transparansi Lokasi: Jika bukan tugas node ini, teruskan ke pemiliknya
        if responsible_node != settings.node_id:
            print(f"[Queue] Proxying Produce '{queue_name}' -> {responsible_node}")
            json_resp, status_code = await forward_request(responsible_node, request)
            return JSONResponse(content=json_resp, status_code=status_code)

        try:
            # Serialisasi aman menggunakan JSON
            payload = json.dumps(message)
            redis_client.lpush(f"queue:{queue_name}", payload)
            return {
                "status": "produced", 
                "queue": queue_name, 
                "node": settings.node_id,
                "message": message
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/queue/{queue_name}")
    async def consume(queue_name: str, request: Request):
        """
        Mengambil pesan dengan semantik At-Least-Once Delivery.
        Menggunakan RPOPLPUSH untuk menjamin pesan tidak hilang jika terjadi crash.
        """
        if not redis_client:
            raise HTTPException(status_code=503, detail="Redis unavailable")

        responsible_node = hasher.get_node(queue_name)
        
        if responsible_node != settings.node_id:
            print(f"[Queue] Proxying Consume '{queue_name}' -> {responsible_node}")
            json_resp, status_code = await forward_request(responsible_node, request)
            return JSONResponse(content=json_resp, status_code=status_code)

        try:
            main_queue = f"queue:{queue_name}"
            processing_queue = f"processing:{settings.node_id}:{queue_name}"
            
            # ATOMIC OPERATION: Pindahkan dari main ke processing queue
            # Menjamin pesan tetap ada di Redis jika node/network mati sebelum ACK
            message_raw = redis_client.rpoplpush(main_queue, processing_queue)
            
            if not message_raw:
                return {"status": "empty", "queue": queue_name}

            return {
                "status": "consumed",
                "node": settings.node_id,
                "data": json.loads(message_raw), # Aman: Menggunakan json.loads, bukan eval()
                "ack_token": {
                    "processing_queue": processing_queue,
                    "raw_data": message_raw
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/queue/ack")
    async def acknowledge(ack_data: dict):
        """
        Menghapus pesan dari antrean 'processing' setelah berhasil diproses.
        """
        if not redis_client:
            raise HTTPException(status_code=503, detail="Redis unavailable")
        
        try:
            p_queue = ack_data.get("processing_queue")
            raw_data = ack_data.get("raw_data")
            
            # Hapus pesan dari antrean sementara
            result = redis_client.lrem(p_queue, 1, raw_data)
            
            if result > 0:
                return {"status": "acknowledged", "message": "Pesan dihapus dari processing queue"}
            else:
                return {"status": "failed", "message": "Pesan tidak ditemukan di processing queue"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))