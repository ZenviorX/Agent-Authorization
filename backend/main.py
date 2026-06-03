from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.routes.agent_routes import router as agent_router
from backend.routes.approval_routes import router as approval_router
from backend.routes.audit_routes import router as audit_router
from backend.routes.demo_routes import router as demo_router
from backend.routes.gateway_routes import router as gateway_router
from backend.routes.task_routes import router as task_router
from backend.routes.task_contract_routes import router as task_contract_router
from backend.routes.report_routes import router as report_router
from backend.routes.capability_routes import router as capability_router
from backend.routes.runtime_routes import router as runtime_router
from backend.routes.attack_chain_routes import router as attack_chain_router
from backend.routes.security_overview_routes import router as security_overview_router

app = FastAPI(
    title="AI Agent Auth Gateway",
    description="Authorization and safety gateway for AI Agent tool calls.",
    version="0.4.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_INDEX = BASE_DIR / "frontend" / "index.html"
FRONTEND_TASK_CHAIN = BASE_DIR / "frontend" / "task_chain.html"
FRONTEND_SECURITY_DASHBOARD = BASE_DIR / "frontend" / "security_dashboard.html"
FRONTEND_ATTACK_CHAIN_RUNTIME = BASE_DIR / "frontend" / "attack_chain_runtime.html"

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
app.include_router(task_router)
app.include_router(task_contract_router)
app.include_router(report_router)
app.include_router(capability_router)
app.include_router(runtime_router)
app.include_router(attack_chain_router)
app.include_router(security_overview_router)

@app.get("/")
def index():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)

    return {
        "message": "Frontend file is missing",
        "expected_path": str(FRONTEND_INDEX),
    }

@app.get("/task-chain")
def task_chain_page():
    if FRONTEND_TASK_CHAIN.exists():
        return FileResponse(FRONTEND_TASK_CHAIN)
    return {
        "message": "Task chain frontend file is missing",
        "expected_path": str(FRONTEND_TASK_CHAIN),
    }



@app.get("/attack-chain-runtime")
def attack_chain_runtime_page():
    if FRONTEND_ATTACK_CHAIN_RUNTIME.exists():
        return FileResponse(FRONTEND_ATTACK_CHAIN_RUNTIME)
    return {
        "message": "Attack chain runtime frontend file is missing",
        "expected_path": str(FRONTEND_ATTACK_CHAIN_RUNTIME),
    }


@app.get("/security-dashboard")
def security_dashboard_page():
    if FRONTEND_SECURITY_DASHBOARD.exists():
        return FileResponse(FRONTEND_SECURITY_DASHBOARD)
    return {
        "message": "Security dashboard frontend file is missing",
        "expected_path": str(FRONTEND_SECURITY_DASHBOARD),
    }


@app.get("/api/status")
def api_status():
    return {
        "message": "AI Agent Auth Gateway is running",
        "version": "0.4.0",
        "architecture": "Agent -> Gateway -> ToolExecutor",
    }



