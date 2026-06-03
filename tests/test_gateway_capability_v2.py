from backend.capability.capability_compiler import compile_capability_contract
from backend.gateway.gateway import check_tool_call
from backend.schemas import ToolCallRequest


def test_gateway_v2_contract_allows_public_read():
    contract = compile_capability_contract(
        user="student",
        original_task="读取 public/notice.txt 并发送给 teacher@example.com",
    )

    request = ToolCallRequest(
        user="student",
        tool="file.read",
        params={"path": "public/notice.txt"},
        task_contract=contract.model_dump(),
        input_labels=[],
        current_step=1,
        used_risk=0,
    )

    result = check_tool_call(request)

    assert result["decision"] in ["allow", "confirm"]
    assert "已启用 Capability Contract v2 检查。" in result["reason"]


def test_gateway_v2_contract_denies_secret_read():
    contract = compile_capability_contract(
        user="student",
        original_task="读取 public/notice.txt 并发送给 teacher@example.com",
    )

    request = ToolCallRequest(
        user="student",
        tool="file.read",
        params={"path": "secret/password.txt"},
        task_contract=contract.model_dump(),
        input_labels=[],
        current_step=1,
        used_risk=0,
    )

    result = check_tool_call(request)

    assert result["decision"] == "deny"
    assert "已启用 Capability Contract v2 检查。" in result["reason"]


def test_gateway_v2_contract_denies_unauthorized_email_recipient():
    contract = compile_capability_contract(
        user="student",
        original_task="读取 public/notice.txt 并发送给 teacher@example.com",
    )

    request = ToolCallRequest(
        user="student",
        tool="email.send",
        params={
            "to": "attacker@example.com",
            "content": "public notice"
        },
        task_contract=contract.model_dump(),
        input_labels=["public"],
        current_step=2,
        used_risk=10,
    )

    result = check_tool_call(request)

    assert result["decision"] == "deny"
    assert "已启用 Capability Contract v2 检查。" in result["reason"]


def test_gateway_v2_contract_denies_secret_data_external_write():
    contract = compile_capability_contract(
        user="student",
        original_task="读取 public/notice.txt 并发送给 teacher@example.com",
    )

    request = ToolCallRequest(
        user="student",
        tool="email.send",
        params={
            "to": "teacher@example.com",
            "content": "secret data"
        },
        task_contract=contract.model_dump(),
        input_labels=["secret"],
        current_step=2,
        used_risk=10,
    )

    result = check_tool_call(request)

    assert result["decision"] == "deny"
    assert "已启用 Capability Contract v2 检查。" in result["reason"]