from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/auth", tags=["Auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(req: LoginRequest):
    u = req.username.strip().lower()
    p = req.password.strip()
    
    if u == "admin" and p == "admin123":
        return {
            "status": "success",
            "role": "admin",
            "token": "admin-token-2026",
            "name": "Library Administrator",
            "theme": "indigo"
        }
    elif u in ["student", "user"] and p in ["user123", "student123"]:
        return {
            "status": "success",
            "role": "user",
            "token": "user-token-2026",
            "name": "Student Scholar",
            "theme": "navy"
        }
    else:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials. Use 'admin' / 'admin123' for Admin or 'student' / 'user123' for Student."
        )
