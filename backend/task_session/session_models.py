from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    """
    返回当前时间，用于记录任务链和步骤创建时间。
    """
    return datetime.now(timezone.utc).isoformat()


class TaskStep(BaseModel):
    """
    表示多步任务链中的一个步骤。

    例如：
    Step 1: file.read public/notice.txt
    Step 2: email.send teacher@sdu.edu.cn
    """

    step_id: int
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)

    description: str = ""

    decision: Optional[str] = None
    risk_score: int = 0
    reason: List[str] = Field(default_factory=list)

    executed: bool = False
    tool_result: Optional[Dict[str, Any]] = None

    sensitive: bool = False
    tainted: bool = False

    created_at: str = Field(default_factory=now_iso)


class TaskSession(BaseModel):
    """
    表示一次完整的 Agent 任务链。

    一个 TaskSession 里可以包含多个 TaskStep。
    后续我们会用它来做：
    1. 多步任务执行
    2. 上下文风险累计
    3. 敏感数据传播追踪
    4. 提示注入攻击链检测
    """

    session_id: str = Field(default_factory=lambda: str(uuid4()))

    user: str
    original_input: str
    agent_type: str = "fake"

    steps: List[TaskStep] = Field(default_factory=list)

    context_risk_score: int = 0
    sensitive_context: bool = False
    tainted_context: bool = False

    status: str = "created"

    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)

    def add_step(self, step: TaskStep) -> None:
        """
        向任务链中添加一个步骤。
        """
        self.steps.append(step)
        self.updated_at = now_iso()

    def mark_running(self) -> None:
        """
        标记任务链正在执行。
        """
        self.status = "running"
        self.updated_at = now_iso()

    def mark_finished(self) -> None:
        """
        标记任务链执行完成。
        """
        self.status = "finished"
        self.updated_at = now_iso()

    def mark_blocked(self) -> None:
        """
        标记任务链被安全网关拦截。
        """
        self.status = "blocked"
        self.updated_at = now_iso()