# src/utils/config.py
import os
from functools import lru_cache

class Settings:
    def __init__(self):
        self.port: int = int(os.getenv("PORT", "8000"))
        self.node_id: str = os.getenv("NODE_ID", "default_node")
        
        nodes_str = os.getenv("ALL_NODES", f"http://localhost:{self.port}")
        self.all_nodes: list[str] = [node.strip() for node in nodes_str.split(',')]
        
        self.self_url = f"http://{self.node_id}:{self.port}"
        
        # Daftar node lain (peers) - FIXED: filter based on port instead of full URL
        # This handles cases where ALL_NODES uses 127.0.0.1, localhost, or node names
        self.peers: list[str] = []
        for node in self.all_nodes:
            # Extract port from node URL (e.g., http://127.0.0.1:8001 -> 8001)
            try:
                node_port = int(node.split(':')[-1])
                if node_port != self.port:
                    self.peers.append(node)
            except (ValueError, IndexError):
                # If we can't parse port, include it in peers to be safe
                self.peers.append(node)
        
        self.redis_host: str = os.getenv("REDIS_HOST", "redis")
        self.redis_port: int = int(os.getenv("REDIS_PORT", "6379"))

@lru_cache()
def get_settings():
    return Settings()