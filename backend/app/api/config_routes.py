from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from ..rag.engine import rag_engine
from .deps import require_admin

router = APIRouter(prefix="/api/config", tags=["Configuration"])

class KeyUpdateRequest(BaseModel):
    api_key: str

@router.get("/status")
async def get_config_status(force: bool = False):
    """
    Checks mandatory Google Gemini LLM connectivity and configuration state.
    Used by frontend gate to enforce compulsory Gemini key requirements.
    """
    status = rag_engine.validate_gemini_connection(force_check=force)
    return status

@router.post("/check")
async def force_check_connection():
    """Forces a live test against Google Gemini API."""
    status = rag_engine.validate_gemini_connection(force_check=True)
    return status

@router.post("/set-key")
async def set_api_key(req: KeyUpdateRequest, user: dict = Depends(require_admin)):
    """Administrator-only: updates active Gemini API key in running engine."""
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
    rag_engine.set_api_key(req.api_key.strip())
    status = rag_engine.validate_gemini_connection(force_check=True)
    return {
        "status": "success",
        "validation": status
    }
