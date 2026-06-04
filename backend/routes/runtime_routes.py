from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.capability.capability_compiler import compile_capability_contract
from backend.runtime.runtime_monitor import (
    create_runtime_state,
    get_step_output_labels,
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

    for step_index in request.input_from_steps:
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
        "result": result.model_dump(),
        "state": state.model_dump(),
    }


@router.get("/{task_id}/state")
def read_runtime_state(task_id: str):
    """
    查看指定任务的运行时状态。
    """

    state = get_runtime_state(task_id)

    if state is None:
        raise HTTPException(status_code=404, detail=f"Runtime task {task_id} not found.")

    return {
        "message": "Runtime task state loaded successfully.",
        "state": state.model_dump(),
    }


@router.get("")
def list_runtime_tasks():
    """
    查看当前内存中的全部运行时任务。
    """

    states = list_runtime_states()

    return {
        "message": "Runtime task list loaded successfully.",
        "count": len(states),
        "tasks": {
            task_id: state.model_dump()
            for task_id, state in states.items()
        },
    }
