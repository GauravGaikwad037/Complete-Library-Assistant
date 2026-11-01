from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from .api.auth_routes import router as auth_router
from .api.admin_routes import router as admin_router
from .api.user_routes import router as user_router
from .api.config_routes import router as config_router

app = FastAPI(
    title="VidyaAI — Smart Library Assistant with RAG & Gemini LLM",
    description="Dual-Portal (Admin & Student) AI Library Management System with explainable RAG and compulsory Google Gemini LLM.",
    version="2.0.0"
)

# CORS configuration for Vite frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(user_router)
app.include_router(config_router)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "VidyaAI Smart Library Assistant",
        "version": "2.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
