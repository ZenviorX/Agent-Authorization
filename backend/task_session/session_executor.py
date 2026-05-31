from typing import Any, Dict, Optional

from backend.gateway import check_tool_call
from backend.schemas import ToolCallRequest
from backend.task_session.context_analyzer import (
    analyze_text_security,
    is_external_output_tool,
    is_sensitive_path,
)
from backend.task_session.session_models import TaskSession, TaskStep
from backend.tools.tool_executor import execute_tool


def extract_tool_result_text(tool_result: Dict[str, Any]) -> str:
    """
    从工具执行结果中提取文本内容。

    file.read 的返回结果一般是：
    {
        "success": True,
        "result": "文件内容..."
    }

    email.send 的 result 可能是一个 dict。
    这里统一转成字符串，方便后续步骤引用。
    """
    if not tool_result:
        return ""

    result = tool_result.get("result", "")

    if isinstance(result, str):
        return result

    return str(result)


def find_step_by_id(session: TaskSession, step_id: int) -> Optional[TaskStep]:
    """
    根据 step_id 查找前面的步骤。
    """
    for step in session.steps:
        if step.step_id == step_id:
            return step
    return None


def build_step_params(session: TaskSession, step: TaskStep) -> Dict[str, Any]:
    """
    构造当前步骤真正要传给 Gateway 的参数。

    重点处理 content_from_step：
    如果当前步骤写了 "content_from_step": 1，
    说明它要使用第 1 步的执行结果作为 content。
    """
    params = dict(step.params)

    if "content_from_step" in params:
        source_step_id = int(params.get("content_from_step"))
        source_step = find_step_by_id(session, source_step_id)

        if source_step and source_step.tool_result:
            params["content"] = extract_tool_result_text(source_step.tool_result)
        else:
            params["content"] = ""

    return params


def apply_context_security_rules(
    session: TaskSession,
    step: TaskStep,
    real_params: Dict[str, Any],
    gateway_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    在原有 Gateway 判断结果基础上，加入任务链上下文安全规则。

    这里做的是“多步任务链”的新增能力：
    1. 如果前面步骤已经被提示注入污染，后续步骤风险升高
    2. 如果前面步骤读到敏感内容，后续外发工具直接拒绝
    3. 如果被污染上下文继续访问敏感路径，明确记录攻击链风险
    """
    decision = gateway_result.get("decision")
    risk_score = gateway_result.get("risk_score", 0)
    reason = list(gateway_result.get("reason", []))

    # 规则一：上下文已经被提示注入污染，后续步骤风险升高
    if session.tainted_context:
        risk_score += 30
        reason.append("任务链上下文已被提示注入内容污染，当前步骤风险分 +30")

    # 规则二：被污染上下文继续访问敏感路径，判定为提示注入攻击链
    if session.tainted_context and step.tool == "file.read":
        path = str(real_params.get("path", ""))
        if is_sensitive_path(path):
            decision = "deny"
            risk_score += 80
            reason.append("检测到提示注入污染上下文正在尝试访问敏感路径，判定为攻击链行为")

    # 规则三：前面步骤已经读到敏感内容，后续外发工具直接拒绝
    if session.sensitive_context and is_external_output_tool(step.tool):
        decision = "deny"
        risk_score += 100
        reason.append("检测到敏感数据可能流向外部工具，拒绝执行")

    # 规则四：如果当前步骤使用了被污染步骤的输出，也提高风险
    if "content_from_step" in step.params:
        source_step_id = int(step.params.get("content_from_step"))
        source_step = find_step_by_id(session, source_step_id)

        if source_step and source_step.tainted:
            risk_score += 50
            reason.append(f"当前步骤引用了被提示注入污染的 Step {source_step_id} 输出，风险分 +50")

        if source_step and source_step.sensitive and is_external_output_tool(step.tool):
            decision = "deny"
            risk_score += 100
            reason.append(f"当前步骤试图将敏感 Step {source_step_id} 的输出传递给外部工具，拒绝执行")

    return {
        "decision": decision,
        "risk_score": risk_score,
        "reason": reason,
    }


def update_context_from_tool_output(session: TaskSession, step: TaskStep) -> None:
    """
    根据工具执行结果更新任务链上下文状态。

    如果工具输出包含：
    1. 敏感关键词 → sensitive=True
    2. 提示注入关键词 → tainted=True

    注意：
    analysis["reasons"] 只添加一次，避免前端展示时重复。
    """
    if not step.tool_result:
        return

    output_text = extract_tool_result_text(step.tool_result)
    analysis = analyze_text_security(output_text)

    analysis_reasons = analysis.get("reasons", [])
    for reason in analysis_reasons:
        if reason not in step.reason:
            step.reason.append(reason)

    if analysis.get("sensitive"):
        step.sensitive = True
        session.sensitive_context = True
        session.context_risk_score += 50

        if "当前 Step 输出被标记为敏感数据" not in step.reason:
            step.reason.append("当前 Step 输出被标记为敏感数据")

    if analysis.get("tainted"):
        step.tainted = True
        session.tainted_context = True
        session.context_risk_score += 30

        if "当前 Step 输出被标记为提示注入污染数据" not in step.reason:
            step.reason.append("当前 Step 输出被标记为提示注入污染数据")


def execute_task_session(session: TaskSession) -> TaskSession:
    """
    执行一个多步任务链。

    执行规则：
    1. 每一步都必须先经过原有 Gateway 检查
    2. 再叠加任务链上下文安全规则
    3. decision == allow 才执行工具
    4. 执行后分析工具输出，更新 sensitive/tainted 标记
    5. decision == confirm 或 deny，则停止整个任务链
    """
    session.mark_running()

    for step in session.steps:
        # 1. 处理当前步骤参数
        real_params = build_step_params(session, step)

        # 2. 构造原有 Gateway 使用的 ToolCallRequest
        tool_request = ToolCallRequest(
            user=session.user,
            tool=step.tool,
            params=real_params,
        )

        # 3. 调用原有安全网关
        gateway_result = check_tool_call(tool_request)

        # 4. 叠加任务链上下文安全规则
        final_result = apply_context_security_rules(
            session=session,
            step=step,
            real_params=real_params,
            gateway_result=gateway_result,
        )

        # 5. 把最终判断结果写回当前步骤
        step.decision = final_result.get("decision")
        step.risk_score = final_result.get("risk_score", 0)
        step.reason = final_result.get("reason", [])

        # 6. 如果不是 allow，就停止整个任务链
        if step.decision != "allow":
            step.executed = False
            session.mark_blocked()
            return session

        # 7. allow 才真正执行工具
        tool_result = execute_tool(step.tool, real_params)

        step.executed = True
        step.tool_result = tool_result

        # 8. 分析工具输出，更新上下文安全状态
        update_context_from_tool_output(session, step)

    session.mark_finished()
    return session