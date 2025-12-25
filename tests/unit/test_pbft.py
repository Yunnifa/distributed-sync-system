import pytest
import asyncio
from src.consensus.pbft import PBFTConsensus, PBFTMessage, PBFTPhase


@pytest.mark.asyncio
async def test_pbft_initialization():
    """Test PBFT initialization"""
    pbft = PBFTConsensus()
    
    assert pbft.view == 0
    assert pbft.sequence == 0
    assert pbft.primary_id is not None
    assert pbft.f >= 0
    assert pbft.quorum_size == 2 * pbft.f + 1


@pytest.mark.asyncio
async def test_pbft_digest_computation():
    """Test digest computation is consistent"""
    pbft = PBFTConsensus()
    
    request1 = {"operation": "transfer", "amount": 100}
    request2 = {"operation": "transfer", "amount": 100}
    request3 = {"operation": "transfer", "amount": 200}
    
    digest1 = pbft.compute_digest(request1)
    digest2 = pbft.compute_digest(request2)
    digest3 = pbft.compute_digest(request3)
    
    # Same request should have same digest
    assert digest1 == digest2
    
    # Different request should have different digest
    assert digest1 != digest3


@pytest.mark.asyncio
async def test_pbft_message_signature():
    """Test message signing and verification"""
    pbft = PBFTConsensus()
    
    message = PBFTMessage(
        msg_type="prepare",
        view=0,
        sequence=1,
        digest="test_digest",
        node_id="node1"
    )
    
    # Sign message
    message.signature = pbft.sign_message(message)
    
    # Verify signature
    assert pbft.verify_signature(message) is True
    
    # Tamper with message
    message.digest = "tampered_digest"
    
    # Verification should fail
    assert pbft.verify_signature(message) is False


@pytest.mark.asyncio
async def test_pbft_byzantine_detection():
    """Test Byzantine behavior detection"""
    pbft = PBFTConsensus()
    
    # Initially not Byzantine
    assert pbft.is_byzantine("malicious_node") is False
    
    # Detect suspicious behavior multiple times
    pbft.detect_byzantine_behavior("malicious_node", "Invalid signature")
    assert pbft.is_byzantine("malicious_node") is False
    
    pbft.detect_byzantine_behavior("malicious_node", "Conflicting message")
    assert pbft.is_byzantine("malicious_node") is False
    
    pbft.detect_byzantine_behavior("malicious_node", "Double voting")
    
    # Should be marked as Byzantine after threshold
    assert pbft.is_byzantine("malicious_node") is True


@pytest.mark.asyncio
async def test_pbft_is_primary():
    """Test primary node detection"""
    pbft = PBFTConsensus()
    
    # Check if current node is primary
    is_primary = pbft.is_primary()
    
    # Should be boolean
    assert isinstance(is_primary, bool)
    
    # Primary ID should match one of the nodes
    assert pbft.primary_id is not None


@pytest.mark.asyncio
async def test_pbft_quorum_calculation():
    """Test quorum size calculation"""
    pbft = PBFTConsensus()
    
    n = len(pbft.settings.all_nodes)
    f = (n - 1) // 3
    expected_quorum = 2 * f + 1
    
    assert pbft.f == f
    assert pbft.quorum_size == expected_quorum
    
    # Quorum should be more than half
    assert pbft.quorum_size > n / 2


@pytest.mark.asyncio
async def test_pbft_message_serialization():
    """Test message serialization and deserialization"""
    message = PBFTMessage(
        msg_type="commit",
        view=2,
        sequence=5,
        digest="abc123",
        node_id="node2",
        signature="sig123"
    )
    
    # Serialize
    msg_dict = message.to_dict()
    
    assert msg_dict["msg_type"] == "commit"
    assert msg_dict["view"] == 2
    assert msg_dict["sequence"] == 5
    
    # Deserialize
    restored = PBFTMessage.from_dict(msg_dict)
    
    assert restored.msg_type == message.msg_type
    assert restored.view == message.view
    assert restored.sequence == message.sequence
    assert restored.digest == message.digest


@pytest.mark.asyncio
async def test_pbft_status():
    """Test PBFT status reporting"""
    pbft = PBFTConsensus()
    
    status = pbft.get_status()
    
    assert "view" in status
    assert "sequence" in status
    assert "primary" in status
    assert "is_primary" in status
    assert "f" in status
    assert "quorum_size" in status
    assert "byzantine_nodes" in status
    assert "suspicious_nodes" in status
    
    # Check types
    assert isinstance(status["view"], int)
    assert isinstance(status["is_primary"], bool)
    assert isinstance(status["byzantine_nodes"], list)
    assert isinstance(status["suspicious_nodes"], dict)
