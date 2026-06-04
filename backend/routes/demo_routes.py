from fastapi import APIRouter

from backend.demo import (
    list_demo_cases,
    run_demo_case,
    run_fake_agent_demo,
    run_fake_agent_plan,
)
from backend.schemas import AgentTextRequest


router = APIRouter(
    prefix="/demo",
    tags=["demo"],
)


@router.get("/cases")
def get_demo_cases():
    """
    查看所有内置演示样例。

    这些样例只用于展示：
    FakeAgent -> Gateway -> ToolExecutor 的演示链路。
    它们不属于主项目核心 API。
    """
    return list_demo_cases()


@router.post("/fake-agent/plan")
def fake_agent_plan(request: AgentTextRequest):
    """
    只运行 FakeAgent 规划阶段。

    这个接口不会执行工具，也不会进入 Gateway。
    它只展示 FakeAgent 如何把自然语言任务转换为结构化工具调用计划。
    """
    return run_fake_agent_plan(request)


@router.post("/fake-agent/run")
def fake_agent_run(request: AgentTextRequest):
    """
    运行完整演示链路：

    1. FakeAgent 解析自然语言；
    2. 生成 ToolCallRequest；
    3. 交给 Gateway 判断；
    4. allow 时执行工具；
    5. confirm 时进入 pending；
    6. deny 时直接拦截。

    注意：这是 demo-only 接口，不是主项目核心接口。
    """
    return run_fake_agent_demo(request)


@router.post("/cases/{case_id}/run")
def run_builtin_demo_case(case_id: str):
    """
    运行一个内置 demo case。

    示例：
    - /demo/cases/read_public_file/run
    - /demo/cases/read_secret_file/run
    - /demo/cases/delete_public_file/run
    - /demo/cases/send_email/run
    - /demo/cases/shell_command/run
    """
    return run_demo_case(case_id)