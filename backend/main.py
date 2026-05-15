from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import (
    ToolCallRequest,
    GatewayResponse,
    AgentTextRequest,
    ApprovalRejectRequest,
)
from backend.agents import get_agent
from backend.gateway import check_tool_call, handle_tool_request
from backend.tools import execute_tool
from backend.audit import get_logs, write_log
from backend.approval import (
    create_pending_request,
    list_pending_requests,
    get_pending_request,
    pop_pending_request,
)


app = FastAPI(
    title="AI Agent Auth Gateway",
    description="面向 AI 智能体工具调用的授权与安全防护系统",
    version="0.3.0"
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

def build_tool_request_from_plan(
    request: AgentTextRequest,
    plan_result: dict,
) -> ToolCallRequest | None:
    tool_call = plan_result.get("tool_call")

    if plan_result.get("status") != "planned" or not tool_call:
        return None

    tool_name = tool_call.get("tool_name")
    if not tool_name:
        return None

    return ToolCallRequest(
        user=request.user,
        tool=tool_name,
        params=tool_call.get("arguments", {}),
    )


def plan_with_agent(request: AgentTextRequest, agent_type: str):
    try:
        agent = get_agent(agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return agent.plan(request.user_input)

@app.get("/")
def index():
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX)

    return {
        "message": "Frontend file is missing",
        "expected_path": str(FRONTEND_INDEX)
    }


@app.get("/api/status")
def api_status():
    return {
        "message": "AI Agent Auth Gateway is running",
        "version": "0.3.0",
        "task": "Task3 - 工具调用规范化与授权网关优化"
    }


@app.post("/gateway/check", response_model=GatewayResponse)
def gateway_check(request: ToolCallRequest):
    """
    单独测试安全网关。
    输入结构化工具调用请求，返回网关判断结果。
    """
    result = check_tool_call(request)

    return {
        "decision": result["decision"],
        "risk_score": result["risk_score"],
        "reason": result["reason"]
    }

@app.post("/agent/plan")
def agent_plan(request: AgentTextRequest, agent_type: str = "fake"):
    plan_result = plan_with_agent(request, agent_type)

    return {
        "user": request.user,
        "source": f"{agent_type}_agent",
        "agent_type": agent_type,
        "agent_result": plan_result,
    }


@app.post("/agent/simulate")
def agent_simulate(request: AgentTextRequest, agent_type: str = "fake"):
    plan_result = plan_with_agent(request, agent_type)
    tool_request = build_tool_request_from_plan(request, plan_result)

    if tool_request is None:
        return {
            "success": False,
            "executed": False,
            "message": "Agent 未生成有效工具调用",
            "source": f"{agent_type}_agent",
            "agent_type": agent_type,
            "agent_result": plan_result,
            "gateway_result": None,
            "tool_result": None,
            "pending_id": None,
        }

    return handle_tool_request(
        request=tool_request,
        original_input=request.user_input,
        agent_result=plan_result,
    )

@app.post("/demo/fake-agent/plan")
def fake_agent_plan(request: AgentTextRequest):
    """
    FakeAgent 演示接口。
    只用于模拟智能体规划，不代表真实大模型。
    """
    plan_result = plan_with_agent(request, "fake")

    return {
        "user": request.user,
        "source": "fake_agent_demo",
        "agent_result": plan_result
    }

@app.post("/llm/plan")
def llm_plan(request: AgentTextRequest):
    """
    真实大模型 Agent 规划接口。

    作用：
    1. 接收用户自然语言输入
    2. 调用真实大模型
    3. 生成结构化工具调用计划

    注意：
    这里只生成计划，不执行工具，也不绕过 Gateway。
    """
    plan_result = plan_with_agent(request, "llm")

    return {
        "user": request.user,
        "source": "llm_agent",
        "agent_result": plan_result,
    }

@app.post("/demo/fake-agent/simulate")
def fake_agent_simulate(request: AgentTextRequest):
    """
    FakeAgent 完整演示流程。

    这个接口用于原型演示：
    1. FakeAgent 根据自然语言生成工具调用
    2. 工具调用进入 Gateway
    3. Gateway 决定 allow / confirm / deny

    注意：FakeAgent 不是安全核心，Gateway 才是安全核心。
    """
    plan_result = plan_with_agent(request, "fake")

    tool_request = build_tool_request_from_plan(request, plan_result)

    if tool_request is None:
        return {
            "success": False,
            "executed": False,
            "message": "FakeAgent 未能生成有效工具调用",
            "source": "fake_agent_demo",
            "agent_result": plan_result,
            "gateway_result": None,
            "tool_result": None,
            "pending_id": None
        }

    return handle_tool_request(
        request=tool_request,
        original_input=request.user_input,
        agent_result=plan_result,
    )


@app.post("/agent/injection-demo")
def agent_injection_demo():
    """
    提示注入攻击链演示接口。

    演示流程：
    1. Agent 正常读取 public/injected_notice.txt；
    2. 网关认为 public 文件读取属于低风险操作，允许执行；
    3. 系统读取到文件内容后，发现其中包含提示注入指令；
    4. 模拟 Agent 被诱导生成新的危险工具调用：读取 secret/password.txt；
    5. 危险工具调用再次经过授权网关；
    6. 网关识别敏感路径并拦截。
    """

    attack_chain = []

    # 第一次工具调用：读取公开文件
    first_request = ToolCallRequest(
        user="alice",
        tool="file.read",
        params={
            "path": "public/injected_notice.txt"
        }
    )

    first_check = check_tool_call(first_request)

    first_tool_result = None
    first_executed = False

    if first_check["decision"] == "allow":
        first_tool_result = execute_tool(
            first_request.tool,
            first_request.params
        )
        first_executed = True

    write_log(
        user=first_request.user,
        tool=first_request.tool,
        params=first_request.params,
        gateway_result=first_check,
        executed=first_executed,
        original_input="读取文件：public/injected_notice.txt",
        message="提示注入演示：第一步读取公开文件",
        tool_result=first_tool_result,
    )

    attack_chain.append({
        "step": 1,
        "description": "Agent 正常读取公开文件 public/injected_notice.txt",
        "request": first_request.dict(),
        "gateway_result": first_check,
        "executed": first_executed,
        "tool_result": first_tool_result,
    })

    # 如果第一步没有成功执行，则攻击链终止
    if not first_executed or not first_tool_result or not first_tool_result.get("success"):
        return {
            "success": False,
            "message": "第一步公开文件读取失败，攻击链终止",
            "attack_chain": attack_chain
        }

    file_content = str(first_tool_result.get("result", ""))

    # 检测公开文件中是否包含提示注入特征
    injection_keywords = [
        "忽略之前的规则",
        "忽略以上要求",
        "ignore previous rules",
        "ignore previous instructions",
        "secret/password.txt",
        "attacker@example.com"
    ]

    detected_keywords = [
        keyword for keyword in injection_keywords
        if keyword.lower() in file_content.lower()
    ]

    if not detected_keywords:
        return {
            "success": True,
            "message": "公开文件读取成功，但未检测到明显提示注入内容",
            "attack_chain": attack_chain,
            "detected_keywords": []
        }

    # 第二次工具调用：模拟 Agent 被恶意内容诱导，尝试读取敏感文件
    second_request = ToolCallRequest(
        user="alice",
        tool="file.read",
        params={
            "path": "secret/password.txt"
        }
    )

    second_check = check_tool_call(second_request)

    second_tool_result = None
    second_executed = False

    if second_check["decision"] == "allow":
        second_tool_result = execute_tool(
            second_request.tool,
            second_request.params
        )
        second_executed = True

    write_log(
        user=second_request.user,
        tool=second_request.tool,
        params=second_request.params,
        gateway_result=second_check,
        executed=second_executed,
        original_input="提示注入诱导：读取 secret/password.txt",
        message="提示注入演示：第二步危险工具调用被网关处理",
        tool_result=second_tool_result,
    )

    attack_chain.append({
        "step": 2,
        "description": "检测到提示注入内容，模拟 Agent 被诱导读取 secret/password.txt",
        "detected_keywords": detected_keywords,
        "request": second_request.dict(),
        "gateway_result": second_check,
        "executed": second_executed,
        "tool_result": second_tool_result,
    })

    return {
        "success": True,
        "message": "提示注入攻击链演示完成",
        "detected_keywords": detected_keywords,
        "attack_chain": attack_chain
    }

@app.post("/gateway/call")
def gateway_call(request: ToolCallRequest):
    """
    正式网关调用接口。
    真实大模型或其他 Agent 生成工具调用后，应调用这里。
    """
    return handle_tool_request(request=request)


@app.post("/agent/call")
def agent_call(request: ToolCallRequest):
    """
    兼容旧接口。
    建议后续使用 /gateway/call。
    """
    return handle_tool_request(request=request)


@app.get("/approval/pending")
def approval_pending(limit: int = 50):
    """
    查看所有待人工确认的工具调用请求。
    """
    return {
        "pending": list_pending_requests(limit)
    }


@app.post("/approval/confirm/{pending_id}")
def approval_confirm(pending_id: str):
    """
    人工确认执行某个 pending 请求。
    确认后才真正调用 tool_executor.py。
    """
    pending = pop_pending_request(pending_id)

    if pending is None:
        return {
            "success": False,
            "message": "pending_id 不存在或已经被处理"
        }

    tool_request_data = pending["tool_request"]

    tool_request = ToolCallRequest(
        user=tool_request_data["user"],
        tool=tool_request_data["tool"],
        params=tool_request_data["params"]
    )

    tool_result = execute_tool(tool_request.tool, tool_request.params)

    gateway_result = pending["gateway_result"]
    gateway_result["decision"] = "confirmed"

    write_log(
        user=tool_request.user,
        tool=tool_request.tool,
        params=tool_request.params,
        gateway_result=gateway_result,
        executed=True,
        original_input=pending.get("original_input"),
        message="人工确认后执行工具调用",
        pending_id=pending_id,
        tool_result=tool_result,
    )

    return {
        "success": True,
        "message": "人工确认成功，工具调用已执行",
        "pending_id": pending_id,
        "tool_request": tool_request_data,
        "tool_result": tool_result
    }


@app.post("/approval/reject/{pending_id}")
def approval_reject(pending_id: str, request: ApprovalRejectRequest):
    """
    人工拒绝某个 pending 请求。
    """
    pending = pop_pending_request(pending_id)

    if pending is None:
        return {
            "success": False,
            "message": "pending_id 不存在或已经被处理"
        }

    tool_request_data = pending["tool_request"]

    gateway_result = pending["gateway_result"]
    gateway_result["decision"] = "rejected"

    write_log(
        user=tool_request_data["user"],
        tool=tool_request_data["tool"],
        params=tool_request_data["params"],
        gateway_result=gateway_result,
        executed=False,
        original_input=pending.get("original_input"),
        message=request.reason,
        pending_id=pending_id,
    )

    return {
        "success": True,
        "message": "已人工拒绝该工具调用",
        "pending_id": pending_id,
        "reason": request.reason
    }


@app.get("/audit/logs")
def audit_logs(limit: int = 50):
    """
    查看审计日志。
    """
    return {
        "logs": get_logs(limit)
    }
