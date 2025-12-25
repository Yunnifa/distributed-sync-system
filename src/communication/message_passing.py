import aiohttp
import asyncio

async def broadcast_invalidate(key: str):
    """
    Mengirimkan request invalidate cache ke semua peer.
    Kita tidak perlu menunggu respons (fire and forget).
    """
    from src.utils.config import get_settings
    settings = get_settings()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for peer in settings.peers:
            url = f"{peer}/cache/invalidate/{key}"
            tasks.append(session.post(url, timeout=aiohttp.ClientTimeout(total=0.5)))
        
        # Jalankan semua request secara paralel
        # Kita tidak peduli hasilnya, yang penting terkirim
        await asyncio.gather(*tasks, return_exceptions=True)

async def send_rpc_to_peer(peer_url: str, endpoint: str, payload: dict) -> dict:
    """
    Mengirim satu RPC ke satu peer dan mengembalikan respons JSON-nya.
    Akan menangani timeout dan error koneksi.
    """
    # Use aiohttp with 3 second timeout for reliable communication
    timeout = aiohttp.ClientTimeout(total=3.0)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        try:
            async with session.post(f"{peer_url}{endpoint}", json=payload) as response:
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError as e:
            print(f"TIMEOUT RPC ke {peer_url}{endpoint}: {e}")
            return {"error": "timeout", "vote_granted": False, "success": False}
        except aiohttp.ClientConnectionError as e:
            print(f"CONNECTION ERROR RPC ke {peer_url}{endpoint}: {e}")
            return {"error": "connection_error", "vote_granted": False, "success": False}
        except Exception as e:
            print(f"RPC GAGAL ke {peer_url}{endpoint}: {type(e).__name__}: {e}")
            return {"error": str(e), "vote_granted": False, "success": False}