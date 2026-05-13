from backend.schemas import ToolCallRequest
from backend.utils import (
    normalize_tool_name,
    normalize_params,
    get_path,
    get_content,
    get_command,
)


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

    user = request.user
    tool = normalize_tool_name(request.tool)
    params = normalize_params(tool, request.params)

    path = get_path(params)
    content = get_content(params)
    command = get_command(params)
    sql = str(params.get("sql", ""))

    path_lower = path.lower().replace("\\", "/")
    content_lower = content.lower()
    command_lower = command.lower()
    sql_lower = sql.lower()
    user_lower = user.lower()

    # 1. 工具自身风险判断
    if tool == "shell.run":
        risk_score += 80
        reason.append("系统命令或代码执行工具风险极高")

    elif tool == "file.delete":
        risk_score += 80
        reason.append("文件删除操作风险极高")

    elif tool == "email.send":
        risk_score += 40
        reason.append("邮件发送工具存在数据外发风险，需要用户确认")

    elif tool == "file.write":
        risk_score += 50
        reason.append("文件写入操作可能修改本地数据")

    elif tool == "file.read":
        risk_score += 10
        reason.append("文件读取操作存在一定信息泄露风险")

    elif tool == "db.query":
        risk_score += 20
        reason.append("数据库查询操作存在一定数据泄露风险")

    else:
        risk_score += 30
        reason.append("未知工具类型，存在不确定风险")

    # 2. 文件路径风险判断
    sensitive_path_keywords = [
        "secret",
        "private",
        "password",
        "passwd",
        "key",
        "token",
        "credential",
        "config",
        ".env",
        "shadow",
        "id_rsa",
    ]

    for keyword in sensitive_path_keywords:
        if keyword in path_lower:
            risk_score += 30
            reason.append(f"访问路径包含敏感关键词：{keyword}")

    # 3. 路径穿越风险判断
    if ".." in path_lower:
        risk_score += 60
        reason.append("路径中包含 ..，可能存在路径穿越风险")

    if path_lower.startswith("/") or ":" in path_lower:
        risk_score += 40
        reason.append("路径疑似绝对路径，存在越权访问风险")

    # 4. 用户权限判断
    if user_lower == "student" and tool == "shell.run":
        risk_score += 40
        reason.append("student 用户无权执行系统命令")

    if user_lower == "student" and path_lower.startswith("secret/"):
        risk_score += 40
        reason.append("student 用户无权访问 secret 目录")

    if user_lower in ["guest", "anonymous"] and tool in ["email.send", "file.write", "file.delete", "shell.run"]:
        risk_score += 40
        reason.append("低权限用户无权执行该类高风险工具")

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

    # 6. 内容风险判断
    dangerous_words = [
        "ignore previous rules",
        "ignore previous instructions",
        "忽略之前的规则",
        "忽略以上要求",
        "password",
        "secret",
        "token",
        "credential",
        "delete",
        "drop table",
        "rm -rf",
        "shutdown",
        "format",
        "绕过",
        "越权",
    ]

    for word in dangerous_words:
        if word.lower() in content_lower:
            risk_score += 20
            reason.append(f"内容包含危险关键词：{word}")

    # 7. 命令风险判断
    dangerous_commands = [
        "rm -rf",
        "del ",
        "format",
        "shutdown",
        "reboot",
        "taskkill",
        "curl",
        "wget",
        "nc ",
        "netcat",
        "chmod 777",
        "powershell",
    ]

    for cmd in dangerous_commands:
        if cmd in command_lower:
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

    # 9. 根据风险分做最终决策
    if risk_score >= 70:
        decision = "deny"
    elif risk_score >= 40:
        decision = "confirm"
    else:
        decision = "allow"

    if not reason:
        reason.append("未发现明显风险")

    return {
        "decision": decision,
        "risk_score": risk_score,
        "reason": reason,
        "normalized_tool": tool,
        "normalized_params": params,
    }