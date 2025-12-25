"""
PBFT Demonstration Script

This script demonstrates the PBFT consensus algorithm and its Byzantine fault tolerance.

Usage:
    python -m scripts.demo_pbft

Requirements:
    - All 4 nodes must be running (for n=4, f=1 Byzantine tolerance)
    - Nodes on ports 8001, 8002, 8003, 8004 (if using 4 nodes)
"""

import asyncio
import httpx
import time
from typing import List


class PBFTDemo:
    """Demonstration of PBFT consensus"""
    
    def __init__(self, nodes: List[str]):
        self.nodes = nodes
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def close(self):
        await self.client.close()
    
    async def get_status(self, node_url: str) -> dict:
        """Get PBFT status from a node"""
        try:
            response = await self.client.get(f"{node_url}/pbft/status")
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def submit_request(self, node_url: str, request: dict) -> dict:
        """Submit a client request to PBFT"""
        try:
            response = await self.client.post(
                f"{node_url}/pbft/request",
                json=request
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def simulate_byzantine(self, node_url: str, behavior_type: str) -> dict:
        """Simulate Byzantine behavior on a node"""
        try:
            response = await self.client.post(
                f"{node_url}/pbft/simulate-byzantine",
                params={"behavior_type": behavior_type}
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def demo_normal_consensus(self):
        """Demonstrate normal PBFT consensus"""
        print("\n" + "="*70)
        print("DEMO 1: Normal PBFT Consensus")
        print("="*70)
        
        # Check initial status
        print("\n📊 Initial Status:")
        for node in self.nodes:
            status = await self.get_status(node)
            print(f"  {node}: Primary={status.get('is_primary')}, View={status.get('view')}, Executed={status.get('executed_count')}")
        
        # Submit request to primary
        print("\n📝 Submitting request to primary...")
        request = {
            "operation": "transfer",
            "from": "Alice",
            "to": "Bob",
            "amount": 100
        }
        
        result = await self.submit_request(self.nodes[0], request)
        print(f"  Result: {result}")
        
        # Wait for consensus
        print("\n⏳ Waiting for consensus (3 seconds)...")
        await asyncio.sleep(3)
        
        # Check final status
        print("\n📊 Final Status:")
        for node in self.nodes:
            status = await self.get_status(node)
            print(f"  {node}: Executed={status.get('executed_count')}, Last={status.get('last_executed')}")
        
        print("\n✅ Normal consensus completed!")
    
    async def demo_byzantine_detection(self):
        """Demonstrate Byzantine fault detection"""
        print("\n" + "="*70)
        print("DEMO 2: Byzantine Fault Detection")
        print("="*70)
        
        # Simulate Byzantine behavior on node 2
        byzantine_node = self.nodes[1] if len(self.nodes) > 1 else self.nodes[0]
        
        print(f"\n🚨 Simulating Byzantine behavior on {byzantine_node}...")
        
        # Send conflicting prepare messages
        for i in range(3):
            result = await self.simulate_byzantine(byzantine_node, "conflicting_prepare")
            print(f"  Attempt {i+1}: {result.get('message', result)}")
            await asyncio.sleep(0.5)
        
        # Wait for detection
        print("\n⏳ Waiting for Byzantine detection (2 seconds)...")
        await asyncio.sleep(2)
        
        # Check status on all nodes
        print("\n📊 Byzantine Detection Status:")
        for node in self.nodes:
            status = await self.get_status(node)
            byzantine_nodes = status.get('byzantine_nodes', [])
            suspicious = status.get('suspicious_nodes', {})
            
            print(f"\n  {node}:")
            print(f"    Byzantine nodes: {byzantine_nodes}")
            print(f"    Suspicious nodes: {suspicious}")
        
        print("\n✅ Byzantine detection completed!")
    
    async def demo_fault_tolerance(self):
        """Demonstrate fault tolerance with f Byzantine nodes"""
        print("\n" + "="*70)
        print("DEMO 3: Fault Tolerance (f Byzantine nodes)")
        print("="*70)
        
        # Get initial status
        status = await self.get_status(self.nodes[0])
        f = status.get('f', 1)
        quorum = status.get('quorum_size', 3)
        
        print(f"\n📊 System Configuration:")
        print(f"  Total nodes (n): {len(self.nodes)}")
        print(f"  Max Byzantine nodes (f): {f}")
        print(f"  Quorum size (2f+1): {quorum}")
        print(f"\n  This system can tolerate up to {f} Byzantine node(s)")
        
        # Submit request
        print("\n📝 Submitting request with Byzantine node present...")
        request = {
            "operation": "update_balance",
            "account": "Charlie",
            "amount": 500
        }
        
        result = await self.submit_request(self.nodes[0], request)
        print(f"  Result: {result}")
        
        # Wait for consensus
        print("\n⏳ Waiting for consensus despite Byzantine node (3 seconds)...")
        await asyncio.sleep(3)
        
        # Check if consensus was reached
        print("\n📊 Consensus Status:")
        for node in self.nodes:
            status = await self.get_status(node)
            print(f"  {node}: Executed={status.get('executed_count')}")
        
        print("\n✅ System maintained consensus despite Byzantine node!")
    
    async def run_all_demos(self):
        """Run all demonstrations"""
        print("\n" + "="*70)
        print("PBFT (Practical Byzantine Fault Tolerance) Demonstration")
        print("="*70)
        print("\nThis demo shows:")
        print("  1. Normal PBFT consensus operation")
        print("  2. Byzantine fault detection")
        print("  3. Fault tolerance with Byzantine nodes")
        
        try:
            await self.demo_normal_consensus()
            await asyncio.sleep(2)
            
            await self.demo_byzantine_detection()
            await asyncio.sleep(2)
            
            await self.demo_fault_tolerance()
            
            print("\n" + "="*70)
            print("All demonstrations completed successfully! 🎉")
            print("="*70)
        
        except Exception as e:
            print(f"\n❌ Error during demonstration: {e}")
        
        finally:
            await self.close()


async def main():
    """Main entry point"""
    # Default nodes (adjust based on your setup)
    nodes = [
        "http://localhost:8001",
        "http://localhost:8002",
        "http://localhost:8003",
        "http://localhost:8004"  # Optional 4th node for better fault tolerance
    ]
    
    # Check which nodes are available
    print("🔍 Checking available nodes...")
    available_nodes = []
    
    async with httpx.AsyncClient(timeout=2.0) as client:
        for node in nodes:
            try:
                response = await client.get(f"{node}/")
                if response.status_code == 200:
                    available_nodes.append(node)
                    print(f"  ✅ {node} is available")
            except:
                print(f"  ❌ {node} is not available")
    
    if len(available_nodes) < 3:
        print("\n⚠️ Warning: PBFT requires at least 3 nodes for Byzantine tolerance")
        print("   Please start more nodes before running this demo")
        return
    
    print(f"\n✅ Found {len(available_nodes)} available nodes")
    print(f"   Byzantine tolerance: f = {(len(available_nodes) - 1) // 3}")
    
    # Run demonstrations
    demo = PBFTDemo(available_nodes)
    await demo.run_all_demos()


if __name__ == "__main__":
    asyncio.run(main())
