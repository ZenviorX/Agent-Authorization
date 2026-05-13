from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class ToolCallRequest(BaseModel):
    """
    结构化工具调用请求。
    user：发起工具调用的用户
    tool：工具名称
    params：工具参数
    """
    user: str = "test_user"
    tool: str
    params: Dict[str, Any] = Field(default_factory=dict)


class GatewayResponse(BaseModel):
    """
    授权网关判断结果。
    decision:
        allow   允许执行
        confirm 需要人工确认
        deny    拒绝执行
    """
    decision: str
    risk_score: int
    reason: List[str]


class AgentTextRequest(BaseModel):
    """
    模拟智能体输入请求。
    user：当前用户
    user_input：自然语言任务
    """
    user: str = "test_user"
    user_input: str


class ApprovalRejectRequest(BaseModel):
    """
    人工拒绝确认请求。
    """
    reason: Optional[str] = "人工拒绝执行"