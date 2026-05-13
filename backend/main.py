from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import (
    ToolCallRequest,
    GatewayResponse,
    AgentTextRequest,
    ApprovalRejectRequest,
)
from backend.gateway import check_tool_call
from backend.tool_executor import execute_tool
from backend.audit_logger import write_log, get_logs
from backend.fake_agent import FakeAgent
from backend.utils import normalize_tool_name, normalize_params
from backend.approval_store import (
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fake_agent = FakeAgent()


@app.get("/")
def index():
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
def agent_plan(request: AgentTextRequest):
    """
    模拟智能体规划接口。
    输入自然语言任务，只生成工具调用计划，不执行工具，也不经过网关。
    """
    plan_result = fake_agent.plan(request.user_input)

    return {
        "user": request.user,
        "agent_result": plan_result
    }


def _handle_tool_request(
    request: ToolCallRequest,
    original_input: str = None,
    agent_result: dict = None,
):
    """
    统一处理工具调用：
    1. 规范化工具名和参数
    2. 网关检查
    3. allow 则执行
    4. confirm 则进入人工确认队列
    5. deny 则拦截
    6. 全流程写入审计日志
    """
    normalized_tool = normalize_tool_name(request.tool)
    normalized_params = normalize_params(normalized_tool, request.params)

    normalized_request = ToolCallRequest(
        user=request.user,
        tool=normalized_tool,
        params=normalized_params
    )

    check_result = check_tool_call(normalized_request)

    # deny：直接拦截
    if check_result["decision"] == "deny":
        write_log(
            user=normalized_request.user,
            tool=normalized_request.tool,
            params=normalized_request.params,
            gateway_result=check_result,
            executed=False,
            original_input=original_input,
            message="工具调用已被安全网关拦截",
        )

        return {
            "executed": False,
            "message": "工具调用已被安全网关拦截",
            "agent_result": agent_result,
            "gateway_result": check_result,
            "tool_result": None,
            "pending_id": None
        }

    # confirm：进入人工确认队列
    if check_result["decision"] == "confirm":
        pending_id = create_pending_request(
            tool_request=normalized_request,
            gateway_result=check_result,
            original_input=original_input,
            agent_result=agent_result,
        )

        write_log(
            user=normalized_request.user,
            tool=normalized_request.tool,
            params=normalized_request.params,
            gateway_result=check_result,
            executed=False,
            original_input=original_input,
            message="工具调用需要人工确认，已进入 pending 队列",
            pending_id=pending_id,
        )

        return {
            "executed": False,
            "message": "工具调用需要人工确认，已进入 pending 队列",
            "agent_result": agent_result,
            "gateway_result": check_result,
            "tool_result": None,
            "pending_id": pending_id
        }

    # allow：直接执行
    tool_result = execute_tool(
        normalized_request.tool,
        normalized_request.params
    )

    write_log(
        user=normalized_request.user,
        tool=normalized_request.tool,
        params=normalized_request.params,
        gateway_result=check_result,
        executed=True,
        original_input=original_input,
        message="工具调用已通过安全检查并执行",
        tool_result=tool_result,
    )

    return {
        "executed": True,
        "message": "工具调用已通过安全检查并执行",
        "agent_result": agent_result,
        "gateway_result": check_result,
        "tool_result": tool_result,
        "pending_id": None
    }


@app.post("/agent/simulate")
def agent_simulate(request: AgentTextRequest):
    """
    模拟完整智能体调用流程。
    流程：
    1. 用户输入自然语言任务
    2. FakeAgent 生成工具调用计划
    3. 将工具调用请求交给安全网关
    4. 根据网关结果决定执行、拦截或进入人工确认
    5. 写入审计日志
    """
    plan_result = fake_agent.plan(request.user_input)

    if plan_result["status"] != "planned" or plan_result["tool_call"] is None:
        return {
            "executed": False,
            "message": "模拟智能体未能生成有效工具调用",
            "agent_result": plan_result,
            "gateway_result": None,
            "tool_result": None,
            "pending_id": None
        }

    tool_call = plan_result["tool_call"]

    tool_request = ToolCallRequest(
        user=request.user,
        tool=tool_call["tool_name"],
        params=tool_call["arguments"]
    )

    return _handle_tool_request(
        request=tool_request,
        original_input=request.user_input,
        agent_result=plan_result,
    )


@app.post("/agent/call")
def agent_call(request: ToolCallRequest):
    """
    结构化工具调用接口。
    这个接口不是自然语言输入，而是直接输入 tool 和 params。
    """
    return _handle_tool_request(request=request)


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