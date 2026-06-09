from __future__ import annotations

import re
import uuid
from typing import List, Optional

from backend.capability.capability_contract import (
    CapabilityContract,
    CapabilityRule,
)


EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

PATH_PATTERN = re.compile(
    r"(?:data/)?(?:public|course|secret|private)/[A-Za-z0-9_\-./]+\.[A-Za-z0-9]+"
    r"|"
    r"\.\./[A-Za-z0-9_\-./]+"
)


DESTRUCTIVE_SQL_KEYWORDS = [
    "drop",
    "delete",
    "truncate",
    "update",
    "insert",
    "alter",
    "grant",
    "revoke",
    "attach database",
    "load_extension",
    "xp_cmdshell",
]

DANGEROUS_SHELL_KEYWORDS = [
    "rm -rf",
    "del /s",
    "format",
    "shutdown",
    "reboot",
    "curl",
    "wget",
    "nc ",
    "netcat",
    "powershell",
    "cmd.exe",
    "certutil",
    "bitsadmin",
    "ssh ",
    "scp ",
    "ftp ",
    "sudo",
    "su -",
    "chmod 777",
    "chown",
    "python -c",
    "bash -c",
    "sh -c",
]

SAFE_ADMIN_SHELL_COMMANDS = [
    "pwd",
    "dir",
    "ls",
    "whoami",
]


def _new_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:12]}"


def _unique(items: List[str]) -> List[str]:
    result = []
    seen = set()

    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)

    return result


def _normalize_path(path: str) -> str:
    """
    统一资源路径格式。

    用户可能输入：
    - public/notice.txt
    - data/public/notice.txt
    - secret/password.txt
    - ../secret/password.txt

    系统内部尽量统一成：
    - data/public/notice.txt
    - data/secret/password.txt
    - ../secret/password.txt
    """

    path = path.strip().replace("\\", "/")
    path = path.strip("'\"，。；;,. ")

    if path.startswith("../"):
        return path

    if path.startswith("data/"):
        return path

    if path.startswith(("public/", "course/", "secret/", "private/")):
        return f"data/{path}"

    return path


def _contains_path_traversal(path: str) -> bool:
    normalized = str(path).replace("\\", "/").lower()
    return (
        "../" in normalized
        or "/.." in normalized
        or "%2e%2e" in normalized
        or "%252e%252e" in normalized
    )


def extract_emails(text: str) -> List[str]:
    """
    从用户任务中提取邮箱地址。
    """

    return _unique(EMAIL_PATTERN.findall(text or ""))


def extract_paths(text: str) -> List[str]:
    """
    从用户任务中提取文件路径。
    """

    raw_paths = PATH_PATTERN.findall(text or "")
    paths = [_normalize_path(path) for path in raw_paths]
    return _unique(paths)


def _contains_any(text: str, keywords: List[str]) -> bool:
    text = text.lower()

    for keyword in keywords:
        if keyword.lower() in text:
            return True

    return False


def _is_read_intent(text: str, paths: List[str]) -> bool:
    """
    判断任务是否包含读取资源的意图。
    """

    read_keywords = [
        "读取",
        "读",
        "查看",
        "打开",
        "获取",
        "read",
        "open",
        "get",
    ]

    return bool(paths) or _contains_any(text, read_keywords)


def _is_send_intent(text: str, emails: List[str]) -> bool:
    """
    判断任务是否包含外发意图。
    """

    send_keywords = [
        "发送",
        "发给",
        "邮件",
        "邮箱",
        "转发",
        "send",
        "email",
        "mail",
    ]

    return bool(emails) or _contains_any(text, send_keywords)


def _is_db_query_intent(text: str) -> bool:
    """
    判断用户任务是否有数据库查询意图。
    """

    db_keywords = [
        "数据库",
        "查询",
        "sql",
        "select",
        "notices 表",
        "notices",
        "db.query",
        "table",
    ]

    return _contains_any(text, db_keywords)


def _is_safe_db_select_intent(text: str) -> bool:
    """
    只给明显的只读数据库查询授予 db.query 能力。

    破坏性 SQL 即使由 admin 发起，也不应该进入自动授权能力。
    """

    text_lower = text.lower()

    if not _is_db_query_intent(text_lower):
        return False

    if _contains_any(text_lower, DESTRUCTIVE_SQL_KEYWORDS):
        return False

    safe_select_keywords = [
        "select",
        "查询",
        "公开",
        "总结",
        "notices",
        "只读",
    ]

    return _contains_any(text_lower, safe_select_keywords)


def _is_shell_intent(text: str) -> bool:
    """
    判断用户任务是否有 shell 命令执行意图。
    """

    shell_keywords = [
        "shell",
        "命令",
        "执行",
        "运行",
        "pwd",
        "dir",
        "ls",
        "whoami",
        "curl",
        "wget",
        "powershell",
    ]

    return _contains_any(text, shell_keywords)


def _is_safe_admin_shell_intent(user: str, text: str) -> bool:
    """
    只允许管理员在任务合约中申请极少数低风险 shell 能力。

    注意：
    - 普通 user 不授予 shell.run。
    - 出现 curl/wget/rm 等危险关键词时不授予 shell.run。
    - 即使是安全命令，也设置 require_approval=True，让 Runtime 进入人工确认。
    """

    text_lower = text.lower()

    if user != "admin":
        return False

    if not _is_shell_intent(text_lower):
        return False

    if _contains_any(text_lower, DANGEROUS_SHELL_KEYWORDS):
        return False

    return _contains_any(text_lower, SAFE_ADMIN_SHELL_COMMANDS)


def _split_paths_by_sensitivity(paths: List[str]) -> tuple[List[str], List[str]]:
    """
    将路径分成允许候选和禁止候选。

    public/course 默认可以作为任务授权对象；
    secret/private/../ 默认视为禁止资源。
    """

    allowed = []
    forbidden = []

    for path in paths:
        if _contains_path_traversal(path):
            forbidden.append(path)
        elif path.startswith(("data/public/", "data/course/")):
            allowed.append(path)
        elif path.startswith(("data/secret/", "data/private/", "../")):
            forbidden.append(path)
        else:
            forbidden.append(path)

    return allowed, forbidden


def compile_capability_contract(
    user: str,
    original_task: str,
    task_id: Optional[str] = None,
    max_steps: int = 5,
    risk_budget: int = 80,
) -> CapabilityContract:
    """
    将用户任务编译为 CapabilityContract v2。

    本版本增强点：
    1. 继续保持 secret/private/path traversal 默认禁止；
    2. 对明确的公开文件读取授予最小 file.read 能力；
    3. 对明确邮箱发送任务授予限定收件人的 email.send 能力；
    4. 对明显安全的只读 SELECT 查询授予 db.query 能力；
    5. 对管理员低风险 shell 命令授予 shell.run 能力，但必须人工确认；
    6. 对 DROP/curl/rm 等高危数据库或 shell 行为继续禁止。
    """

    task_id = task_id or _new_task_id()

    emails = extract_emails(original_task)
    paths = extract_paths(original_task)

    allowed_paths, forbidden_paths_from_task = _split_paths_by_sensitivity(paths)

    capabilities: List[CapabilityRule] = []
    reasons: List[str] = []

    has_read_intent = _is_read_intent(original_task, paths)
    has_send_intent = _is_send_intent(original_task, emails)
    has_safe_db_query_intent = _is_safe_db_select_intent(original_task)
    has_db_query_intent = _is_db_query_intent(original_task)
    has_safe_admin_shell_intent = _is_safe_admin_shell_intent(user, original_task)
    has_shell_intent = _is_shell_intent(original_task)

    if has_read_intent:
        if allowed_paths:
            read_resources = allowed_paths
            reasons.append(
                "Detected explicit public/course file read target, grant file.read only for these resources."
            )
        else:
            read_resources = ["data/public/*", "data/course/*"]
            reasons.append(
                "Detected read intent without explicit safe path, grant file.read only for public/course resources."
            )

        capabilities.append(
            CapabilityRule(
                tool="file.read",
                mode="read",
                resource_patterns=read_resources,
                allowed_input_labels=[],
                output_labels=["public"],
                risk_cost=10,
                require_approval=False,
            )
        )

    if has_send_intent:
        if emails:
            recipients = emails
            reasons.append(
                "Detected explicit email recipient, grant email.send only to listed recipients."
            )
        else:
            recipients = []
            reasons.append(
                "Detected send intent but no explicit recipient, external write requires approval."
            )

        capabilities.append(
            CapabilityRule(
                tool="email.send",
                mode="external_write",
                recipients=recipients,
                allowed_input_labels=["public"],
                output_labels=[],
                risk_cost=20,
                require_approval=True,
            )
        )

    if has_safe_db_query_intent:
        capabilities.append(
            CapabilityRule(
                tool="db.query",
                mode="query",
                resource_patterns=["*"],
                allowed_input_labels=[],
                output_labels=["public"],
                risk_cost=15,
                require_approval=False,
            )
        )
        reasons.append(
            "Detected safe read-only database query intent, grant db.query for SELECT-like public query."
        )
    elif has_db_query_intent:
        reasons.append(
            "Detected database intent but it is not a clear safe SELECT query, keep db.query forbidden."
        )

    if has_safe_admin_shell_intent:
        capabilities.append(
            CapabilityRule(
                tool="shell.run",
                mode="execute",
                resource_patterns=[],
                allowed_input_labels=[],
                output_labels=["public"],
                risk_cost=35,
                require_approval=True,
            )
        )
        reasons.append(
            "Detected admin low-risk shell intent, grant shell.run with human approval required."
        )
    elif has_shell_intent:
        reasons.append(
            "Detected shell intent but it is not a safe admin shell command, keep shell.run forbidden."
        )

    forbidden_tools = [
        "code.exec",
        "run_code",
    ]

    if not has_safe_admin_shell_intent:
        forbidden_tools.append("shell.run")

    if not has_safe_db_query_intent:
        forbidden_tools.append("db.query")

    forbidden_resources = _unique(
        [
            "data/secret/*",
            "data/private/*",
            "../*",
            "data/public/../*",
            "data/course/../*",
        ]
        + forbidden_paths_from_task
    )

    if forbidden_paths_from_task:
        reasons.append(
            "Detected sensitive or unsafe path in the task text, add it to forbidden resources."
        )

    if not capabilities:
        reasons.append(
            "No clear safe capability detected, generate a restrictive contract with no granted tool capability."
        )

    return CapabilityContract(
        task_id=task_id,
        user=user,
        original_task=original_task,
        task_goal=original_task,
        capabilities=capabilities,
        forbidden_tools=forbidden_tools,
        forbidden_resources=forbidden_resources,
        max_steps=max_steps,
        risk_budget=risk_budget,
        expires_at=None,
        approval_required_when=[
            "external_write",
            "tainted_input",
            "sensitive_input",
        ],
        reason=reasons,
    )
