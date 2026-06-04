from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.routes.approval_routes import router as approval_router
from backend.routes.audit_routes import router as audit_router
from backend.routes.gateway_routes import router as gateway_router
from backend.routes.task_routes import router as task_router
from backend.routes.task_contract_routes import router as task_contract_router
from backend.routes.report_routes import router as report_router
from backend.routes.capability_routes import router as capability_router
from backend.routes.runtime_routes import router as runtime_router
from backend.routes.attack_chain_routes import router as attack_chain_router
from backend.routes.security_overview_routes import router as security_overview_router
from backend.routes.demo_routes import router as demo_router


app = FastAPI(
    title="AI Agent Auth Gateway",
    description=(
        "Authorization and safety gateway for AI Agent tool calls. "
        "Core gateway APIs are separated from demo-only FakeAgent interfaces."
    ),
    version="0.5.0",
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_INDEX = BASE_DIR / "frontend" / "index.html"
FRONTEND_TASK_CHAIN = BASE_DIR / "frontend" / "task_chain.html"
FRONTEND_SECURITY_DASHBOARD = BASE_DIR / "frontend" / "security_dashboard.html"
FRONTEND_ATTACK_CHAIN_RUNTIME = BASE_DIR / "frontend" / "attack_chain_runtime.html"


def _serve_frontend_html(path: Path, missing_message: str):
    if path.exists():
        return FileResponse(path)

    return {
        "message": missing_message,
        "expected_path": str(path),
    }


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

# -----------------------------
# Core project APIs
# -----------------------------
app.include_router(gateway_router)
app.include_router(approval_router)
app.include_router(audit_router)
app.include_router(task_router)
app.include_router(task_contract_router)
app.include_router(report_router)
app.include_router(capability_router)
app.include_router(runtime_router)
app.include_router(attack_chain_router)
app.include_router(security_overview_router)

# -----------------------------
# Demo-only APIs
# -----------------------------
app.include_router(demo_router)


@app.get("/")
def index():
    return _serve_frontend_html(
        FRONTEND_INDEX,
        "Frontend file is missing",
    )


@app.get("/task-chain")
def task_chain_page():
    return _serve_frontend_html(
        FRONTEND_TASK_CHAIN,
        "Task chain frontend file is missing",
    )


@app.get("/attack-chain-runtime")
def attack_chain_runtime_page():
    return _serve_frontend_html(
        FRONTEND_ATTACK_CHAIN_RUNTIME,
        "Attack chain runtime frontend file is missing",
    )


@app.get("/security-dashboard")
def security_dashboard_page():
    return _serve_frontend_html(
        FRONTEND_SECURITY_DASHBOARD,
        "Security dashboard frontend file is missing",
    )


@app.get("/api/status")
def api_status():
    return {
        "message": "AI Agent Auth Gateway is running",
        "version": "0.5.0",
        "architecture": {
            "core": "External caller -> Gateway -> ToolExecutor",
            "demo": "FakeAgent -> Demo API -> Gateway -> ToolExecutor",
        },
        "note": "FakeAgent is demo-only and is not part of the core gateway API.",
    }