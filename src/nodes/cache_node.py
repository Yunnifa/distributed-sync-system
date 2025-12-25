import redis
import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from collections import OrderedDict
from threading import Lock

from src.utils.config import get_settings
from src.utils.hashing import ConsistentHasher
from src.utils.metrics import metrics_store

# Dapatkan settings
settings = get_settings()

# Inisialisasi Redis Client
try:
    redis_client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=0,
        decode_responses=True # Penting agar output Redis berupa string
    )
    redis_client.ping()
    print(f"✅ Node {settings.node_id} berhasil terhubung ke Redis.")
except redis.exceptions.ConnectionError as e:
    print(f"❌ Node {settings.node_id} GAGAL terhubung ke Redis: {e}")
    redis_client = None

# Inisialisasi Consistent Hashing Ring
# Kita gunakan node_id sebagai nama node di ring
node_ids = [url.split('//')[1].split(':')[0] for url in settings.all_nodes]
hasher = ConsistentHasher(nodes=node_ids)

# --- Implementasi Cache Store dengan LRU Policy ---
class CacheStore:
    """
    Custom cache implementation with LRU eviction policy and proper hit/miss tracking.
    Thread-safe for concurrent access.
    """
    def __init__(self, maxsize=128):
        self.maxsize = maxsize
        self.cache = OrderedDict()  # Maintains insertion order
        self.lock = Lock()
        # Cache state tracking: Modified, Shared, Invalid (simplified MESI)
        self.states = {}  # {key: "M" | "S" | "I"}
    
    def get(self, key: str):
        """Get value from cache. Returns None if not found or invalid."""
        with self.lock:
            if key in self.cache and self.states.get(key) != "I":
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                metrics_store.hit()
                return self.cache[key]
            else:
                metrics_store.miss()
                return None
    
    def put(self, key: str, value: str, state: str = "M"):
        """
        Put value in cache with specified state.
        M = Modified (exclusive, dirty)
        S = Shared (clean, may exist in other caches)
        I = Invalid
        """
        with self.lock:
            if key in self.cache:
                # Update existing entry
                self.cache.move_to_end(key)
            else:
                # Add new entry
                if len(self.cache) >= self.maxsize:
                    # Evict least recently used
                    evicted_key, _ = self.cache.popitem(last=False)
                    if evicted_key in self.states:
                        del self.states[evicted_key]
            
            self.cache[key] = value
            self.states[key] = state
    
    def invalidate(self, key: str):
        """Mark a cache entry as invalid."""
        with self.lock:
            if key in self.states:
                self.states[key] = "I"
                # Optionally remove from cache entirely
                if key in self.cache:
                    del self.cache[key]
                    del self.states[key]
    
    def invalidate_all(self):
        """Invalidate all cache entries."""
        with self.lock:
            self.cache.clear()
            self.states.clear()
    
    def get_stats(self):
        """Get cache statistics."""
        with self.lock:
            return {
                "size": len(self.cache),
                "maxsize": self.maxsize,
                "states": dict(self.states)
            }

# Create global cache instance
cache_store = CacheStore(maxsize=128)

# Ini adalah 'database' palsu kita.
# Di dunia nyata, ini adalah database SQL atau NoSQL.
mock_db = {
    "item:123": "Ini adalah data untuk item 123",
    "item:456": "Data rahasia untuk item 456"
}

def get_data_from_db(key: str) -> str | None:
    """
    Fungsi ini mengambil data dari 'database' palsu.
    """
    print(f"CACHE MISS: Mengambil data '{key}' dari DB.")
    return mock_db.get(key)

# --- Fungsi untuk Rute API ---
def add_cache_routes(app: FastAPI):

    @app.get("/cache/{key}")
    def read_cache(key: str):
        """
        Membaca data. Akan mencoba dari cache terlebih dahulu.
        """
        # Try to get from cache first
        cached_value = cache_store.get(key)
        
        if cached_value is not None:
            return {
                "key": key,
                "data": cached_value,
                "source": "cache (LRU)",
                "cache_state": cache_store.states.get(key, "unknown")
            }
        
        # Cache miss - get from database
        data = get_data_from_db(key)
        
        if data:
            # Store in cache with Shared state (read from DB)
            cache_store.put(key, data, state="S")
            return {
                "key": key,
                "data": data,
                "source": "database (cached for future)"
            }
        else:
            raise HTTPException(status_code=404, detail="Data not found")

    @app.post("/cache/{key}")
    async def write_cache(key: str, value: dict, background_tasks: BackgroundTasks):
        """
        Menulis/memperbarui data.
        Ini akan meng-invalidate cache di semua node lain.
        """
        from src.communication.message_passing import broadcast_invalidate
        
        # 1. Tulis data ke 'database' palsu
        new_data = value.get("data")
        mock_db[key] = new_data
        
        # 2. Update cache LOKAL dengan Modified state
        cache_store.put(key, new_data, state="M")
        
        # 3. Kirim invalidasi ke semua PEER 
        # Kita gunakan BackgroundTasks agar request ini tidak memblokir respons
        background_tasks.add_task(broadcast_invalidate, key)
        
        return {
            "status": "data updated",
            "key": key,
            "new_data": new_data,
            "cache_state": "M"
        }

    @app.post("/cache/invalidate/{key}")
    def invalidate_cache(key: str):
        """
        Endpoint internal yang dipanggil oleh node lain
        untuk meng-invalidate cache mereka.
        """
        print(f"INVALIDATE diterima untuk key: {key}")
        cache_store.invalidate(key)
        return {"status": "cache invalidated", "key": key}

    @app.get("/metrics")
    def get_metrics():
        """
        Endpoint untuk memenuhi syarat Performance Monitoring 
        """
        stats = metrics_store.get_stats()
        stats["cache_stats"] = cache_store.get_stats()
        return stats