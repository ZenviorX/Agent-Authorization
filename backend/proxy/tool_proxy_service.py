from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.audit import write_log
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
from backend.runtime.flow_label import analyze_output_labels
from backend.runtime.task_state import RuntimeTaskState
from backend.sandbox.real_sandbox_executor import execute_tool_in_real_sandbox
from backend.sandbox.sandbox_policy import evaluate_sandbox_policy
from backend.guardrails.task_boundary_guard import evaluate_task_boundary_policy
from backend.guardrails.authorization_trace import build_authorization_trace
from backend.guardrails.capability_token import issue_capability_token, validate_capability_token_for_request, mark_capability_token_consumed
from backend.task_session.session_executor import model_to_dict
from backend.task_session.task_store import (
    load_session,
    save_session,
)
from backend.task_session.task_store import create_data_reference
from backend.task_session.task_store import create_approval_ticket
from backend.task_session.task_store import ApprovalTicketBindingError, ApprovalTicketNotFoundError, ApprovalTicketStateError, consume_approval_ticket, get_approval_ticket, validate_approval_ticket_for_request
from backend.audit.trusted_audit_store import append_trusted_audit_event
from backend.audit.decision_snapshot import build_decision_snapshot
from backend.revocation.revocation_store import RevocationStoreError, assert_subject_not_revoked


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


def _write_proxy_audit_log(
    request: ToolProxyAuthorizeRequest,
    result_dict: Dict[str, Any],
    executed: bool,
    tool_result: Optional[Dict[str, Any]],
) -> None:
    """
    Write both compatibility logs and a trusted,
    reproducible authorization decision snapshot.
    """
    try:
        write_log(
            user=request.user,
            tool=request.tool,
            params=request.params,
            gateway_result={
                "decision": str(
                    result_dict.get(
                        "decision",
                        "deny",
                    )
                ),
                "risk_score": int(
                    result_dict.get(
                        "risk_score",
                        0,
                    )
                    or 0
                ),
                "reason": _as_reason_list(
                    result_dict.get(
                        "reason"
                    )
                ),
                "risk_level": None,
            },
            executed=executed,
            original_input=(
                request.original_task
            ),
            message=(
                "Tool Proxy execute=true entered "
                "the sandbox."
                if request.execute
                else "Tool Proxy authorization "
                "result was recorded."
            ),
            tool_result=tool_result,
        )

    except Exception:
        # Compatibility JSONL logging remains best-effort.
        pass

    task_handle = str(
        getattr(
            request,
            "task_handle",
            "",
        )
        or ""
    ).strip()

    if not task_handle:
        return

    metadata = dict(
        request.external_agent_metadata
        or {}
    )

    approval_ticket = str(
        getattr(
            request,
            "approval_ticket",
            "",
        )
        or ""
    ).strip()

    if approval_ticket:
        event_type = (
            "approval.execution_result"
            if request.execute
            else "approval.authorization_result"
        )

    elif request.execute:
        event_type = (
            "tool.execution_result"
        )

    else:
        event_type = (
            "authorization.result"
        )

    decision_snapshot = (
        build_decision_snapshot(
            request=request,
            result_dict=result_dict,
            executed=executed,
            tool_result=tool_result,
        )
    )

    append_trusted_audit_event(
        task_handle=task_handle,
        user=request.user,
        event_type=event_type,
        payload={
            "tool": request.tool,
            "params": dict(
                request.params or {}
            ),
            "decision": str(
                result_dict.get(
                    "decision",
                    "deny",
                )
            ),
            "risk_score": int(
                result_dict.get(
                    "risk_score",
                    0,
                )
                or 0
            ),
            "reason": _as_reason_list(
                result_dict.get(
                    "reason"
                )
            ),
            "executed": bool(
                executed
            ),
            "authorization_phase": str(
                metadata.get(
                    "authorization_phase"
                )
                or (
                    "execute"
                    if request.execute
                    else "prepare"
                )
            ),
            "data_refs": list(
                metadata.get(
                    "trusted_data_refs"
                )
                or []
            ),
            "input_from_steps": list(
                request.input_from_steps
                or []
            ),
            "input_labels": list(
                request.input_labels
                or []
            ),
            "approval_reference_hash": (
                decision_snapshot[
                    "request_summary"
                ].get(
                    "approval_reference_hash",
                    "",
                )
            ),
            "tool_result": tool_result,
            "decision_snapshot": (
                decision_snapshot
            ),
        },
    )


def _sandbox_entered(real_sandbox_result: Dict[str, Any]) -> bool:
    """
    Execution phase means the authorized call entered the sandbox runner.

    Token replay protection must not depend only on tool_result.success. A tool may
    execute and return success=false, but the capability token has still been spent.
    Existing regression tests also expect execute=true + allow to mark executed when
    the sandbox creates evidence.
    """

    evidence = real_sandbox_result.get("sandbox_evidence")
    if isinstance(evidence, dict):
        if evidence.get("executed") is True:
            return True
        if evidence.get("run_id") or evidence.get("started_at"):
            return True

    return bool(real_sandbox_result.get("success") is True)


def _runtime_state_from_dict(
    data: Dict[str, Any],
) -> RuntimeTaskState:
    if hasattr(RuntimeTaskState, "model_validate"):
        return RuntimeTaskState.model_validate(data)

    return RuntimeTaskState.parse_obj(data)


def _load_task_context(
    request: ToolProxyAuthorizeRequest,
):
    task_handle = request.task_handle.strip()

    if not task_handle:
        contract = compile_capability_contract(
            user=request.user,
            original_task=request.original_task,
            max_steps=5,
            risk_budget=80,
        )

        return (
            None,
            0,
            contract,
            create_runtime_state(contract),
        )

    session, version = load_session(
        task_handle=task_handle,
        expected_user=request.user,
    )

    # ???????????????
    request.original_task = session.original_input

    if session.runtime_state:
        runtime_state = _runtime_state_from_dict(
            session.runtime_state
        )
        contract = runtime_state.contract
    else:
        contract = compile_capability_contract(
            user=session.user,
            original_task=session.original_input,
            max_steps=5,
            risk_budget=80,
        )
        runtime_state = create_runtime_state(contract)

    return (
        session,
        version,
        contract,
        runtime_state,
    )


def _extract_tool_output_text(
    tool_result: Optional[Dict[str, Any]],
) -> str:
    if not isinstance(tool_result, dict):
        return ""

    value = tool_result.get("result")

    if value is None:
        return ""

    if isinstance(value, str):
        return value

    try:
        import json

        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
        )
    except (TypeError, ValueError):
        return str(value)


def _extract_resource_from_request(
    request: ToolProxyAuthorizeRequest,
) -> Optional[str]:
    params = request.params or {}

    for key in (
        "path",
        "file_path",
        "resource",
        "filename",
        "url",
    ):
        value = params.get(key)

        if value:
            return str(value)

    return None


def _update_runtime_labels_from_tool_output(
    *,
    runtime_state: RuntimeTaskState,
    request: ToolProxyAuthorizeRequest,
    tool_result: Optional[Dict[str, Any]],
    executed: bool,
) -> List[str]:
    """
    ?????????????????

    ???? AgentGuard ???????????
    ????? Agent ??? input_labels?
    """
    if not executed:
        return []

    if not runtime_state.steps:
        return []

    runtime_record = runtime_state.steps[-1]

    output_text = _extract_tool_output_text(
        tool_result
    )

    labels = analyze_output_labels(
        content=output_text,
        base_labels=list(
            runtime_record.output_labels or []
        ),
        resource=_extract_resource_from_request(
            request
        ),
    )

    runtime_record.output_labels = list(labels)
    runtime_record.executed = True

    runtime_state.data_labels_by_step[
        runtime_record.step_index
    ] = list(labels)

    return list(labels)

def _find_approved_runtime_step(
    runtime_state: RuntimeTaskState,
    step_index: int,
):
    for step in runtime_state.steps:
        if int(step.step_index) == int(step_index):
            return step

    raise ApprovalTicketBindingError(
        "The approval ticket points to a runtime "
        "step that does not exist"
    )


def _current_approval_status(
    *,
    approval_ticket: str,
    task_handle: str,
    user: str,
) -> str:
    try:
        record = get_approval_ticket(
            approval_ticket=approval_ticket,
            expected_task_handle=task_handle,
            expected_user=user,
        )

        return str(
            record.get("status")
            or ""
        )

    except Exception:
        return "invalid"


def _recompute_runtime_final_decision(
    runtime_state: RuntimeTaskState,
) -> str:
    if any(
        step.decision == "deny"
        for step in runtime_state.steps
    ):
        return "deny"

    if any(
        step.requires_confirmation
        and not step.confirmed
        for step in runtime_state.steps
    ):
        return "confirm"

    return "allow"


def _authorize_approved_tool_call(
    request: ToolProxyAuthorizeRequest,
) -> ToolProxyAuthorizeResponse:
    """
    Execute the exact call bound to an approved ticket.

    Prepare phase validates the ticket and issues a
    capability token. Execute phase atomically consumes
    the ticket before entering the sandbox.
    """
    (
        trusted_session,
        task_version,
        contract,
        runtime_state,
    ) = _load_task_context(request)

    if trusted_session is None:
        raise ApprovalTicketBindingError(
            "An approval ticket requires a "
            "trusted task session"
        )

    task_handle = str(
        trusted_session.task_handle
        or request.task_handle
        or ""
    ).strip()

    approval_ticket = str(
        request.approval_ticket
        or ""
    ).strip()

    metadata = (
        request.external_agent_metadata
        or {}
    )

    data_refs = list(
        metadata.get("trusted_data_refs")
        or []
    )

    authorization_phase = str(
        metadata.get("authorization_phase")
        or ""
    )

    agent_auth_profile = build_agent_auth_profile(
        request=request,
        contract=contract,
    )

    sandbox_evaluation = evaluate_sandbox_policy(
        profile_name=request.sandbox_profile,
        tool=request.tool,
        params=request.params,
    )

    task_boundary_evaluation = (
        evaluate_task_boundary_policy(
            original_task=request.original_task,
            tool=request.tool,
            params=request.params,
            input_labels=request.input_labels,
        )
    )

    capability_token_validation = (
        validate_capability_token_for_request(
            token=getattr(
                request,
                "capability_token",
                "",
            ),
            user=request.user,
            agent_platform=request.agent_platform,
            original_task=request.original_task,
            expected_contract=(
                task_boundary_evaluation.get(
                    "capability_contract",
                    {},
                )
            ),
            tool=request.tool,
            params=request.params,
            sandbox_profile=(
                request.sandbox_profile
            ),
            require_token=bool(
                request.execute
            ),
        )
    )

    approval_record = None
    approval_error = ""

    try:
        approval_record = (
            validate_approval_ticket_for_request(
                approval_ticket=approval_ticket,
                task_handle=task_handle,
                user=request.user,
                tool=request.tool,
                params=dict(
                    request.params or {}
                ),
                data_refs=data_refs,
            )
        )

    except (
        ApprovalTicketNotFoundError,
        ApprovalTicketBindingError,
        ApprovalTicketStateError,
    ) as exc:
        approval_error = str(exc)

    approval_status = (
        str(
            approval_record.get("status")
            or ""
        )
        if approval_record is not None
        else _current_approval_status(
            approval_ticket=approval_ticket,
            task_handle=task_handle,
            user=request.user,
        )
    )

    result_dict = {
        "decision": "allow",
        "risk_score": 0,
        "reason": [
            (
                "The exact tool call is covered by "
                "a server-issued human approval ticket."
            )
        ],
    }

    if approval_record is not None:
        result_dict["risk_score"] = int(
            next(
                (
                    step.risk_score
                    for step in runtime_state.steps
                    if int(step.step_index)
                    == int(
                        approval_record[
                            "step_index"
                        ]
                    )
                ),
                0,
            )
            or 0
        )

        reviewer = str(
            approval_record.get(
                "decided_by"
            )
            or ""
        )

        if reviewer:
            result_dict["reason"].append(
                "Approved by OAuth subject: "
                + reviewer
            )

    if approval_error:
        result_dict = _deny_result(
            risk_score=100,
            reasons=[
                "Approval ticket validation failed.",
                approval_error,
            ],
        )

    elif (
        agent_auth_profile.get(
            "scope_decision"
        )
        == "deny"
    ):
        missing_scopes = list(
            agent_auth_profile.get(
                "missing_scopes",
                [],
            )
        )

        result_dict = _deny_result(
            risk_score=100,
            reasons=[
                "OAuth-style scope check failed.",
                (
                    "Missing scopes: "
                    + ", ".join(
                        str(item)
                        for item in missing_scopes
                    )
                ),
            ],
        )

    elif (
        sandbox_evaluation.get("decision")
        == "deny"
    ):
        result_dict = _apply_sandbox_deny(
            result_dict=result_dict,
            sandbox_evaluation=(
                sandbox_evaluation
            ),
        )

    elif (
        task_boundary_evaluation.get(
            "decision"
        )
        == "deny"
    ):
        result_dict = _deny_result(
            risk_score=max(
                100,
                int(
                    task_boundary_evaluation.get(
                        "risk_delta",
                        0,
                    )
                    or 0
                ),
            ),
            reasons=[
                (
                    "Task Boundary Guard produced "
                    "a hard deny that human approval "
                    "cannot override."
                )
            ]
            + _as_reason_list(
                task_boundary_evaluation.get(
                    "reason"
                )
            ),
        )

    elif (
        capability_token_validation.get(
            "decision"
        )
        == "deny"
    ):
        result_dict = (
            _apply_capability_token_decision(
                result_dict=result_dict,
                capability_token_validation=(
                    capability_token_validation
                ),
            )
        )

    executed = False
    tool_result: Optional[
        Dict[str, Any]
    ] = None
    sandbox_evidence: Optional[
        Dict[str, Any]
    ] = None
    data_ref = ""

    if (
        bool(request.execute)
        and result_dict.get("decision")
        == "allow"
        and approval_record is not None
    ):
        try:
            consumed_record = (
                consume_approval_ticket(
                    approval_ticket=(
                        approval_ticket
                    ),
                    task_handle=task_handle,
                    user=request.user,
                    tool=request.tool,
                    params=dict(
                        request.params or {}
                    ),
                    data_refs=data_refs,
                )
            )

        except (
            ApprovalTicketNotFoundError,
            ApprovalTicketBindingError,
            ApprovalTicketStateError,
        ) as exc:
            result_dict = _deny_result(
                risk_score=100,
                reasons=[
                    (
                        "Approval ticket could not "
                        "be consumed."
                    ),
                    str(exc),
                ],
            )

        else:
            approval_status = str(
                consumed_record.get(
                    "status"
                )
                or "consumed"
            )

            approved_step = (
                _find_approved_runtime_step(
                    runtime_state,
                    int(
                        consumed_record[
                            "step_index"
                        ]
                    ),
                )
            )

            real_sandbox_result = (
                execute_tool_in_real_sandbox(
                    tool=request.tool,
                    params=request.params,
                    profile_name=(
                        request.sandbox_profile
                    ),
                    prefer="auto",
                )
            )

            sandbox_evidence = (
                real_sandbox_result.get(
                    "sandbox_evidence"
                )
            )

            tool_result = (
                real_sandbox_result.get(
                    "tool_result"
                )
                or {
                    "success": bool(
                        real_sandbox_result.get(
                            "success"
                        )
                    ),
                    "result": (
                        real_sandbox_result.get(
                            "result"
                        )
                    ),
                }
            )

            executed = _sandbox_entered(
                real_sandbox_result
            )

            approved_step.decision = "allow"
            approved_step.executed = executed
            approved_step.blocked = False
            approved_step.requires_confirmation = False
            approved_step.confirmed = True
            approved_step.confirmation_status = (
                "approved"
            )

            approved_reason = (
                "Human approval ticket was "
                "validated and consumed."
            )

            if (
                approved_reason
                not in approved_step.reason
            ):
                approved_step.reason.append(
                    approved_reason
                )

            output_labels: List[str] = []

            if executed:
                output_labels = (
                    analyze_output_labels(
                        content=(
                            _extract_tool_output_text(
                                tool_result
                            )
                        ),
                        base_labels=list(
                            approved_step.output_labels
                            or []
                        ),
                        resource=(
                            _extract_resource_from_request(
                                request
                            )
                        ),
                    )
                )

                approved_step.output_labels = (
                    list(output_labels)
                )

                runtime_state.data_labels_by_step[
                    int(
                        approved_step.step_index
                    )
                ] = list(output_labels)

            runtime_state.pending_confirm_steps = [
                step_index
                for step_index
                in runtime_state.pending_confirm_steps
                if int(step_index)
                != int(
                    approved_step.step_index
                )
            ]

            runtime_state.final_decision = (
                _recompute_runtime_final_decision(
                    runtime_state
                )
            )

            trusted_session.runtime_state = (
                model_to_dict(
                    runtime_state
                )
            )

            trusted_session.final_decision = (
                runtime_state.final_decision
            )

            trusted_session.pending_confirm_steps = [
                step_index
                for step_index
                in trusted_session.pending_confirm_steps
                if int(step_index)
                != int(
                    approved_step.step_index
                )
            ]

            if (
                trusted_session.status
                == "confirm_required"
            ):
                trusted_session.status = (
                    "running"
                )

            task_version = save_session(
                task_handle=task_handle,
                session=trusted_session,
                expected_version=(
                    task_version
                ),
            )

            if executed:
                data_ref = create_data_reference(
                    task_handle=task_handle,
                    user=request.user,
                    step_index=int(
                        approved_step.step_index
                    ),
                    labels=list(
                        approved_step.output_labels
                        or []
                    ),
                )

    security_graph = (
        build_runtime_security_graph(
            runtime_state
        )
    )

    if (
        request.execute
        and result_dict.get("decision")
        == "allow"
        and capability_token_validation.get(
            "decision"
        )
        == "allow"
    ):
        capability_token_validation = dict(
            capability_token_validation
        )

        consumption = (
            mark_capability_token_consumed(
                getattr(
                    request,
                    "capability_token",
                    "",
                )
            )
        )

        capability_token_validation[
            "consumption"
        ] = consumption

    if (
        result_dict.get("decision")
        == "allow"
        and not request.execute
    ):
        capability_token = (
            issue_capability_token(
                user=request.user,
                agent_platform=(
                    request.agent_platform
                ),
                original_task=(
                    request.original_task
                ),
                capability_contract=(
                    task_boundary_evaluation.get(
                        "capability_contract",
                        {},
                    )
                ),
                tool=request.tool,
                params=request.params,
                sandbox_profile=(
                    request.sandbox_profile
                ),
            )
        )

        capability_token["issued"] = True

    elif (
        result_dict.get("decision")
        == "allow"
        and request.execute
    ):
        capability_token = {
            "token_type": (
                "agentguard_capability_token"
            ),
            "issued": False,
            "reason": (
                "Execution phase consumes the "
                "capability token."
            ),
        }

    else:
        capability_token = {
            "token_type": (
                "agentguard_capability_token"
            ),
            "issued": False,
            "reason": (
                "No capability token was issued."
            ),
        }

    authorization_trace = (
        build_authorization_trace(
            agent_auth_profile=(
                agent_auth_profile
            ),
            capability_token_validation=(
                capability_token_validation
            ),
            task_boundary_evaluation=(
                task_boundary_evaluation
            ),
            sandbox_evaluation=(
                sandbox_evaluation
            ),
            final_decision=str(
                result_dict.get(
                    "decision",
                    "deny",
                )
            ),
            final_risk_score=int(
                result_dict.get(
                    "risk_score",
                    0,
                )
                or 0
            ),
            executed=executed,
        )
    )

    _write_proxy_audit_log(
        request=request,
        result_dict=result_dict,
        executed=executed,
        tool_result=tool_result,
    )

    return ToolProxyAuthorizeResponse(
        success=True,
        mode="tool_proxy_authorize",
        decision=str(
            result_dict.get(
                "decision",
                "deny",
            )
        ),
        risk_score=int(
            result_dict.get(
                "risk_score",
                0,
            )
            or 0
        ),
        reason=_as_reason_list(
            result_dict.get("reason")
        ),
        executed=executed,
        tool_result=tool_result,
        sandbox_evidence=(
            sandbox_evidence
        ),
        contract=model_to_dict(contract),
        runtime_state=model_to_dict(
            runtime_state
        ),
        security_graph=security_graph,
        agent_auth_profile=(
            agent_auth_profile
        ),
        capability_token=(
            capability_token
        ),
        capability_token_validation=(
            capability_token_validation
        ),
        authorization_trace=(
            authorization_trace
        ),
        task_boundary_evaluation=(
            task_boundary_evaluation
        ),
        sandbox_profile=(
            request.sandbox_profile
        ),
        sandbox_evaluation=(
            sandbox_evaluation
        ),
        task_handle=task_handle,
        task_version=int(
            task_version or 0
        ),
        data_ref=data_ref,
        approval_ticket=(
            approval_ticket
        ),
        approval_status=(
            approval_status
        ),
    )

def _revocation_subject_values(
    request: ToolProxyAuthorizeRequest,
) -> Dict[str, str]:
    metadata = dict(
        getattr(
            request,
            "external_agent_metadata",
            {},
        )
        or {}
    )

    capability_token = str(
        getattr(
            request,
            "capability_token",
            "",
        )
        or metadata.get(
            "capability_token"
        )
        or metadata.get(
            "capabilityToken"
        )
        or metadata.get(
            "agentguard/capabilityToken"
        )
        or metadata.get(
            "agentguard.capability_token"
        )
        or ""
    ).strip()

    return {
        "task": str(
            getattr(
                request,
                "task_handle",
                "",
            )
            or ""
        ).strip(),
        "approval_ticket": str(
            getattr(
                request,
                "approval_ticket",
                "",
            )
            or ""
        ).strip(),
        "capability_token": (
            capability_token
        ),
    }


def _revocation_block_reason(
    request: ToolProxyAuthorizeRequest,
) -> str:
    values = (
        _revocation_subject_values(
            request
        )
    )

    task_handle = values["task"]

    user = str(
        getattr(
            request,
            "user",
            "",
        )
        or ""
    ).strip()

    checks = [
        (
            "task",
            task_handle,
        ),
        (
            "approval_ticket",
            values[
                "approval_ticket"
            ],
        ),
        (
            "capability_token",
            values[
                "capability_token"
            ],
        ),
    ]

    for subject_type, subject_value in checks:
        if not subject_value:
            continue

        try:
            assert_subject_not_revoked(
                subject_type=(
                    subject_type
                ),
                subject_value=(
                    subject_value
                ),
                expected_task_handle=(
                    task_handle
                ),
                expected_user=user,
            )

        except RevocationStoreError as exc:
            return (
                "Authorization revoked: "
                + str(exc)
            )

    return ""


def _build_revocation_denial_response(
    request: ToolProxyAuthorizeRequest,
    reason: str,
) -> ToolProxyAuthorizeResponse:
    payload = {
        "success": (
            False
        ),
        "mode": (
            ""
        ),
        "task_handle": (
            str(getattr(request, "task_handle", "") or "")
        ),
        "task_version": (
            0
        ),
        "decision": (
            "deny"
        ),
        "risk_score": (
            100
        ),
        "reason": (
            [reason, "Revocation registry blocked this tool call."]
        ),
        "executed": (
            False
        ),
        "tool_result": (
            None
        ),
        "sandbox_evidence": (
            None
        ),
        "contract": (
            {}
        ),
        "runtime_state": (
            {}
        ),
        "security_graph": (
            {}
        ),
        "agent_auth_profile": (
            {}
        ),
        "capability_token": (
            ""
        ),
        "capability_token_validation": (
            {}
        ),
        "authorization_trace": (
            []
        ),
        "task_boundary_evaluation": (
            {}
        ),
        "sandbox_profile": (
            ""
        ),
        "sandbox_evaluation": (
            {}
        ),
        "data_ref": (
            ""
        ),
        "approval_ticket": (
            str(getattr(request, "approval_ticket", "") or "")
        ),
        "approval_status": (
            "revoked"
        ),
    }

    result_dict = {
        "decision": "deny",
        "risk_score": 100,
        "reason": [
            reason,
            (
                "Revocation registry blocked "
                "this tool call before runtime "
                "analysis and sandbox execution."
            ),
        ],
    }

    try:
        _write_proxy_audit_log(
            request=request,
            result_dict=result_dict,
            executed=False,
            tool_result=None,
        )

    except Exception:
        # Revocation enforcement must remain fail-closed
        # even if audit persistence is unavailable.
        pass

    model_construct = getattr(
        ToolProxyAuthorizeResponse,
        "model_construct",
        None,
    )

    if callable(model_construct):
        return model_construct(
            **payload
        )

    legacy_construct = getattr(
        ToolProxyAuthorizeResponse,
        "construct",
        None,
    )

    if callable(legacy_construct):
        return legacy_construct(
            **payload
        )

    return ToolProxyAuthorizeResponse(
        **payload
    )

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

    该函数提供外部 Agent 工具调用的统一安全入口。
    """
    revocation_reason = (
        _revocation_block_reason(
            request
        )
    )

    if revocation_reason:
        return (
            _build_revocation_denial_response(
                request,
                revocation_reason,
            )
        )


    if str(
        getattr(
            request,
            "approval_ticket",
            "",
        )
        or ""
    ).strip():
        return _authorize_approved_tool_call(
            request
        )


    (
        trusted_session,
        task_version,
        contract,
        runtime_state,
    ) = _load_task_context(request)

    runtime_step_recorded = False

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
    data_ref = ""
    approval_ticket = ""
    approval_status = ""

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

        runtime_step_recorded = True
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
        executed = _sandbox_entered(real_sandbox_result)

    _update_runtime_labels_from_tool_output(
        runtime_state=runtime_state,
        request=request,
        tool_result=tool_result,
        executed=executed,
    )

    security_graph = build_runtime_security_graph(runtime_state)

    if request.execute and result_dict.get("decision") == "allow" and capability_token_validation.get("decision") == "allow":
        capability_token_validation = dict(capability_token_validation)
        consumption = mark_capability_token_consumed(getattr(request, "capability_token", ""))
        capability_token_validation["consumption"] = consumption
        reasons = _as_reason_list(capability_token_validation.get("reason"))
        if consumption.get("consumed"):
            reasons.append("Capability token was consumed after execution phase entered sandbox.")
        else:
            reasons.append("Capability token consumption was attempted after execution phase.")
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

    authorization_phase = str(
        (
            request.external_agent_metadata
            or {}
        ).get("authorization_phase")
        or ""
    )

    should_persist_runtime = (
        authorization_phase != "prepare"
        or str(
            result_dict.get(
                "decision"
            )
            or "deny"
        ) != "allow"
    )

    if (
        trusted_session is not None
        and runtime_step_recorded
        and should_persist_runtime
    ):
        trusted_session.task_id = runtime_state.task_id
        trusted_session.contract = model_to_dict(contract)
        trusted_session.runtime_state = model_to_dict(runtime_state)

        trusted_session.update_final_decision(
            str(result_dict.get("decision", "deny"))
        )

        if trusted_session.final_decision == "deny":
            trusted_session.status = "blocked"
        elif trusted_session.final_decision == "confirm":
            trusted_session.status = "confirm_required"
        else:
            trusted_session.status = "running"

        task_version = save_session(
            task_handle=request.task_handle,
            session=trusted_session,
            expected_version=task_version,
        )

        if (
            str(
                result_dict.get(
                    "decision"
                )
                or "deny"
            ) == "confirm"
            and runtime_state.steps
        ):
            latest_step = runtime_state.steps[-1]
            approval_ticket, approval_status = create_approval_ticket(
                task_handle=str(
                    trusted_session.task_handle
                    or request.task_handle
                ).strip(),
                user=request.user,
                step_index=int(
                    latest_step.step_index
                ),
                tool=request.tool,
                params=dict(
                    request.params or {}
                ),
                data_refs=list(
                    (
                        request.external_agent_metadata
                        or {}
                    ).get("trusted_data_refs")
                    or []
                ),
            )

        if executed and runtime_state.steps:
            latest_step = runtime_state.steps[-1]
            data_ref = create_data_reference(
                task_handle=str(
                    trusted_session.task_handle
                    or request.task_handle
                ).strip(),
                user=request.user,
                step_index=int(
                    latest_step.step_index
                ),
                labels=list(
                    latest_step.output_labels
                    or []
                ),
            )

    _write_proxy_audit_log(
        request=request,
        result_dict=result_dict,
        executed=executed,
        tool_result=tool_result,
    )

    return ToolProxyAuthorizeResponse(
        success=True,
        task_handle=request.task_handle.strip(),
        task_version=task_version,
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
        data_ref=data_ref,
        approval_ticket=approval_ticket,
        approval_status=approval_status,
    )
