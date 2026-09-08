from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.investigation import router as investigation_router

app = FastAPI(
    title="Banking Transaction Investigation Agent",
    description="Agentic AI system for banking transaction investigation",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(investigation_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "banking-investigation-agent",
    }