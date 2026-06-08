from backend.schemas import ToolCallRequest, GatewayResponse
from backend.gateway.policy_loader import (
    get_tool_risk,
    get_decision_threshold,
    get_user_role,
    match_role_policy,
    get_resource_risk,
    get_dangerous_keywords,
    match_keywords,
    get_supported_tools,
    get_required_params,
    get_agent_plan_policy,
    get_risk_score,
    get_internal_email_domains,
)
from backend.gateway.semantic_guard import semantic_check_tool_call
from backend.utils import (
    normalize_tool_name,
    normalize_params,
    get_path,
    get_content,
    get_command,
)
from backend.task_contract.contract_models import TaskAuthContract
from backend.task_contract.contract_enforcer import check_call_against_contract
from backend.capability.capability_contract import CapabilityContract
from backend.capability.capability_enforcer import enforce_capability_contract


TOOL_REASON_MAP = {
    "shell.run": "系统命令或代码执行工具风险极高",
    "file.delete": "文件删除操作风险极高",
    "email.send": "邮件发送工具存在数据外发风险，需要用户确认",
    "file.write": "文件写入操作可能修改本地数据",
    "file.read": "文件读取操作存在一定信息泄露风险",
    "db.query": "数据库查询操作存在一定数据泄露风险",
}


def get_risk_level(score: int) -> str:
    """
    将风险分转换为风险等级，便于前端展示、人工确认和审计分析。
    """
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def build_explanations(reason: list[str]) -> list[dict]:
    """
    将原有 reason 文本转换为结构化解释。
    这样既保留原有判断逻辑，又能让前端和审计模块展示风险来源。
    """
    explanations = []

    for item in reason:
        text = str(item)

        if "路径" in text or "secret" in text or "资源风险" in text or "访问路径" in text:
            factor = "resource_path"
        elif "角色" in text or "权限" in text or "user" in text or "admin" in text:
            factor = "role_policy"
        elif "邮件" in text or "外发" in text or "接收人" in text:
            factor = "external_output"
        elif "提示注入" in text or "ignore previous" in text or "忽略" in text:
            factor = "prompt_injection"
        elif "命令" in text or "shell" in text or "高危操作" in text:
            factor = "command"
        elif "SQL" in text or "数据库" in text or "SELECT" in text:
            factor = "database"
        elif "Agent" in text or "置信度" in text or "计划" in text:
            factor = "agent_plan"
        elif "任务授权合约" in text or "Capability Contract" in text or "合约" in text:
            factor = "task_contract"
        elif "工具" in text:
            factor = "tool"
        elif "参数" in text:
            factor = "params"
        else:
            factor = "general"

        explanations.append(
            {
                "factor": factor,
                "reason": text,
            }
        )

    return explanations


def build_gateway_result(
    decision: str,
    risk_score: int,
    reason: list[str],
    user: str,
    role: str,
    tool: str,
    params: dict,
) -> dict:
    """
    统一构造 Gateway 返回值，保证所有提前 return 和最终 return 字段一致。
    """
    return {
        "decision": decision,
        "risk_score": risk_score,
        "risk_level": get_risk_level(risk_score),
        "reason": reason,
        "explanations": build_explanations(reason),
        "user": user,
        "role": role,
        "normalized_tool": tool,
        "normalized_params": params,
    }


def check_tool_call(request: ToolCallRequest):
    """
    授权网关核心逻辑：
    1. 统一工具名
    2. 统一参数名
    3. 根据工具类型、路径、内容、用户身份等计算风险分
    4. 返回 allow / confirm / deny
    """
    risk_score = 0
    reason = []
    hard_deny = False

    user = request.user
    role = get_user_role(user)

    tool = normalize_tool_name(request.tool)
    params = normalize_params(tool, request.params)

    path = get_path(params)
    content = get_content(params)
    command = get_command(params)
    sql = str(params.get("sql", ""))

    supported_tools = set(get_supported_tools())
    required_params = get_required_params()
    agent_plan_policy = get_agent_plan_policy()

    if tool not in supported_tools:
        unknown_tool_score = get_risk_score("unknown_tool", 100)
        unknown_tool_reason = [
            f"工具 {tool} 不在系统支持列表中。",
            "未知工具不能自动执行，已按失败关闭原则拒绝。",
        ]

        return build_gateway_result(
            decision="deny",
            risk_score=unknown_tool_score,
            reason=unknown_tool_reason,
            user=user,
            role=role,
            tool=tool,
            params=params,
        )

    low_confidence_force_confirm = False
    capability_force_confirm = False
    semantic_force_confirm = False

    if request.agent_confidence is not None:
        confidence = float(request.agent_confidence)
        min_confirm_confidence = agent_plan_policy["min_confirm_confidence"]
        min_auto_confidence = agent_plan_policy["min_auto_confidence"]

        if confidence < min_confirm_confidence:
            low_confidence_score = get_risk_score("low_confidence_deny", 100)
            low_confidence_reason = [
                f"Agent 计划置信度过低：{confidence}",
                "系统无法可靠确认用户意图，拒绝自动执行。",
            ]

            return build_gateway_result(
                decision="deny",
                risk_score=low_confidence_score,
                reason=low_confidence_reason,
                user=user,
                role=role,
                tool=tool,
                params=params,
            )

        if confidence < min_auto_confidence:
            risk_score += get_risk_score("low_confidence_confirm", 45)
            low_confidence_force_confirm = True
            reason.append(
                f"Agent 计划置信度较低：{confidence}，提高风险分并至少要求人工确认。"
            )

    missing_params = []
    for name in required_params.get(tool, []):
        value = str(params.get(name, "")).strip()
        if not value or value == "unknown":
            missing_params.append(name)

    if missing_params:
        risk_score += get_risk_score("missing_params", 60)
        reason.append(f"工具调用缺少必要参数：{', '.join(missing_params)}")

        return build_gateway_result(
            decision="confirm",
            risk_score=risk_score,
            reason=reason
            + [
                "参数不完整，不能自动执行，需要用户补充信息或人工确认。"
            ],
            user=user,
            role=role,
            tool=tool,
            params=params,
        )

    path_lower = path.lower().replace("\\", "/")
    content_lower = content.lower()
    command_lower = command.lower()
    sql_lower = sql.lower()

    # 0.5 Embedding 语义风险检测：
    # 用本地句向量相似度识别关键词规则难以覆盖的模糊风险意图。
    semantic_result = semantic_check_tool_call(
        user=user,
        role=role,
        tool=tool,
        params=params,
        path=path,
        content=content,
        command=command,
        sql=sql,
    )

    if semantic_result.get("enabled"):
        semantic_risk_score = int(semantic_result.get("risk_score", 0))
        risk_score += semantic_risk_score

        labels = semantic_result.get("labels", [])
        if labels:
            reason.append(
                f"语义检测命中风险标签：{', '.join(labels)}，风险分 +{semantic_risk_score}"
            )

        for item in semantic_result.get("reasons", []):
            reason.append(f"语义检测：{item}")

        if semantic_result.get("force_confirm"):
            semantic_force_confirm = True

        if semantic_result.get("hard_deny"):
            hard_deny = True
            reason.append("语义检测判定存在高危意图，本次调用进入拒绝路径。")

    # 0. 任务授权合约检查：
    # 如果请求携带 task_contract，则先判断本次工具调用是否偏离任务目标。
    # 支持两种合约：
    # - v1 TaskAuthContract
    # - v2 CapabilityContract
    if request.task_contract is not None:
        try:
            contract_data = request.task_contract

            is_capability_v2 = (
                contract_data.get("contract_version") == "2.0"
                or "capabilities" in contract_data
            )

            if is_capability_v2:
                capability_contract = CapabilityContract(**contract_data)

                contract_result = enforce_capability_contract(
                    contract=capability_contract,
                    tool=tool,
                    params=params,
                    input_labels=request.input_labels,
                    current_step=request.current_step,
                    used_risk=request.used_risk,
                )

                risk_score += contract_result.risk_score
                reason.append("已启用 Capability Contract v2 检查。")
                reason.extend(contract_result.reason)

                if contract_result.decision == "deny":
                    return build_gateway_result(
                        decision="deny",
                        risk_score=risk_score,
                        reason=reason,
                        user=user,
                        role=role,
                        tool=tool,
                        params=params,
                    )

                if contract_result.decision == "confirm":
                    capability_force_confirm = True

            else:
                task_contract = TaskAuthContract(**contract_data)

                contract_result = check_call_against_contract(
                    contract=task_contract,
                    tool=tool,
                    params=params,
                )

                risk_score += contract_result.risk_score
                reason.append("已启用任务授权合约检查。")
                reason.extend(contract_result.reason)

                if contract_result.decision == "deny":
                    return build_gateway_result(
                        decision="deny",
                        risk_score=risk_score,
                        reason=reason,
                        user=user,
                        role=role,
                        tool=tool,
                        params=params,
                    )

        except Exception as e:
            risk_score += get_risk_score("contract_parse_error", 100)
            reason.append("任务授权合约解析失败，拒绝本次工具调用。")
            reason.append(str(e))

            return build_gateway_result(
                decision="deny",
                risk_score=risk_score,
                reason=reason,
                user=user,
                role=role,
                tool=tool,
                params=params,
            )

    # 1. 工具自身风险判断：
    # 从 config/policy.yaml 读取基础风险分
    tool_base_risk = get_tool_risk(tool)
    risk_score += tool_base_risk
    reason.append(
        TOOL_REASON_MAP.get(
            tool,
            f"未知工具类型，使用默认基础风险分：{tool_base_risk}",
        )
    )

    # 2. 文件路径风险判断：
    # 从 config/policy.yaml 的 resource_risk 中读取
    resource_risk_score, resource_reasons = get_resource_risk(path)
    risk_score += resource_risk_score
    reason.extend(resource_reasons)

    # 3. 路径穿越风险判断
    if ".." in path_lower:
        risk_score += get_risk_score("path_traversal", 60)
        hard_deny = True
        reason.append("路径中包含 ..，可能存在路径穿越风险")

    if path_lower.startswith("/") or ":" in path_lower:
        risk_score += get_risk_score("absolute_path", 40)
        hard_deny = True
        reason.append("路径疑似绝对路径，存在越权访问风险")

    # 4. 角色权限策略判断：
    # 从 config/policy.yaml 的 roles 中读取
    policy_decision, policy_reason = match_role_policy(role, tool, path_lower)

    if policy_decision == "deny":
        risk_score += get_risk_score("role_deny", 70)
        reason.append(policy_reason)
    elif policy_decision == "confirm":
        reason.append(policy_reason)
    elif policy_decision == "allow":
        reason.append(policy_reason)
    else:
        risk_score += get_risk_score("no_role_policy", 20)
        reason.append(policy_reason)

    # 5. 邮件外发风险判断
    if tool == "email.send":
        to = str(params.get("to", "")).strip()
        internal_domains = get_internal_email_domains()

        if not to or to == "unknown":
            risk_score += get_risk_score("missing_email_to", 20)
            reason.append("邮件接收人为空或无法识别，存在误发风险")
        elif internal_domains and not any(
            to.lower().endswith(domain) for domain in internal_domains
        ):
            risk_score += get_risk_score("external_email", 25)
            reason.append("邮件发送目标不是内部可信邮箱，存在数据外发风险")

        sensitive_content_keywords = get_dangerous_keywords("sensitive_content")
        if any(word in content_lower for word in sensitive_content_keywords):
            risk_score += get_risk_score("sensitive_email_content", 30)
            reason.append("邮件内容包含敏感信息关键词")

    # 6. 内容风险判断：
    # 从 config/policy.yaml 的 dangerous_keywords 中读取
    prompt_injection_keywords = get_dangerous_keywords("prompt_injection")
    matched_prompt_keywords = match_keywords(content, prompt_injection_keywords)

    for word in matched_prompt_keywords:
        risk_score += get_risk_score("prompt_injection_keyword", 30)
        reason.append(f"内容命中提示注入关键词：{word}")

    sensitive_content_keywords = get_dangerous_keywords("sensitive_content")
    matched_sensitive_keywords = match_keywords(content, sensitive_content_keywords)

    for word in matched_sensitive_keywords:
        risk_score += get_risk_score("sensitive_content_keyword", 20)
        reason.append(f"内容包含敏感信息关键词：{word}")

    # 7. 命令风险判断：
    # 从 config/policy.yaml 的 dangerous_keywords.command 中读取
    dangerous_commands = get_dangerous_keywords("command")
    matched_commands = match_keywords(command, dangerous_commands)

    for cmd in matched_commands:
        risk_score += get_risk_score("command_keyword", 30)
        reason.append(f"命令中包含高危操作：{cmd}")

    # 8. SQL 风险判断：
    # 从 config/policy.yaml 的 dangerous_keywords.sql 中读取
    dangerous_sql = get_dangerous_keywords("sql")

    if tool == "db.query":
        for keyword in dangerous_sql:
            if keyword in sql_lower:
                risk_score += get_risk_score("sql_keyword", 50)
                reason.append(f"SQL 语句包含高危操作：{keyword}")

        if sql_lower and not sql_lower.strip().startswith("select"):
            risk_score += get_risk_score("non_select_sql", 30)
            reason.append("当前数据库工具只建议执行 SELECT 查询")

    # 9. 根据风险分和角色策略做最终决策
    threshold = get_decision_threshold()
    allow_max = int(threshold.get("allow_max", 39))
    confirm_max = int(threshold.get("confirm_max", 69))

    # 先根据风险分得到基础决策
    if risk_score <= allow_max:
        decision = "allow"
    elif risk_score <= confirm_max:
        decision = "confirm"
    else:
        decision = "deny"

    # 再根据角色策略进行修正
    # 明确违规优先级最高：路径穿越、绝对路径、角色 deny 都必须拒绝。
    if hard_deny or policy_decision == "deny":
        decision = "deny"

    # confirm 策略表示该角色允许申请执行，但必须经过人工确认。
    elif policy_decision == "confirm":
        decision = "confirm"

    # allow 策略表示用户有权限执行该工具
    # 但如果工具本身风险极高，不直接放行，而是降级为人工确认
    elif policy_decision == "allow" and decision == "deny":
        decision = "confirm"
        reason.append("用户角色具备该操作权限，但操作风险较高，转入人工确认")

    if low_confidence_force_confirm and decision == "allow":
        decision = "confirm"
        reason.append("由于 Agent 计划置信度不足，本次操作不能自动放行，转入人工确认。")

    if capability_force_confirm and decision == "allow":
        decision = "confirm"
        reason.append("Capability Contract v2 要求本次工具调用进入人工确认。")

    if semantic_force_confirm and decision == "allow":
        decision = "confirm"
        reason.append("语义检测发现潜在风险，本次操作不能自动放行，转入人工确认。")

    if not reason:
        reason.append("未发现明显风险")

    return build_gateway_result(
        decision=decision,
        risk_score=risk_score,
        reason=reason,
        user=user,
        role=role,
        tool=tool,
        params=params,
    )
