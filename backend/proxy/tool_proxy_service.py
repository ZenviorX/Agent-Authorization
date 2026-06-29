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
from backend.sandbox.real_sandbox_executor import execute_tool_in_real_sandbox
from backend.sandbox.sandbox_policy import evaluate_sandbox_policy
from backend.guardrails.task_boundary_guard import evaluate_task_boundary_policy
from backend.guardrails.authorization_trace import build_authorization_trace
from backend.guardrails.capability_token import issue_capability_token, validate_capability_token_for_request, mark_capability_token_consumed
from backend.task_session.session_executor import model_to_dict


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


def _apply_task_boundary_decision(
    result_dict: Dict[str, Any],
    task_boundary_evaluation: Dict[str, Any],
) -> Dict[str, Any]:
    result_dict = dict(result_dict)

    boundary_decision = str(task_boundary_evaluation.get("decision") or "allow")
    current_decision = str(result_dict.get("decision") or "allow")

    if boundary_decision == "deny":
        result_dict["decision"] = "deny"
    elif boundary_decision == "confirm" and current_decision == "allow":
        result_dict["decision"] = "confirm"

    result_dict["risk_score"] = max(
        int(result_dict.get("risk_score") or 0),
        int(task_boundary_evaluation.get("risk_delta") or 0),
    )

    reasons = _as_reason_list(result_dict.get("reason"))
    reasons.append("Task Boundary Guard evaluated this tool call.")
    reasons.extend(_as_reason_list(task_boundary_evaluation.get("reason")))

    result_dict["reason"] = reasons
    return result_dict


def _apply_capability_token_decision(
    result_dict: Dict[str, Any],
    capability_token_validation: Dict[str, Any],
) -> Dict[str, Any]:
    result_dict = dict(result_dict)

    if capability_token_validation.get("decision") == "deny":
        result_dict["decision"] = "deny"

    result_dict["risk_score"] = max(
        int(result_dict.get("risk_score") or 0),
        int(capability_token_validation.get("risk_delta") or 0),
    )

    reasons = _as_reason_list(result_dict.get("reason"))
    reasons.append("Capability Token validation evaluated this tool call.")
    reasons.extend(_as_reason_list(capability_token_validation.get("reason")))

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
        -> Hybrid Real Sandbox Executor
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

    task_boundary_evaluation = evaluate_task_boundary_policy(
        original_task=request.original_task,
        tool=request.tool,
        params=request.params,
        input_labels=request.input_labels,
    )

    capability_token_validation = validate_capability_token_for_request(
        token=getattr(request, "capability_token", ""),
        user=request.user,
        agent_platform=request.agent_platform,
        original_task=request.original_task,
        expected_contract=task_boundary_evaluation.get("capability_contract", {}),
        tool=request.tool,
        params=request.params,
        sandbox_profile=request.sandbox_profile,
        require_token=bool(request.execute),
    )

    executed = False
    tool_result: Optional[Dict[str, Any]] = None
    sandbox_evidence: Optional[Dict[str, Any]] = None

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

        if task_boundary_evaluation.get("decision") in {"deny", "confirm"}:
            result_dict = _apply_task_boundary_decision(
                result_dict=result_dict,
                task_boundary_evaluation=task_boundary_evaluation,
            )

        if capability_token_validation.get("decision") == "deny":
            result_dict = _apply_capability_token_decision(
                result_dict=result_dict,
                capability_token_validation=capability_token_validation,
            )

        # 3. Sandbox Policy 进一步约束外部 Agent 工具调用。
        if sandbox_evaluation.get("decision") == "deny":
            result_dict = _apply_sandbox_deny(
                result_dict=result_dict,
                sandbox_evaluation=sandbox_evaluation,
            )

    # 4. 只有明确 allow 且 execute=True 时才进入真执行沙箱。
    #    默认 auto：有 Docker 用 Docker；无 Docker 自动降级到无需安装的 native_subprocess sandbox。
    if request.execute and result_dict.get("decision") == "allow":
        real_sandbox_result = execute_tool_in_real_sandbox(
            tool=request.tool,
            params=request.params,
            profile_name=request.sandbox_profile,
            prefer="auto",
        )
        sandbox_evidence = real_sandbox_result.get("sandbox_evidence")
        tool_result = real_sandbox_result.get("tool_result") or {
            "success": bool(real_sandbox_result.get("success")),
            "result": real_sandbox_result.get("result"),
        }
        executed = bool(tool_result.get("success") is True)

    security_graph = build_runtime_security_graph(runtime_state)

    if executed and capability_token_validation.get("decision") == "allow":
        capability_token_validation = dict(capability_token_validation)
        capability_token_validation["consumption"] = mark_capability_token_consumed(
            getattr(request, "capability_token", "")
        )
        reasons = _as_reason_list(capability_token_validation.get("reason"))
        reasons.append("Capability token was consumed after successful real sandbox execution.")
        capability_token_validation["reason"] = reasons

    if str(result_dict.get("decision", "deny")) == "allow" and not bool(request.execute):
        capability_token = issue_capability_token(
            user=request.user,
            agent_platform=request.agent_platform,
            original_task=request.original_task,
            capability_contract=task_boundary_evaluation.get("capability_contract", {}),
            tool=request.tool,
            params=request.params,
            sandbox_profile=request.sandbox_profile,
        )
        capability_token["issued"] = True
    elif str(result_dict.get("decision", "deny")) == "allow" and bool(request.execute):
        capability_token = {
            "token_type": "agentguard_capability_token",
            "issued": False,
            "reason": "Execution phase consumes capability token and does not issue a new token.",
        }
    else:
        capability_token = {
            "token_type": "agentguard_capability_token",
            "issued": False,
            "reason": "Capability token is only issued when final decision is allow.",
        }

    authorization_trace = build_authorization_trace(
        agent_auth_profile=agent_auth_profile,
        capability_token_validation=capability_token_validation,
        task_boundary_evaluation=task_boundary_evaluation,
        sandbox_evaluation=sandbox_evaluation,
        final_decision=str(result_dict.get("decision", "deny")),
        final_risk_score=int(result_dict.get("risk_score", 0) or 0),
        executed=executed,
    )

    return ToolProxyAuthorizeResponse(
        success=True,
        authorization_trace=authorization_trace,
        capability_token_validation=capability_token_validation,
        capability_token=capability_token,
        mode="tool_proxy_authorize",
        decision=str(result_dict.get("decision", "deny")),
        risk_score=int(result_dict.get("risk_score", 0) or 0),
        reason=_as_reason_list(result_dict.get("reason")),
        executed=executed,
        tool_result=tool_result,
        sandbox_evidence=sandbox_evidence,
        contract=model_to_dict(contract),
        runtime_state=model_to_dict(runtime_state),
        security_graph=security_graph,
        agent_auth_profile=agent_auth_profile,
        sandbox_profile=request.sandbox_profile,
        sandbox_evaluation=sandbox_evaluation,
    )
