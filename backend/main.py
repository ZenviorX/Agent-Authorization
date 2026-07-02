from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.routes.approval_routes import router as approval_router
from backend.routes.audit_routes import router as audit_router
from backend.routes.gateway_routes import router as gateway_router
from backend.routes.task_contract_routes import router as task_contract_router
from backend.routes.report_routes import router as report_router
from backend.routes.capability_routes import router as capability_router
from backend.routes.runtime_routes import router as runtime_router
from backend.routes.attack_chain_routes import router as attack_chain_router
from backend.routes.security_overview_routes import router as security_overview_router
from backend.routes.demo_routes import router as demo_router
from backend.routes.sandbox_evidence_routes import router as sandbox_evidence_router
from backend.routes.showcase_report_routes import router as showcase_report_router
from backend.routes.agent_runtime_routes import router as agent_runtime_router
from backend.routes.tool_proxy_routes import router as tool_proxy_router
from backend.routes.external_agent_routes import router as external_agent_router
from backend.routes.oauth_comparison_routes import router as oauth_comparison_router
from backend.routes.research_eval_routes import router as research_eval_router
from backend.routes.research_strategy_routes import router as research_strategy_router
from backend.routes.test_results_routes import router as test_results_router
from backend.routes.docker_sandbox_routes import router as docker_sandbox_router
from backend.routes.native_sandbox_routes import router as native_sandbox_router
from backend.routes.frontend_data_routes import router as frontend_data_router
from backend.routes.two_phase_tool_proxy_routes import router as two_phase_tool_proxy_router
from backend.routes.capability_token_routes import router as capability_token_router
from backend.routes.llm_tool_call_routes import router as llm_tool_call_router


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
FRONTEND_SANDBOX_DASHBOARD = BASE_DIR / "frontend" / "sandbox_dashboard.html"
FRONTEND_AUTHORIZED_EVIDENCE = BASE_DIR / "frontend" / "authorized_evidence.html"
FRONTEND_SHOWCASE = BASE_DIR / "frontend" / "showcase.html"
FRONTEND_TOOL_PROXY = BASE_DIR / "frontend" / "tool_proxy.html"


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
        "null",
    ],
    allow_origin_regex=r"^http://(127\.0\.0\.1|localhost):\d+$",
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
app.include_router(task_contract_router)
app.include_router(report_router)
app.include_router(capability_router)
app.include_router(runtime_router)
app.include_router(attack_chain_router)
app.include_router(security_overview_router)
app.include_router(sandbox_evidence_router)
app.include_router(showcase_report_router)
app.include_router(agent_runtime_router)
app.include_router(tool_proxy_router)
app.include_router(external_agent_router)
app.include_router(oauth_comparison_router)
app.include_router(research_eval_router)
app.include_router(research_strategy_router)
app.include_router(two_phase_tool_proxy_router)
app.include_router(capability_token_router)
app.include_router(llm_tool_call_router)

# -----------------------------
# Frontend local runtime data APIs
# -----------------------------

app.include_router(frontend_data_router)

# -----------------------------
# Real execution sandbox APIs
# -----------------------------

app.include_router(docker_sandbox_router)
app.include_router(native_sandbox_router)

# -----------------------------
# Independent test result APIs
# -----------------------------

app.include_router(test_results_router)

# -----------------------------
# Demo-only APIs
# -----------------------------

app.include_router(demo_router)

# -----------------------------
# Frontend pages
# -----------------------------

@app.get("/")
def index():
    return _serve_frontend_html(
        FRONTEND_INDEX,
        "Frontend file is missing",
    )


@app.get("/showcase")
def showcase_page():
    return _serve_frontend_html(
        FRONTEND_SHOWCASE,
        "Showcase frontend file is missing",
    )


@app.get("/tool-proxy")
def tool_proxy_page():
    return _serve_frontend_html(
        FRONTEND_TOOL_PROXY,
        "Tool Proxy frontend file is missing",
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


@app.get("/sandbox-dashboard")
def sandbox_dashboard_page():
    return _serve_frontend_html(
        FRONTEND_SANDBOX_DASHBOARD,
        "Sandbox frontend file is missing",
    )


@app.get("/authorized-evidence")
def authorized_evidence_page():
    return _serve_frontend_html(
        FRONTEND_AUTHORIZED_EVIDENCE,
        "Authorized evidence frontend file is missing",
    )


# -----------------------------
# Health check
# -----------------------------

@app.get("/api/status")
def api_status():
    return {
        "message": "AI Agent Auth Gateway is running",
        "version": "0.5.0",
        "architecture": {
            "core": (
                "External caller -> Agent Runtime / Gateway -> "
                "Runtime Monitor -> ToolExecutor"
            ),
            "real_agent": (
                "MultiStepLLMAgent -> Capability Contract -> "
                "Runtime Monitor -> Hybrid Sandbox Executor"
            ),
            "demo": "FakeAgent -> Demo API -> Gateway -> ToolExecutor",
        },
        "registered_core_features": [
            "gateway",
            "capability_contract",
            "runtime_monitor",
            "attack_chain_detector",
            "sandbox_evidence",
            "docker_sandbox_executor",
            "native_subprocess_sandbox",
            "showcase_report",
            "agent_runtime",
            "tool_proxy",
            "external_agent_adapter",
            "independent_test_runner",
            "frontend_local_runtime_data",
        ],
        "note": (
            "FakeAgent is demo-only. Real Agent runtime APIs are exposed under "
            "/agent-runtime and still require Gateway / Runtime Monitor checks."
        ),
    }


# === Teacher review cleanup: legacy frontend route notice ===
# The project has migrated from FastAPI-served static HTML pages to
# a Vite + React frontend. Keep these compatibility routes friendly.
def _install_legacy_frontend_route_notice():
    try:
        from fastapi.responses import JSONResponse
    except Exception:
        return

    legacy_paths = {
        "/",
        "/showcase",
        "/task-chain",
        "/attack-chain-runtime",
        "/security-dashboard",
        "/sandbox-dashboard",
        "/authorized-evidence",
        "/tool-proxy",
    }

    try:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) not in legacy_paths
        ]
    except Exception:
        return

    async def legacy_frontend_notice():
        return JSONResponse(
            {
                "message": "旧版后端静态页面入口已废弃，请访问新版 React 前端。",
                "frontend": "http://127.0.0.1:5173",
                "backend": "http://127.0.0.1:8000",
                "docs": "http://127.0.0.1:8000/docs",
                "recommended_demo_mode": "授权演示 -> 真沙箱执行（自动选择）",
            }
        )

    for path in sorted(legacy_paths):
        app.add_api_route(path, legacy_frontend_notice, methods=["GET"], include_in_schema=False)


_install_legacy_frontend_route_notice()
# === End teacher review cleanup ===

