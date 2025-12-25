import pytest
import asyncio
from src.consensus.raft import RaftConsensus, RaftState

@pytest.mark.asyncio
async def test_raft_initialization():
    """Test that Raft initializes in FOLLOWER state."""
    raft = RaftConsensus()
    assert raft.state == RaftState.FOLLOWER
    assert raft.current_term == 0
    assert raft.voted_for is None
    assert len(raft.log) == 0

@pytest.mark.asyncio
async def test_raft_election_timeout():
    """Test that election timeout triggers candidate transition."""
    raft = RaftConsensus()
    
    # Set very short timeout for testing
    raft._min_election_timeout = 0.1
    raft._max_election_timeout = 0.2
    
    # Start election timer
    raft.reset_election_timer()
    
    # Wait for timeout
    await asyncio.sleep(0.3)
    
    # Should have transitioned to CANDIDATE
    assert raft.state == RaftState.CANDIDATE
    assert raft.current_term == 1
    assert raft.voted_for == raft.settings.node_id

@pytest.mark.asyncio
async def test_raft_vote_granting():
    """Test vote granting logic."""
    raft = RaftConsensus()
    
    # Should grant vote for first request in term 1
    response = await raft.handle_request_vote(
        term=1,
        candidate_id="node2",
        last_log_index=0,
        last_log_term=0
    )
    
    assert response["vote_granted"] is True
    assert response["term"] == 1
    assert raft.voted_for == "node2"

@pytest.mark.asyncio
async def test_raft_vote_denial_already_voted():
    """Test that node doesn't grant vote if already voted."""
    raft = RaftConsensus()
    
    # Grant vote to node2
    await raft.handle_request_vote(term=1, candidate_id="node2", last_log_index=0, last_log_term=0)
    
    # Try to vote for node3 in same term
    response = await raft.handle_request_vote(term=1, candidate_id="node3", last_log_index=0, last_log_term=0)
    
    assert response["vote_granted"] is False
    assert raft.voted_for == "node2"

@pytest.mark.asyncio
async def test_raft_step_down_on_higher_term():
    """Test that node steps down when seeing higher term."""
    raft = RaftConsensus()
    raft.current_term = 5
    raft.state = RaftState.CANDIDATE
    
    # Receive vote request with higher term
    response = await raft.handle_request_vote(term=10, candidate_id="node2", last_log_index=0, last_log_term=0)
    
    assert raft.state == RaftState.FOLLOWER
    assert raft.current_term == 10
    assert response["vote_granted"] is True

@pytest.mark.asyncio
async def test_raft_log_up_to_date_check():
    """Test log up-to-date comparison."""
    raft = RaftConsensus()
    
    # Add some log entries
    raft.log = [
        {"term": 1, "command": {"type": "test"}},
        {"term": 2, "command": {"type": "test"}},
        {"term": 2, "command": {"type": "test"}}
    ]
    
    # Candidate with higher term should be more up-to-date
    assert raft._is_log_up_to_date(last_log_index=3, last_log_term=3) is True
    
    # Candidate with same term but shorter log should not be up-to-date
    assert raft._is_log_up_to_date(last_log_index=2, last_log_term=2) is False
    
    # Candidate with same term and same length should be up-to-date
    assert raft._is_log_up_to_date(last_log_index=3, last_log_term=2) is True

@pytest.mark.asyncio
async def test_raft_append_entries_heartbeat():
    """Test handling of heartbeat AppendEntries."""
    raft = RaftConsensus()
    raft.state = RaftState.FOLLOWER
    raft.current_term = 1
    
    # Receive heartbeat from leader
    response = await raft.handle_append_entries(
        term=1,
        leader_id="node2",
        entries=[],
        prev_log_index=0,
        prev_log_term=0,
        leader_commit=0
    )
    
    assert response["success"] is True
    assert raft.leader_id == "node2"
    assert raft.state == RaftState.FOLLOWER

@pytest.mark.asyncio
async def test_raft_log_replication():
    """Test log entry replication."""
    raft = RaftConsensus()
    raft.state = RaftState.LEADER
    raft.current_term = 1
    
    # Leader appends entry
    command = {"type": "test", "data": "hello"}
    success = await raft.append_log_entry(command)
    
    assert success is True
    assert len(raft.log) == 1
    assert raft.log[0]["term"] == 1
    assert raft.log[0]["command"] == command

@pytest.mark.asyncio
async def test_raft_log_consistency_check():
    """Test log consistency checking in AppendEntries."""
    raft = RaftConsensus()
    raft.log = [
        {"term": 1, "command": {"type": "test1"}},
        {"term": 1, "command": {"type": "test2"}}
    ]
    
    # Consistency check should fail if prev_log_index is beyond log
    response = await raft.handle_append_entries(
        term=2,
        leader_id="node2",
        entries=[{"term": 2, "command": {"type": "test3"}}],
        prev_log_index=5,
        prev_log_term=1,
        leader_commit=0
    )
    
    assert response["success"] is False
    
    # Consistency check should fail if term doesn't match
    response = await raft.handle_append_entries(
        term=2,
        leader_id="node2",
        entries=[{"term": 2, "command": {"type": "test3"}}],
        prev_log_index=2,
        prev_log_term=2,  # Wrong term
        leader_commit=0
    )
    
    assert response["success"] is False
