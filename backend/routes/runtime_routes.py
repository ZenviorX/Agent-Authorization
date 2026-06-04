from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.capability.capability_compiler import compile_capability_contract
from backend.runtime.runtime_monitor import (
    approve_runtime_step,
    create_runtime_state,
    get_step_output_labels,
    reject_runtime_step,
    run_runtime_step,
)
from backend.runtime.runtime_store import (
    get_runtime_state,
    list_runtime_states,
    save_runtime_state,
)


router = APIRouter(
    prefix="/runtime",
    tags=["Agent Runtime Monitor"],
)


class RuntimeStartRequest(BaseModel):
    user: str = Field(default="user", description="发起任务的用户")
    original_task: str = Field(..., description="用户原始任务")
    max_steps: int = Field(default=5, description="任务最大步骤数")
    risk_budget: int = Field(default=80, description="任务风险预算")


def build_runtime_summary(state):
    """
    生成运行时任务摘要，供 start / step / state / list 接口复用。
    """
    last_step = state.steps[-1] if state.steps else None
    attack_chain_state = state.attack_chain_state or {}

    approved_steps = [
        step.step_index
        for step in state.steps
        if step.confirmation_status == "approved"
    ]

    rejected_steps = [
        step.step_index
        for step in state.steps
        if step.confirmation_status == "rejected"
    ]

    return {
        "task_id": state.task_id,
        "user": state.user,
        "original_task": state.original_task,
        "current_step": state.current_step,
        "used_risk": state.used_risk,
        "risk_budget": state.contract.risk_budget,
        "final_decision": state.final_decision,
        "is_blocked": state.is_blocked,
        "pending_confirm_steps": state.pending_confirm_steps,
        "approved_steps": approved_steps,
        "rejected_steps": rejected_steps,
        "pending_confirm_count": len(state.pending_confirm_steps),
        "step_count": len(state.steps),
        "violation_count": len(state.violations),
        "last_tool": last_step.tool if last_step else None,
        "last_decision": last_step.decision if last_step else None,
        "last_risk_score": last_step.risk_score if last_step else None,
        "attack_chain_decision": attack_chain_state.get("final_decision"),
        "attack_chain_risk": attack_chain_state.get("cumulative_risk"),
    }

class RuntimeStepRequest(BaseModel):
    tool: str = Field(..., description="当前调用的工具")
    params: Dict[str, Any] = Field(default_factory=dict, description="工具调用参数")

    input_labels: List[str] = Field(
        default_factory=list,
        description="手动传入的输入标签"
    )

    input_from_steps: List[int] = Field(
        default_factory=list,
        description="继承哪些历史步骤的输出标签"
    )

    output_content: Optional[str] = Field(
        default=None,
        description="工具实际输出内容，用于自动分析 taint / sensitive 标签"
    )



@router.post("/start")
def start_runtime_task(request: RuntimeStartRequest):
    """
    启动一个运行时任务。

    系统会自动：
    1. 编译 Capability Contract v2；
    2. 创建 RuntimeTaskState；
    3. 保存到内存状态表。
    """

    contract = compile_capability_contract(
        user=request.user,
        original_task=request.original_task,
        max_steps=request.max_steps,
        risk_budget=request.risk_budget,
    )

    state = create_runtime_state(contract)
    save_runtime_state(state)

    return {
        "message": "Runtime task started successfully.",
        "task_id": state.task_id,
        "summary": build_runtime_summary(state),
        "attack_chain_state": state.attack_chain_state,
        "contract": contract.model_dump(),
        "state": state.model_dump(),
    }

@router.post("/{task_id}/step")
def run_step(task_id: str, request: RuntimeStepRequest):
    """
    在指定任务中执行一步工具调用检查。

    如果 input_from_steps=[1]，
    系统会自动把第 1 步的 output_labels 作为本步骤的 input_labels。
    """

    state = get_runtime_state(task_id)

    if state is None:
        raise HTTPException(status_code=404, detail=f"Runtime task {task_id} not found.")

    merged_input_labels = list(request.input_labels)

    source_steps = list(request.input_from_steps)

    if not source_steps and state.current_step > 0:
        source_steps.append(state.current_step)

    for step_index in source_steps:
        inherited_labels = get_step_output_labels(state, step_index)

        for label in inherited_labels:
            if label not in merged_input_labels:
                merged_input_labels.append(label)

    result = run_runtime_step(
        state=state,
        tool=request.tool,
        params=request.params,
        input_labels=merged_input_labels,
        output_content=request.output_content,
    )

    save_runtime_state(state)

    return {
        "message": "Runtime step checked successfully.",
        "task_id": task_id,
        "decision": result.decision,
        "risk_score": result.risk_score,
        "reason": result.reason,
        "summary": build_runtime_summary(state),
        "attack_chain_state": state.attack_chain_state,
        "result": result.model_dump(),
        "state": state.model_dump(),
    }


@router.get("/{task_id}/state")
def get_state(task_id: str):
    state = get_runtime_state(task_id)

    if not state:
        raise HTTPException(status_code=404, detail="Runtime task not found.")

    return {
        "message": "Runtime task state fetched successfully.",
        "task_id": task_id,
        "summary": build_runtime_summary(state),
        "violations": state.violations,
        "attack_chain_state": state.attack_chain_state,
        "steps": [step.model_dump() for step in state.steps],
        "state": state.model_dump(),
    }

@router.post("/{task_id}/confirm/{step_index}")
def confirm_runtime_step(task_id: str, step_index: int):
    """
    人工批准某个等待确认的运行时步骤。
    """
    state = get_runtime_state(task_id)

    if not state:
        raise HTTPException(status_code=404, detail="Runtime task not found.")

    success = approve_runtime_step(
        state=state,
        step_index=step_index,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Runtime step is not waiting for confirmation.",
        )

    save_runtime_state(state)

    return {
        "message": "Runtime step confirmed successfully.",
        "task_id": task_id,
        "confirmed_step": step_index,
        "summary": build_runtime_summary(state),
        "state": state.model_dump(),
    }

@router.post("/{task_id}/reject/{step_index}")
def reject_runtime_confirm_step(task_id: str, step_index: int):
    """
    人工拒绝某个等待确认的运行时步骤。
    """
    state = get_runtime_state(task_id)

    if not state:
        raise HTTPException(status_code=404, detail="Runtime task not found.")

    success = reject_runtime_step(
        state=state,
        step_index=step_index,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Runtime step is not waiting for confirmation.",
        )

    save_runtime_state(state)

    return {
        "message": "Runtime step rejected successfully.",
        "task_id": task_id,
        "rejected_step": step_index,
        "summary": build_runtime_summary(state),
        "state": state.model_dump(),
    }

@router.get("")
def list_runtime_tasks():
    """
    查看当前内存中的全部运行时任务摘要。
    """
    states = list_runtime_states()

    tasks = [
        build_runtime_summary(state)
        for state in states.values()
    ]

    return {
        "message": "Runtime task list loaded successfully.",
        "count": len(tasks),
        "tasks": tasks,
    }
