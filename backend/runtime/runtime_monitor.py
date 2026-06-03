from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.capability.capability_contract import CapabilityContract, CapabilityCheckResult
from backend.capability.capability_enforcer import enforce_capability_contract
from backend.runtime.task_state import RuntimeStepRecord, RuntimeTaskState
from backend.runtime.flow_label import analyze_output_labels


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

    step_record = RuntimeStepRecord(
        step_index=next_step,
        tool=tool,
        params=params,
        input_labels=input_labels,
        output_labels=output_labels,
        decision=result.decision,
        risk_score=result.risk_score,
        reason=result.reason,
        executed=(result.decision == "allow"),
        blocked=(result.decision == "deny"),
    )

    state.steps.append(step_record)

    if result.decision == "allow":
        state.current_step = next_step
        state.used_risk += result.risk_score
        state.data_labels_by_step[next_step] = output_labels

    elif result.decision == "confirm":
        state.current_step = next_step
        state.used_risk += result.risk_score
        state.violations.append(
            f"Step {next_step} requires human confirmation: {tool}"
        )

    elif result.decision == "deny":
        state.is_blocked = True
        state.violations.extend(result.reason)

    return result


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