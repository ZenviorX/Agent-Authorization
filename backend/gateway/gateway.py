from backend.schemas import ToolCallRequest, GatewayResponse
from backend.gateway.policy_loader import (
    get_tool_risk,
    get_decision_threshold,
    get_user_role,
    match_role_policy,
    get_resource_risk,
    get_dangerous_keywords,
    match_keywords,
)
from backend.utils import (
    normalize_tool_name,
    normalize_params,
    get_path,
    get_content,
    get_command,
)

<<<<<<< HEAD
SUPPORTED_TOOLS = {
    "file.read",
    "file.write",
    "file.delete",
    "email.send",
    "shell.run",
    "db.query",
}

REQUIRED_PARAMS = {
    "file.read": ["path"],
    "file.write": ["path", "content"],
    "file.delete": ["path"],
    "email.send": ["to", "content"],
    "shell.run": ["command"],
    "db.query": ["sql"],
}
=======
from backend.task_contract.contract_models import TaskAuthContract
from backend.task_contract.contract_enforcer import check_call_against_contract
>>>>>>> e9ccbc9bc675b06c259aef1c406a8f74a460dff7

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

    if tool not in SUPPORTED_TOOLS:
        return {
            "decision": "deny",
            "risk_score": 100,
            "reason": [
                f"工具 {tool} 不在系统支持列表中。",
                "未知工具不能自动执行，已按失败关闭原则拒绝。",
            ],
            "user": user,
            "role": role,
            "normalized_tool": tool,
            "normalized_params": params,
        }
    
    low_confidence_force_confirm = False

    if request.agent_confidence is not None:
        confidence = float(request.agent_confidence)

        if confidence < 0.55:
            return {
                "decision": "deny",
                "risk_score": 100,
                "reason": [
                    f"Agent 计划置信度过低：{confidence}",
                    "系统无法可靠确认用户意图，拒绝自动执行。",
                ],
                "user": user,
                "role": role,
                "normalized_tool": tool,
                "normalized_params": params,
            }

        if confidence < 0.85:
            risk_score += 45
            low_confidence_force_confirm = True
            reason.append(
                f"Agent 计划置信度较低：{confidence}，提高风险分并至少要求人工确认。"
            )
    
    missing_params = []

    for name in REQUIRED_PARAMS.get(tool, []):
        value = str(params.get(name, "")).strip()
        if not value or value == "unknown":
            missing_params.append(name)

    if missing_params:
        risk_score += 60
        reason.append(f"工具调用缺少必要参数：{', '.join(missing_params)}")

        return {
            "decision": "confirm",
            "risk_score": risk_score,
            "reason": reason + [
                "参数不完整，不能自动执行，需要用户补充信息或人工确认。"
            ],
            "user": user,
            "role": role,
            "normalized_tool": tool,
            "normalized_params": params,
        }

    path_lower = path.lower().replace("\\", "/")
    content_lower = content.lower()
    command_lower = command.lower()
    sql_lower = sql.lower()

    # 0. 任务授权合约检查：如果请求中携带 task_contract，则先判断本次工具调用是否偏离任务目标
    if request.task_contract is not None:
        try:
            task_contract = TaskAuthContract(**request.task_contract)
            contract_result = check_call_against_contract(
                contract=task_contract,
                tool=tool,
                params=params
            )

            risk_score += contract_result.risk_score

            reason.append("已启用任务授权合约检查。")
            reason.extend(contract_result.reason)

            if contract_result.decision == "deny":
                return{
                            "decision": "deny",
        "risk_score": risk_score,
        "reason": reason,
        "user": user,
        "role": role,
        "normalized_tool": tool,
        "normalized_params": params
                }
        except Exception as e:
            risk_score += 100
            reason.append("任务授权合约解析失败，拒绝本次工具调用。")
            reason.append(str(e))

            return{
                       "decision": "deny",
        "risk_score": risk_score,
        "reason": reason,
        "user": user,
        "role": role,
        "normalized_tool": tool,
        "normalized_params": params
            }

    # 1. 工具自身风险判断：从 config/policy.yaml 读取基础风险分
    tool_base_risk = get_tool_risk(tool)
    risk_score += tool_base_risk

    tool_reason_map = {
        "shell.run": "系统命令或代码执行工具风险极高",
        "file.delete": "文件删除操作风险极高",
        "email.send": "邮件发送工具存在数据外发风险，需要用户确认",
        "file.write": "文件写入操作可能修改本地数据",
        "file.read": "文件读取操作存在一定信息泄露风险",
        "db.query": "数据库查询操作存在一定数据泄露风险",
    }

    reason.append(
        tool_reason_map.get(
            tool,
            f"未知工具类型，使用默认基础风险分：{tool_base_risk}"
        )
    )
    # 2. 文件路径风险判断：从 config/policy.yaml 的 resource_risk 中读取
    resource_risk_score, resource_reasons = get_resource_risk(path)

    risk_score += resource_risk_score
    reason.extend(resource_reasons)

    # 3. 路径穿越风险判断
    if ".." in path_lower:
        risk_score += 60
        hard_deny = True
        reason.append("路径中包含 ..，可能存在路径穿越风险")

    if path_lower.startswith("/") or ":" in path_lower:
        risk_score += 40
        hard_deny = True
        reason.append("路径疑似绝对路径，存在越权访问风险")

    # 4. 角色权限策略判断：从 config/policy.yaml 的 roles 中读取
    policy_decision, policy_reason = match_role_policy(role, tool, path_lower)

    if policy_decision == "deny":
        risk_score += 70
        reason.append(policy_reason)

    elif policy_decision == "confirm":
        reason.append(policy_reason)

    elif policy_decision == "allow":
        reason.append(policy_reason)

    else:
        risk_score += 20
        reason.append(policy_reason)

    # 5. 邮件外发风险判断
    if tool == "email.send":
        to = str(params.get("to", "")).strip()

        if not to or to == "unknown":
            risk_score += 20
            reason.append("邮件接收人为空或无法识别，存在误发风险")

        elif not to.endswith("@sdu.edu.cn"):
            risk_score += 25
            reason.append("邮件发送目标不是校内邮箱，存在数据外发风险")

        if any(word in content_lower for word in ["password", "secret", "token", "密钥", "密码"]):
            risk_score += 30
            reason.append("邮件内容包含敏感信息关键词")

    # 6. 内容风险判断：从 config/policy.yaml 的 dangerous_keywords 中读取
    prompt_injection_keywords = get_dangerous_keywords("prompt_injection")
    matched_prompt_keywords = match_keywords(content, prompt_injection_keywords)

    for word in matched_prompt_keywords:
        risk_score += 30
        reason.append(f"内容命中提示注入关键词：{word}")

    sensitive_content_keywords = ["password", "secret", "token", "credential", "密钥", "密码"]
    matched_sensitive_keywords = match_keywords(content, sensitive_content_keywords)

    for word in matched_sensitive_keywords:
        risk_score += 20
        reason.append(f"内容包含敏感信息关键词：{word}")

    # 7. 命令风险判断：从 config/policy.yaml 的 dangerous_keywords.command 中读取
    dangerous_commands = get_dangerous_keywords("command")
    matched_commands = match_keywords(command, dangerous_commands)

    for cmd in matched_commands:
        risk_score += 30
        reason.append(f"命令中包含高危操作：{cmd}")

    # 8. SQL 风险判断
    dangerous_sql = [
        "drop table",
        "delete from",
        "truncate",
        "update ",
        "insert into",
        "alter table",
        "create table",
    ]

    if tool == "db.query":
        for keyword in dangerous_sql:
            if keyword in sql_lower:
                risk_score += 50
                reason.append(f"SQL 语句包含高危操作：{keyword}")

        if sql_lower and not sql_lower.strip().startswith("select"):
            risk_score += 30
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

    if not reason:
        reason.append("未发现明显风险")

    return {
        "decision": decision,
        "risk_score": risk_score,
        "reason": reason,
        "user": user,
        "role": role,
        "normalized_tool": tool,
        "normalized_params": params,
    }
