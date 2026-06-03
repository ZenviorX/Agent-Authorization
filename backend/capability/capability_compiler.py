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


def _split_paths_by_sensitivity(paths: List[str]) -> tuple[List[str], List[str]]:
    """
    将路径分成允许候选和禁止候选。

    public/course 默认可以作为任务授权对象；
    secret/private/../ 默认视为禁止资源。
    """

    allowed = []
    forbidden = []

    for path in paths:
        if path.startswith(("data/public/", "data/course/")):
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

    这是主干升级的关键入口：
    用户不是直接拿到所有工具权限，
    而是根据本次任务获得一个最小能力边界。
    """

    task_id = task_id or _new_task_id()

    emails = extract_emails(original_task)
    paths = extract_paths(original_task)

    allowed_paths, forbidden_paths_from_task = _split_paths_by_sensitivity(paths)

    capabilities: List[CapabilityRule] = []
    reasons: List[str] = []

    has_read_intent = _is_read_intent(original_task, paths)
    has_send_intent = _is_send_intent(original_task, emails)

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

    forbidden_tools = [
        "shell.run",
        "code.exec",
        "db.query",
        "run_code",
    ]

    forbidden_resources = _unique(
        [
            "data/secret/*",
            "data/private/*",
            "../*",
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
    