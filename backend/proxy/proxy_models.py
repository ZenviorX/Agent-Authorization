from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolProxyAuthorizeRequest(BaseModel):
    """
    外部 Agent 工具调用安全检查请求。

    这个模型用于接收第三方 Agent / 前端调试台发来的工具调用请求。
    第一版只负责做安全判断，不强制真实执行工具。
    """

    user: str = Field(
        default="user",
        description="当前用户身份，例如 user / admin / analyst",
    )

    original_task: str = Field(
        ...,
        description="用户原始任务，例如：帮我读取公开通知并总结",
    )

    tool: str = Field(
        ...,
        description="Agent 想调用的工具名，例如 file.read / email.send / db.query / shell.run",
    )

    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具调用参数，例如 {'path': 'public/notice.txt'}",
    )

    input_labels: List[str] = Field(
        default_factory=list,
        description="当前工具调用输入数据的安全标签，例如 public / tainted / sensitive / secret",
    )

    input_from_steps: List[int] = Field(
        default_factory=list,
        description="当前调用是否引用了前面步骤的输出，第一版可以先留空",
    )

    agent_confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Agent 对本次工具调用的置信度，第一版可以不传",
    )

    execute: bool = Field(
        default=False,
        description="是否在 allow 后真实执行工具。第一版默认 False，只做安全检查",
    )


class ToolProxyAuthorizeResponse(BaseModel):
    """
    Tool Proxy 安全检查响应。

    前端页面会直接展示这个结构。
    """

    success: bool = Field(
        default=True,
        description="接口是否正常完成",
    )

    mode: str = Field(
        default="tool_proxy_authorize",
        description="当前运行模式",
    )

    decision: str = Field(
        ...,
        description="安全决策：allow / confirm / deny",
    )

    risk_score: int = Field(
        default=0,
        description="风险分数",
    )

    reason: List[str] = Field(
        default_factory=list,
        description="安全判断原因",
    )

    executed: bool = Field(
        default=False,
        description="本次工具是否被真实执行",
    )

    tool_result: Optional[Dict[str, Any]] = Field(
        default=None,
        description="工具执行结果。execute=False 时通常为空",
    )

    contract: Dict[str, Any] = Field(
        default_factory=dict,
        description="本次任务生成的 Capability Contract",
    )

    runtime_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="运行时状态",
    )

    security_graph: Dict[str, Any] = Field(
        default_factory=dict,
        description="运行时安全图谱",
    )
