from fastapi import APIRouter, HTTPException

from backend.agents.agent_service import (
    build_tool_request_from_plan,
    dump_plan_result,
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

    tool_request = build_tool_request_from_plan(request, plan_result)
    agent_result = dump_plan_result(plan_result)

    if tool_request is None:
        return {
            "success": False,
            "executed": False,
            "message": "Agent did not generate a valid tool call",
            "source": f"{agent_type}_agent",
            "agent_type": agent_type,
            "agent_result": agent_result,
            "gateway_result": None,
            "tool_result": None,
            "pending_id": None,
        }

    return handle_tool_request(
        request=tool_request,
        original_input=request.user_input,
        agent_result=agent_result,
    )


@router.post("/llm/plan")
def llm_plan(request: AgentTextRequest):
    plan_result = plan_with_agent(request, "llm")

    return {
        "user": request.user,
        "source": "llm_agent",
        "agent_result": dump_plan_result(plan_result),
    }
