from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.routes.agent_routes import router as agent_router
from backend.routes.approval_routes import router as approval_router
from backend.routes.audit_routes import router as audit_router
from backend.routes.demo_routes import router as demo_router
from backend.routes.gateway_routes import router as gateway_router


app = FastAPI(
    title="AI Agent Auth Gateway",
    description="Authorization and safety gateway for AI Agent tool calls.",
    version="0.4.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_INDEX = BASE_DIR / "frontend" / "index.html"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agent_router)
app.include_router(gateway_router)
app.include_router(demo_router)
app.include_router(approval_router)
app.include_router(audit_router)


@app.get("/")
def index():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)

    return {
        "message": "Frontend file is missing",
        "expected_path": str(FRONTEND_INDEX),
    }


@app.get("/api/status")
def api_status():
    return {
        "message": "AI Agent Auth Gateway is running",
        "version": "0.4.0",
        "architecture": "Agent -> Gateway -> ToolExecutor",
    }
