"""
PBFT Node - API endpoints for PBFT consensus
"""
import asyncio
from fastapi import FastAPI, Request, HTTPException

from src.consensus.pbft import PBFTConsensus, PBFTMessage

# Create global PBFT instance
pbft_instance = PBFTConsensus()


def add_pbft_routes(app: FastAPI):
    """Add PBFT-related routes to the FastAPI app"""
    
    @app.on_event("startup")
    async def startup_pbft():
        """Initialize PBFT on startup"""
        print(f"✅ PBFT initialized for node {pbft_instance.settings.node_id}")
    
    @app.post("/pbft/request")
    async def pbft_client_request(request: Request):
        """
        Client submits a request to PBFT consensus
        
        This is the entry point for clients to submit requests.
        If this node is primary, it starts consensus.
        If this node is a replica, it forwards to primary.
        """
        payload = await request.json()
        
        result = await pbft_instance.handle_client_request(payload)
        return result
    
    @app.post("/pbft/message")
    async def pbft_protocol_message(request: Request):
        """
        Internal endpoint for PBFT protocol messages
        
        Handles pre-prepare, prepare, and commit messages from other nodes.
        """
        payload = await request.json()
        
        try:
            message = PBFTMessage.from_dict(payload)
            
            if message.msg_type == "pre-prepare":
                await pbft_instance.handle_pre_prepare(message)
            elif message.msg_type == "prepare":
                await pbft_instance.handle_prepare(message)
            elif message.msg_type == "commit":
                await pbft_instance.handle_commit(message)
            else:
                raise HTTPException(status_code=400, detail=f"Unknown message type: {message.msg_type}")
            
            return {"status": "processed", "msg_type": message.msg_type}
        
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/pbft/status")
    async def pbft_status():
        """
        Get current PBFT status
        
        Returns information about current view, primary, executed requests,
        and any detected Byzantine nodes.
        """
        return pbft_instance.get_status()
    
    @app.post("/pbft/simulate-byzantine")
    async def simulate_byzantine_behavior(behavior_type: str = "conflicting_prepare"):
        """
        Simulate Byzantine (malicious) behavior for testing
        
        Types:
        - conflicting_prepare: Send conflicting prepare messages
        - invalid_signature: Send message with invalid signature
        - double_prepare: Send multiple prepares for same sequence
        """
        from src.utils.config import get_settings
        settings = get_settings()
        
        if behavior_type == "conflicting_prepare":
            # Send prepare with wrong digest
            fake_message = PBFTMessage(
                msg_type="prepare",
                view=pbft_instance.view,
                sequence=pbft_instance.sequence,
                digest="fake_digest_12345",
                node_id=settings.node_id
            )
            fake_message.signature = pbft_instance.sign_message(fake_message)
            
            await pbft_instance.broadcast_message(fake_message)
            
            return {
                "status": "byzantine_behavior_simulated",
                "type": behavior_type,
                "message": "Sent conflicting prepare message"
            }
        
        elif behavior_type == "invalid_signature":
            # Send message with invalid signature
            fake_message = PBFTMessage(
                msg_type="prepare",
                view=pbft_instance.view,
                sequence=pbft_instance.sequence,
                digest="some_digest",
                node_id=settings.node_id,
                signature="invalid_signature_xyz"
            )
            
            await pbft_instance.broadcast_message(fake_message)
            
            return {
                "status": "byzantine_behavior_simulated",
                "type": behavior_type,
                "message": "Sent message with invalid signature"
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"Unknown behavior type: {behavior_type}")
