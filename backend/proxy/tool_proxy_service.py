from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.capability.capability_compiler import compile_capability_contract
from backend.proxy.oauth_profile import build_agent_auth_profile
from backend.proxy.proxy_models import (
    ToolProxyAuthorizeRequest,
    ToolProxyAuthorizeResponse,
)
from backend.runtime.runtime_monitor import (
    build_runtime_security_graph,
    create_runtime_state,
    run_runtime_step,
)
from backend.sandbox.sandbox_policy import evaluate_sandbox_policy
from backend.task_session.session_executor import model_to_dict
from backend.tools.tool_executor import execute_tool


def _as_reason_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item) for item in value]

    return [str(value)]


def _deny_result(
    risk_score: int,
    reasons: List[str],
) -> Dict[str, Any]:
    return {
        "decision": "deny",
        "risk_score": risk_score,
        "reason": reasons,
    }


def _apply_sandbox_deny(
    result_dict: Dict[str, Any],
    sandbox_evaluation: Dict[str, Any],
) -> Dict[str, Any]:
    result_dict = dict(result_dict)

    result_dict["decision"] = "deny"
    result_dict["risk_score"] = max(
        int(result_dict.get("risk_score") or 0),
        int(sandbox_evaluation.get("risk_delta") or 100),
    )

    reasons = _as_reason_list(result_dict.get("reason"))
    reasons.append("Sandbox policy denied this tool call.")
    reasons.extend(_as_reason_list(sandbox_evaluation.get("reason")))

    result_dict["reason"] = reasons
    return result_dict


def authorize_tool_call(
    request: ToolProxyAuthorizeRequest,
) -> ToolProxyAuthorizeResponse:
    """
    Tool Proxy 核心服务函数。

    执行链路：

    External Agent
        -> Tool Proxy
        -> OAuth-style scope check
        -> Sandbox Policy
        -> Capability Contract
        -> Runtime Monitor
        -> allow / confirm / deny

    该函数的目标不是替代 Agent Runtime，而是提供外部 Agent 工具调用的
    统一安全入口。
    """

    contract = compile_capability_contract(
        user=request.user,
        original_task=request.original_task,
        max_steps=5,
        risk_budget=80,
    )

    runtime_state = create_runtime_state(contract)

    agent_auth_profile = build_agent_auth_profile(
        request=request,
        contract=contract,
    )

    sandbox_evaluation = evaluate_sandbox_policy(
        profile_name=request.sandbox_profile,
        tool=request.tool,
        params=request.params,
    )

    executed = False
    tool_result: Optional[Dict[str, Any]] = None

    # 1. OAuth-style scope 不足：直接拒绝，不进入真实工具执行。
    if agent_auth_profile.get("scope_decision") == "deny":
        missing_scopes = agent_auth_profile.get("missing_scopes", [])

        result_dict = _deny_result(
            risk_score=100,
            reasons=[
                "OAuth-style scope check failed.",
                "External Agent declared insufficient scopes for this tool call.",
                "Missing scopes: " + ", ".join([str(item) for item in missing_scopes]),
            ],
        )

    else:
        # 2. Capability Contract + Runtime Monitor 检查。
        runtime_result = run_runtime_step(
            state=runtime_state,
            tool=request.tool,
            params=request.params,
            input_labels=request.input_labels,
            input_from_steps=request.input_from_steps,
            output_content=None,
        )

        result_dict = model_to_dict(runtime_result)

        # 3. Sandbox Policy 进一步约束外部 Agent 工具调用。
        if sandbox_evaluation.get("decision") == "deny":
            result_dict = _apply_sandbox_deny(
                result_dict=result_dict,
                sandbox_evaluation=sandbox_evaluation,
            )

    # 4. 只有明确 allow 且 execute=True 时才真实执行工具。
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
        reason=_as_reason_list(result_dict.get("reason")),
        executed=executed,
        tool_result=tool_result,
        contract=model_to_dict(contract),
        runtime_state=model_to_dict(runtime_state),
        security_graph=security_graph,
        agent_auth_profile=agent_auth_profile,
        sandbox_profile=request.sandbox_profile,
        sandbox_evaluation=sandbox_evaluation,
    )
