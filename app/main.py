import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.investigation import router as investigation_router
from app.api.account import router as account_router

app = FastAPI(
    title="Banking Transaction Investigation Agent",
    description="Agentic AI system for banking transaction investigation",
    version="0.1.0",
)

# CORS is restricted to an explicit allowlist, configurable via
# CORS_ALLOWED_ORIGINS (comma-separated), defaulting to the Streamlit
# frontend's local dev origins only. This is a browser-enforced
# policy - it does not affect the frontend's own requests.requests()
# calls (server-to-server, not subject to CORS) or this project's
# TestClient-based test suites. No production origin is assumed or
# hardcoded; deploying elsewhere requires explicitly setting this
# environment variable.
_default_cors_origins = "http://localhost:8501,http://127.0.0.1:8501"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", _default_cors_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(investigation_router)
app.include_router(account_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "banking-investigation-agent",
    }