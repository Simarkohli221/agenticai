from fastapi import FastAPI

app = FastAPI(
    title="Banking Transaction Investigation Agent",
    description="Agentic AI system for banking transaction investigation",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "banking-investigation-agent",
    }