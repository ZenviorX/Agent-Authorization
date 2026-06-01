from fastapi import APIRouter, HTTPException

from backend.agents.agent_service import (
    dump_plan_result,
    inspect_and_build_tool_request,
    plan_with_agent,
)
from backend.gateway import handle_tool_request
from backend.schemas import AgentTextRequest


router = APIRouter()


@router.post("/agent/plan")
def agent_plan(request: AgentTextRequest, agent_type: str = "fake"):
    try:
        plan_result = plan_with_agent(request, agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "user": request.user,
        "source": f"{agent_type}_agent",
        "agent_type": agent_type,
        "agent_result": dump_plan_result(plan_result),
    }


@router.post("/agent/simulate")
def agent_simulate(request: AgentTextRequest, agent_type: str = "fake"):
    try:
        plan_result = plan_with_agent(request, agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    agent_result = dump_plan_result(plan_result)

    tool_request, guard_result = inspect_and_build_tool_request(
        request=request,
        plan_result=plan_result,
    )

    if tool_request is None:
        return {
            "success": True,
            "executed": False,
            "message": "Agent 计划未通过 PlanGuard 校验，系统未执行任何工具。",
            "source": f"{agent_type}_agent",
            "agent_type": agent_type,
            "agent_result": {
                **agent_result,
                "plan_guard": guard_result,
            },
            "gateway_result": {
                "decision": guard_result["decision"],
                "risk_score": guard_result["risk_score"],
                "reason": guard_result["reason"],
                "stage": "plan_guard",
                "missing_params": guard_result.get("missing_params", []),
                "clarification_question": guard_result.get("clarification_question"),
            },
            "tool_result": None,
            "pending_id": None,
            "action_required": (
                "clarification"
                if guard_result["decision"] == "confirm"
                else "blocked"
            ),
        }

    return handle_tool_request(
        request=tool_request,
        original_input=request.user_input,
        agent_result={
            **agent_result,
            "plan_guard": guard_result,
        },
    )


@router.post("/llm/plan")
def llm_plan(request: AgentTextRequest):
    plan_result = plan_with_agent(request, "llm")

    return {
        "user": request.user,
        "source": "llm_agent",
        "agent_result": dump_plan_result(plan_result),
    }