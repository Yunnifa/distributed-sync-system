from locust import HttpUser, task, between
import random

class DistributedSystemUser(HttpUser):
    """
    Locust load test for the distributed sync system.
    Tests locks, queue, and cache under concurrent load.
    """
    wait_time = between(0.1, 0.5)  # Wait 0.1-0.5 seconds between tasks
    
    def on_start(self):
        """Called when a simulated user starts."""
        self.user_id = f"user_{random.randint(1000, 9999)}"
    
    @task(3)
    def test_cache_read(self):
        """Test cache read operations (higher weight = more frequent)."""
        keys = ["item:123", "item:456", f"item:{random.randint(100, 200)}"]
        key = random.choice(keys)
        
        with self.client.get(f"/cache/{key}", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.success()  # Not found is acceptable
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def test_cache_write(self):
        """Test cache write operations."""
        key = f"item:{random.randint(100, 200)}"
        data = {"data": f"Test data from {self.user_id}"}
        
        with self.client.post(f"/cache/{key}", json=data, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Cache write failed: {response.status_code}")
    
    @task(2)
    def test_queue_produce(self):
        """Test queue message production."""
        queue_name = f"test_queue_{random.randint(1, 5)}"
        message = {"sender": self.user_id, "data": f"Message {random.randint(1, 1000)}"}
        
        with self.client.post(f"/queue/{queue_name}", json=message, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Queue produce failed: {response.status_code}")
    
    @task(2)
    def test_queue_consume(self):
        """Test queue message consumption."""
        queue_name = f"test_queue_{random.randint(1, 5)}"
        
        with self.client.get(f"/queue/{queue_name}", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
                # In real scenario, would ACK the message here
            elif response.status_code == 404:
                response.success()  # Empty queue is acceptable
            else:
                response.failure(f"Queue consume failed: {response.status_code}")
    
    @task(1)
    def test_lock_acquire_release(self):
        """Test lock acquisition and release."""
        lock_name = f"test_lock_{random.randint(1, 3)}"
        lock_type = random.choice(["shared", "exclusive"])
        
        # Try to acquire lock
        with self.client.post(
            f"/lock/{lock_name}?lock_type={lock_type}",
            catch_response=True
        ) as response:
            if response.status_code == 200:
                # Successfully acquired, now release
                with self.client.delete(f"/lock/{lock_name}", catch_response=True) as release_response:
                    if release_response.status_code == 200:
                        response.success()
                    else:
                        response.failure(f"Lock release failed: {release_response.status_code}")
            elif response.status_code == 423:
                # Lock held by others - this is expected under load
                response.success()
            elif response.status_code == 503:
                # No leader elected yet or forwarding failed
                response.success()
            else:
                response.failure(f"Lock acquire unexpected status: {response.status_code}")
    
    @task(1)
    def test_metrics(self):
        """Test metrics endpoint."""
        with self.client.get("/metrics", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics failed: {response.status_code}")
    
    @task(1)
    def test_lock_status(self):
        """Test lock status endpoint."""
        lock_name = f"test_lock_{random.randint(1, 3)}"
        
        with self.client.get(f"/lock/{lock_name}", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Lock status failed: {response.status_code}")


class StressTestUser(HttpUser):
    """
    Stress test with more aggressive load patterns.
    """
    wait_time = between(0.01, 0.1)  # Very short wait time
    
    @task
    def stress_test_cache(self):
        """Hammer the cache with rapid requests."""
        key = f"stress_item:{random.randint(1, 10)}"
        
        if random.random() < 0.8:  # 80% reads
            self.client.get(f"/cache/{key}")
        else:  # 20% writes
            self.client.post(f"/cache/{key}", json={"data": f"stress_{random.randint(1, 1000)}"})
    
    @task
    def stress_test_queue(self):
        """Hammer the queue with rapid messages."""
        queue_name = "stress_queue"
        
        if random.random() < 0.5:
            self.client.post(f"/queue/{queue_name}", json={"data": f"stress_{random.randint(1, 1000)}"})
        else:
            self.client.get(f"/queue/{queue_name}")
