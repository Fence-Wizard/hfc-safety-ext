from fastapi import FastAPI
from src.ext.routes import router as ext_router

app = FastAPI(title="HFC Master Orchestrator", version="0.1.0")

@app.get("/health")
async def health():
    return {"status": "ok"}

app.include_router(ext_router)
