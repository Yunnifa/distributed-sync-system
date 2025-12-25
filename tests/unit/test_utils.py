import pytest
from src.utils.hashing import ConsistentHasher

def test_consistent_hashing_initialization():
    """Test that consistent hasher initializes correctly."""
    nodes = ["node1", "node2", "node3"]
    hasher = ConsistentHasher(nodes=nodes, replicas=3)
    
    assert len(hasher._sorted_keys) == 9  # 3 nodes * 3 replicas

def test_consistent_hashing_distribution():
    """Test that keys are distributed across nodes."""
    nodes = ["node1", "node2", "node3"]
    hasher = ConsistentHasher(nodes=nodes, replicas=5)
    
    # Test multiple keys
    assignments = {}
    for i in range(100):
        key = f"queue_{i}"
        node = hasher.get_node(key)
        assignments[node] = assignments.get(node, 0) + 1
    
    # Each node should get some keys (not perfect distribution but should be reasonable)
    assert len(assignments) == 3
    for node in nodes:
        assert assignments[node] > 0

def test_consistent_hashing_consistency():
    """Test that same key always maps to same node."""
    nodes = ["node1", "node2", "node3"]
    hasher = ConsistentHasher(nodes=nodes)
    
    key = "test_queue"
    node1 = hasher.get_node(key)
    node2 = hasher.get_node(key)
    node3 = hasher.get_node(key)
    
    assert node1 == node2 == node3

def test_cache_store_lru_eviction():
    """Test that LRU eviction works correctly."""
    from src.nodes.cache_node import CacheStore
    
    cache = CacheStore(maxsize=3)
    
    # Add 3 items
    cache.put("key1", "value1")
    cache.put("key2", "value2")
    cache.put("key3", "value3")
    
    # Access key1 to make it recently used
    cache.get("key1")
    
    # Add key4, should evict key2 (least recently used)
    cache.put("key4", "value4")
    
    assert cache.get("key1") == "value1"
    assert cache.get("key2") is None  # Evicted
    assert cache.get("key3") == "value3"
    assert cache.get("key4") == "value4"

def test_cache_store_invalidation():
    """Test cache invalidation."""
    from src.nodes.cache_node import CacheStore
    
    cache = CacheStore(maxsize=10)
    
    cache.put("key1", "value1", state="M")
    assert cache.get("key1") == "value1"
    
    # Invalidate
    cache.invalidate("key1")
    assert cache.get("key1") is None

def test_cache_store_state_tracking():
    """Test MESI-like state tracking."""
    from src.nodes.cache_node import CacheStore
    
    cache = CacheStore(maxsize=10)
    
    # Modified state
    cache.put("key1", "value1", state="M")
    assert cache.states["key1"] == "M"
    
    # Shared state
    cache.put("key2", "value2", state="S")
    assert cache.states["key2"] == "S"
    
    # Invalid state
    cache.put("key3", "value3", state="I")
    # Getting invalid key should return None
    assert cache.get("key3") is None

def test_metrics_tracking():
    """Test that metrics are tracked correctly."""
    from src.utils.metrics import CacheMetrics
    
    metrics = CacheMetrics()
    
    assert metrics.cache_hits == 0
    assert metrics.cache_misses == 0
    
    metrics.hit()
    metrics.hit()
    metrics.miss()
    
    assert metrics.cache_hits == 2
    assert metrics.cache_misses == 1
    
    stats = metrics.get_stats()
    assert stats["cache_hits"] == 2
    assert stats["cache_misses"] == 1
