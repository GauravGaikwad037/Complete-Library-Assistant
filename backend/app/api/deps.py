from typing import Optional, Dict
from fastapi import Header, HTTPException

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, str]:
    """Extracts authenticated user context from token header."""
    if not authorization:
        # Default student identity if no token header provided
        return {"role": "user", "username": "student", "name": "Student Scholar"}
        
    token = authorization.replace("Bearer ", "").strip()
    if "admin" in token.lower():
        return {"role": "admin", "username": "admin", "name": "Library Administrator"}
    elif "student" in token.lower() or "user" in token.lower():
        return {"role": "user", "username": "student", "name": "Student Scholar"}
    else:
        return {"role": "user", "username": "student", "name": "Student Scholar"}

def require_admin(authorization: Optional[str] = Header(None)) -> Dict[str, str]:
    """Guards administrator-only routes against unauthorized access."""
    user = get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Access forbidden: Administrator privileges required for this operation."
        )
    return user
