from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.capability.capability_contract import CapabilityContract, CapabilityCheckResult
from backend.capability.capability_enforcer import enforce_capability_contract
from backend.runtime.task_state import RuntimeStepRecord, RuntimeTaskState
from backend.runtime.flow_label import analyze_output_labels
from backend.attack_chain.attack_chain_detector import AttackChainDetector
from backend.attack_chain.attack_chain_detector import AttackChainDetector


def create_runtime_state(contract: CapabilityContract) -> RuntimeTaskState:
    """
    根据 Capability Contract v2 创建任务运行时状态。
    """

    return RuntimeTaskState(
        task_id=contract.task_id,
        user=contract.user,
        original_task=contract.original_task,
        contract=contract,
        current_step=0,
        used_risk=0,
    )


def _infer_output_labels(
    contract: CapabilityContract,
    tool: str,
    decision: str,
    output_content: Optional[str] = None,
    resource: Optional[str] = None,
) -> List[str]:
    """
    根据合约能力规则和实际输出内容推断输出标签。

    - allow 的步骤才会产生输出；
    - 先读取合约中该工具的基础 output_labels；
    - 再根据实际输出内容做 taint / sensitive 分析。
    """

    if decision != "allow":
        return []

    base_labels: List[str] = []

    for capability in contract.capabilities:
        if capability.tool == tool:
            base_labels = list(capability.output_labels)
            break

    return analyze_output_labels(
        content=output_content,
        base_labels=base_labels,
        resource=resource,
    )
    
    """
    根据合约中的能力规则推断该工具调用可能产生的输出标签。

    注意：
    - 只有 allow 的步骤才认为真正产生输出。
    - confirm 表示等待人工确认，暂时不产生输出。
    - deny 表示被阻断，也不产生输出。
    """

    if decision != "allow":
        return []

    for capability in contract.capabilities:
        if capability.tool == tool:
            return list(capability.output_labels)

    return []
def _build_attack_chain_detector(state: RuntimeTaskState) -> AttackChainDetector:
    """
    根据当前 RuntimeTaskState 中已经执行过的步骤，
    重新构造攻击链检测器的历史状态。
    """
    detector = AttackChainDetector(session_id=state.task_id)

    for step in state.steps:
        chain_params = dict(step.params or {})

        labels = set(step.input_labels or []) | set(step.output_labels or [])

        # 如果历史步骤的标签里已经有 prompt_injection，
        # 就补一个内容标记，方便攻击链检测器恢复状态。
        if "prompt_injection" in labels and not chain_params.get("content"):
            chain_params["content"] = "ignore previous instructions"

        detector.add_event(
            tool=step.tool,
            params=chain_params,
            gateway_result={
                "decision": step.decision,
                "risk_score": step.risk_score,
            },
        )

    return detector

def _merge_task_decision(
    current_decision: str,
    new_decision: str,
) -> str:
    """
    合并任务级整体决策，保证任务状态不会被后续低风险步骤降级。

    优先级：
    deny > confirm > allow
    """
    priority = {
        "allow": 0,
        "confirm": 1,
        "deny": 2,
    }

    current_level = priority.get(current_decision, 0)
    new_level = priority.get(new_decision, 0)

    if new_level >= current_level:
        return new_decision

    return current_decision

def run_runtime_step(
    state: RuntimeTaskState,
    tool: str,
    params: Dict[str, Any],
    input_labels: Optional[List[str]] = None,
    output_content: Optional[str] = None,
) -> CapabilityCheckResult:
    """
    在运行时状态中执行一次工具调用检查，并记录结果。

    它做三件事：
    1. 根据当前状态调用 Capability Enforcer；
    2. 根据 allow / confirm / deny 更新任务状态；
    3. 记录 RuntimeStepRecord，形成任务执行链。
    """

    input_labels = input_labels or []
    if state.is_blocked:
        return CapabilityCheckResult(
            decision="deny",
            risk_score=0,
            reason=[
                "Runtime task is already blocked; no further tool calls are allowed."
            ],
        )   

    next_step = state.current_step + 1

    result = enforce_capability_contract(
        contract=state.contract,
        tool=tool,
        params=params,
        input_labels=input_labels,
        current_step=next_step,
        used_risk=state.used_risk,
    )

    resource = None
    for key in ["path", "file_path", "resource", "filename"]:
       if params.get(key):
          resource = str(params.get(key))
          break

    output_labels = _infer_output_labels(
      contract=state.contract,
      tool=tool,
      decision=result.decision,
      output_content=output_content,
      resource=resource,
)

    chain_detector = _build_attack_chain_detector(state)

    chain_params = dict(params or {})
    if output_content:
        chain_params["content"] = output_content

    chain_state = chain_detector.add_event(
        tool=tool,
        params=chain_params,
        gateway_result={
            "decision": result.decision,
            "risk_score": result.risk_score,
        },
    )

    state.attack_chain_state = chain_state

    chain_events = chain_state.get("events", [])
    current_chain_event = chain_events[-1] if chain_events else {}

    chain_decision = chain_state.get("final_decision", result.decision)
    chain_risk_delta = int(current_chain_event.get("risk_delta", 0) or 0)
    chain_reason = current_chain_event.get("reason", [])

    final_decision = result.decision
    final_risk_score = result.risk_score
    final_reason = list(result.reason or [])

    if chain_reason:
        final_reason.append("Attack chain detector:")
        final_reason.extend(chain_reason)

    dangerous_tools = {
        "email.send",
        "file.write",
        "file.delete",
        "shell.run",
        "code.exec",
        "db.query",
        "http.post",
    }

    dangerous_chain_stages = {
        "sensitive_resource_access",
        "prompt_to_sensitive_access_chain",
        "data_exfiltration_chain",
        "prompt_to_command_execution_chain",
        "high_risk_command",
        "external_output",
    }

    current_chain_stage = current_chain_event.get("stage")

    if chain_decision == "deny":
        final_decision = "deny"
        final_risk_score += chain_risk_delta

    elif chain_decision == "confirm" and final_decision == "allow":
        if tool in dangerous_tools or current_chain_stage in dangerous_chain_stages:
            final_decision = "confirm"
            final_risk_score += chain_risk_delta
        else:
            final_reason.append(
                "Attack chain risk observed, but current step is read-only; "
                "the step is allowed and tainted labels will be propagated."
            )

    elif chain_risk_delta > 0 and (
        tool in dangerous_tools or current_chain_stage in dangerous_chain_stages
    ):
        final_risk_score += chain_risk_delta
    state.final_decision = _merge_task_decision(
        state.final_decision,
        final_decision,
    )

    if final_decision == "confirm" and next_step not in state.pending_confirm_steps:
        state.pending_confirm_steps.append(next_step)

    final_result = CapabilityCheckResult(
        decision=final_decision,
        risk_score=final_risk_score,
        reason=final_reason,
    )

    step_record = RuntimeStepRecord(
        step_index=next_step,
        tool=tool,
        params=params,
        input_labels=input_labels,
        output_labels=output_labels,
        decision=final_result.decision,
        risk_score=final_result.risk_score,
        reason=final_result.reason,
        executed=(final_result.decision == "allow"),
        blocked=(final_result.decision == "deny"),
        requires_confirmation=(final_result.decision == "confirm"),
        confirmed=False,
        confirmation_status=(
            "pending" if final_result.decision == "confirm" else "none"
        ),
    )

    state.steps.append(step_record)

    if final_result.decision == "allow":
        state.current_step = next_step
        state.used_risk += final_result.risk_score
        state.data_labels_by_step[next_step] = output_labels

    elif final_result.decision == "confirm":
        state.current_step = next_step
        state.used_risk += final_result.risk_score
        state.violations.append(
            f"Step {next_step} requires human confirmation: {tool}"
        )

    elif final_result.decision == "deny":
        state.is_blocked = True
        state.violations.extend(final_result.reason)

    return final_result


def get_step_output_labels(
    state: RuntimeTaskState,
    step_index: int,
) -> List[str]:
    """
    获取某一步产生的输出标签。

    后续多步任务中，如果 step2 使用 step1 的输出，
    就可以通过这个函数把 step1 的 output_labels 传给 step2。
    """

    return state.data_labels_by_step.get(step_index, [])

def approve_runtime_step(
    state: RuntimeTaskState,
    step_index: int,
) -> bool:
    """
    批准一个等待人工确认的运行时步骤。

    返回 True 表示批准成功；
    返回 False 表示没有找到对应的待确认步骤。
    """
    for step in state.steps:
        if step.step_index != step_index:
            continue

        if not step.requires_confirmation:
            return False

        step.confirmed = True
        step.confirmation_status = "approved"
        step.executed = True
        step.blocked = False

        state.data_labels_by_step[step_index] = step.output_labels

        if step_index in state.pending_confirm_steps:
            state.pending_confirm_steps.remove(step_index)
        if (
            not state.pending_confirm_steps
            and state.final_decision == "confirm"
            and not state.is_blocked
        ):
            state.final_decision = "allow"

        return True

    return False

def reject_runtime_step(
    state: RuntimeTaskState,
    step_index: int,
) -> bool:
    """
    拒绝一个等待人工确认的运行时步骤。

    返回 True 表示拒绝成功；
    返回 False 表示没有找到对应的待确认步骤。
    """
    for step in state.steps:
        if step.step_index != step_index:
            continue

        if not step.requires_confirmation:
            return False

        step.confirmed = False
        step.confirmation_status = "rejected"
        step.executed = False
        step.blocked = True
        step.decision = "deny"

        if step_index in state.pending_confirm_steps:
            state.pending_confirm_steps.remove(step_index)

        state.is_blocked = True
        state.final_decision = "deny"
        state.violations.append(
            f"Step {step_index} was rejected by human reviewer."
        )

        return True

    return False