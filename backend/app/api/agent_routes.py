from fastapi import APIRouter, HTTPException
from ..models.schemas import AgentQueryRequest, AgentResponse
from ..agents.gemini_client import agent_engine
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/agent", tags=["Agent"])

class KeyUpdateRequest(BaseModel):
    api_key: str

@router.post("/chat", response_model=AgentResponse)
async def chat_with_agent(req: AgentQueryRequest):
    try:
        res = agent_engine.execute_query(
            query=req.query,
            history=req.history,
            agent_mode=req.agent_mode or "concierge",
            custom_key=req.api_key
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent execution error: {str(e)}")

@router.get("/status")
async def get_agent_status():
    has_key = bool(agent_engine.api_key)
    return {
        "status": "operational",
        "has_gemini_key": has_key,
        "active_model": agent_engine.model_name,
        "mode": "Gemini Live ReAct" if has_key else "Autonomous Deterministic Agent",
        "available_tools": [
            "semantic_catalog_search",
            "physical_shelf_locator",
            "circulation_policy_officer",
            "academic_citation_generator",
            "book_study_companion",
            "study_room_reservation"
        ]
    }

@router.post("/set-key")
async def set_gemini_key(req: KeyUpdateRequest):
    if not req.api_key or len(req.api_key.strip()) < 10:
        raise HTTPException(status_code=400, detail="Invalid API key format")
    agent_engine.update_api_key(req.api_key.strip())
    return {
        "status": "updated",
        "has_gemini_key": True,
        "message": "Gemini API key successfully configured and active."
    }
