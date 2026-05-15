from fastapi import APIRouter

from backend.agents.agent_service import (
    build_tool_request_from_plan,
    dump_plan_result,
    plan_with_agent,
)
from backend.audit import write_log
from backend.gateway import check_tool_call, handle_tool_request
from backend.schemas import AgentTextRequest, ToolCallRequest
from backend.tools import execute_tool


router = APIRouter()


@router.post("/demo/fake-agent/plan")
def fake_agent_plan(request: AgentTextRequest):
    plan_result = plan_with_agent(request, "fake")

    return {
        "user": request.user,
        "source": "fake_agent_demo",
        "agent_result": dump_plan_result(plan_result),
    }


@router.post("/demo/fake-agent/simulate")
def fake_agent_simulate(request: AgentTextRequest):
    plan_result = plan_with_agent(request, "fake")
    tool_request = build_tool_request_from_plan(request, plan_result)
    agent_result = dump_plan_result(plan_result)

    if tool_request is None:
        return {
            "success": False,
            "executed": False,
            "message": "FakeAgent did not generate a valid tool call",
            "source": "fake_agent_demo",
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


@router.post("/agent/injection-demo")
def agent_injection_demo():
    attack_chain = []

    first_request = ToolCallRequest(
        user="alice",
        tool="file.read",
        params={"path": "public/injected_notice.txt"},
    )

    first_check = check_tool_call(first_request)
    first_tool_result = None
    first_executed = False

    if first_check["decision"] == "allow":
        first_tool_result = execute_tool(first_request.tool, first_request.params)
        first_executed = True

    write_log(
        user=first_request.user,
        tool=first_request.tool,
        params=first_request.params,
        gateway_result=first_check,
        executed=first_executed,
        original_input="read file public/injected_notice.txt",
        message="Prompt-injection demo step 1: read public file",
        tool_result=first_tool_result,
    )

    attack_chain.append({
        "step": 1,
        "description": "Agent reads public/injected_notice.txt",
        "request": first_request.model_dump(),
        "gateway_result": first_check,
        "executed": first_executed,
        "tool_result": first_tool_result,
    })

    if not first_executed or not first_tool_result or not first_tool_result.get("success"):
        return {
            "success": False,
            "message": "Step 1 failed; attack chain stopped",
            "attack_chain": attack_chain,
        }

    file_content = str(first_tool_result.get("result", ""))
    injection_keywords = [
        "ignore previous rules",
        "ignore previous instructions",
        "secret/password.txt",
        "attacker@example.com",
    ]

    detected_keywords = [
        keyword for keyword in injection_keywords
        if keyword.lower() in file_content.lower()
    ]

    if not detected_keywords:
        return {
            "success": True,
            "message": "Public file was read, but no obvious prompt-injection keyword was detected",
            "attack_chain": attack_chain,
            "detected_keywords": [],
        }

    second_request = ToolCallRequest(
        user="alice",
        tool="file.read",
        params={"path": "secret/password.txt"},
    )

    second_check = check_tool_call(second_request)
    second_tool_result = None
    second_executed = False

    if second_check["decision"] == "allow":
        second_tool_result = execute_tool(second_request.tool, second_request.params)
        second_executed = True

    write_log(
        user=second_request.user,
        tool=second_request.tool,
        params=second_request.params,
        gateway_result=second_check,
        executed=second_executed,
        original_input="prompt injection tries to read secret/password.txt",
        message="Prompt-injection demo step 2: dangerous tool call handled by Gateway",
        tool_result=second_tool_result,
    )

    attack_chain.append({
        "step": 2,
        "description": "Prompt-injection content tries to induce reading secret/password.txt",
        "detected_keywords": detected_keywords,
        "request": second_request.model_dump(),
        "gateway_result": second_check,
        "executed": second_executed,
        "tool_result": second_tool_result,
    })

    return {
        "success": True,
        "message": "Prompt-injection attack-chain demo completed",
        "detected_keywords": detected_keywords,
        "attack_chain": attack_chain,
    }
