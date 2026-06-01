from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from backend.agents.multistep_fake_agent import MultiStepFakeAgent
from backend.agents.multistep_llm_agent import MultiStepLLMAgent
from backend.task_session.session_executor import execute_task_session
from backend.task_session.session_models import TaskSession
from backend.task_session.task_audit_logger import write_task_session_log, read_task_session_logs


router = APIRouter(
    prefix="/task",
    tags=["task-session"],
)


class TaskRunRequest(BaseModel):
    """
    多步任务执行请求。

    user: 当前用户，例如 student / teacher / admin
    user_input: 用户输入的自然语言任务
    agent_type: 使用哪种 Agent
        - fake: 规则模拟 Agent
        - llm: 真实大模型 Agent
    """

    user: str
    user_input: str
    agent_type: str = "fake"


@router.post("/run", response_model=TaskSession)
def run_task(request: TaskRunRequest):
    """
    执行一个多步 Agent 任务链。

    流程：
    1. 根据 agent_type 选择 FakeAgent 或 LLM Agent
    2. Agent 生成多步任务计划
    3. TaskSessionExecutor 执行任务链
    4. 每一步都经过 Gateway 检查
    5. 返回完整任务链结果
    """

    if request.agent_type == "llm":
        try:
            agent = MultiStepLLMAgent()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"MultiStepLLMAgent 初始化失败：{str(e)}",
            )
    else:
        agent = MultiStepFakeAgent()

    try:
        session = agent.plan(
            user=request.user,
            user_input=request.user_input,
        )

        result = execute_task_session(session)
        write_task_session_log(result)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"多步任务执行失败：{str(e)}",
        )

@router.get("/logs")
def get_task_logs(limit: int = 50):
    """
    读取最近的多步任务链审计日志。

    参数：
    - limit: 最多返回多少条日志，默认 50 条

    返回：
    - logs: 任务链日志列表
    - count: 实际返回数量
    """
    logs = read_task_session_logs(limit=limit)

    return {
        "count": len(logs),
        "logs": logs,
    }