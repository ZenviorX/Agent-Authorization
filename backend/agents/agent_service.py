from backend.agents import get_agent
from backend.schemas import AgentPlanResult, AgentTextRequest, ToolCallRequest


def _model_to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()

    if hasattr(model, "dict"):
        return model.dict()

    return model


def plan_with_agent(request: AgentTextRequest, agent_type: str) -> AgentPlanResult:
    agent = get_agent(agent_type)
    raw_result = agent.plan(request.user_input)
    return AgentPlanResult.model_validate(_model_to_dict(raw_result))


def dump_plan_result(plan_result: AgentPlanResult) -> dict:
    return _model_to_dict(plan_result)


def build_tool_request_from_plan(
    request: AgentTextRequest,
    plan_result: AgentPlanResult,
) -> ToolCallRequest | None:
    if plan_result.status != "planned" or plan_result.tool_call is None:
        return None

    return ToolCallRequest(
        user=request.user,
        tool=plan_result.tool_call.tool_name,
        params=plan_result.tool_call.arguments,
    )
