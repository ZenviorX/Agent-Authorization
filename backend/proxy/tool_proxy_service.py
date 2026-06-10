from __future__ import annotations

from typing import Any, Dict, Optional

from backend.capability.capability_compiler import compile_capability_contract
from backend.runtime.runtime_monitor import (
    build_runtime_security_graph,
    create_runtime_state,
    run_runtime_step,
)
from backend.task_session.session_executor import model_to_dict
from backend.tools.tool_executor import execute_tool
from backend.proxy.proxy_models import (
    ToolProxyAuthorizeRequest,
    ToolProxyAuthorizeResponse,
)


def authorize_tool_call(
    request: ToolProxyAuthorizeRequest,
) -> ToolProxyAuthorizeResponse:
    """
    Tool Proxy 核心服务函数。

    作用：
    1. 接收外部 Agent / 前端调试台发来的工具调用请求；
    2. 根据 original_task 生成 Capability Contract；
    3. 创建 RuntimeTaskState；
    4. 使用 run_runtime_step() 执行安全检查；
    5. 如果 execute=True 且 decision=allow，则真实执行沙箱工具；
    6. 返回 allow / confirm / deny、风险分、原因、合约和安全图谱。

    注意：
    第一版主要目标是做“安全检查入口”，不是替代原来的 Agent Runtime。
    """

    contract = compile_capability_contract(
        user=request.user,
        original_task=request.original_task,
        max_steps=5,
        risk_budget=80,
    )

    runtime_state = create_runtime_state(contract)

    runtime_result = run_runtime_step(
        state=runtime_state,
        tool=request.tool,
        params=request.params,
        input_labels=request.input_labels,
        input_from_steps=request.input_from_steps,
        output_content=None,
    )

    result_dict = model_to_dict(runtime_result)

    executed = False
    tool_result: Optional[Dict[str, Any]] = None

    if request.execute and result_dict.get("decision") == "allow":
        tool_result = execute_tool(
            tool=request.tool,
            params=request.params,
        )
        executed = bool(tool_result.get("success") is True)

    security_graph = build_runtime_security_graph(runtime_state)

    return ToolProxyAuthorizeResponse(
        success=True,
        mode="tool_proxy_authorize",
        decision=str(result_dict.get("decision", "deny")),
        risk_score=int(result_dict.get("risk_score", 0) or 0),
        reason=list(result_dict.get("reason", []) or []),
        executed=executed,
        tool_result=tool_result,
        contract=model_to_dict(contract),
        runtime_state=model_to_dict(runtime_state),
        security_graph=security_graph,
    )
