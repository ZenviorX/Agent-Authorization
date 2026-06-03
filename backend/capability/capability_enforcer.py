from __future__ import annotations

from fnmatch import fnmatch
from typing import Any, Dict, List, Optional

from backend.capability.capability_contract import (
    CapabilityContract,
    CapabilityCheckResult,
    CapabilityRule,
)


SENSITIVE_LABELS = {"sensitive", "secret"}
TAINTED_LABELS = {"tainted", "prompt_injection", "unknown"}
RESOURCE_MODES = {"read", "write", "delete", "query"}
EXTERNAL_WRITE_MODE = "external_write"


def _normalize_path(path: str) -> str:
    """
    将路径统一成系统内部格式。

    例如：
    public/notice.txt -> data/public/notice.txt
    secret/password.txt -> data/secret/password.txt
    ../secret/password.txt -> ../secret/password.txt
    """

    path = str(path).strip().replace("\\", "/")
    path = path.strip("'\"，。；;,. ")

    if path.startswith("../"):
        return path

    if path.startswith("data/"):
        return path

    if path.startswith(("public/", "course/", "secret/", "private/")):
        return f"data/{path}"

    return path


def _match_any(value: str, patterns: List[str]) -> bool:
    """
    判断 value 是否匹配任意一个 pattern。
    支持 data/public/* 这种通配符。
    """

    if not patterns:
        return True

    return any(fnmatch(value, pattern) for pattern in patterns)


def _extract_resource(params: Dict[str, Any]) -> Optional[str]:
    """
    从工具参数中提取资源路径。

    兼容不同字段名：
    - path
    - file_path
    - resource
    - filename
    """

    for key in ["path", "file_path", "resource", "filename"]:
        value = params.get(key)
        if value:
            return _normalize_path(str(value))

    return None


def _extract_recipient(params: Dict[str, Any]) -> Optional[str]:
    """
    从工具参数中提取外发目标。

    兼容不同字段名：
    - to
    - recipient
    - email
    - to_email
    """

    for key in ["to", "recipient", "email", "to_email"]:
        value = params.get(key)
        if value:
            return str(value).strip()

    return None


def _is_forbidden_tool(tool: str, contract: CapabilityContract) -> bool:
    return tool in contract.forbidden_tools


def _is_forbidden_resource(resource: Optional[str], contract: CapabilityContract) -> bool:
    if not resource:
        return False

    return _match_any(resource, contract.forbidden_resources)


def _resource_matches_rule(
    rule: CapabilityRule,
    tool: str,
    resource: Optional[str],
) -> bool:
    """
    检查资源型工具是否匹配能力规则。
    """

    if rule.tool != tool:
        return False

    if rule.mode in RESOURCE_MODES:
        if not resource:
            return False

        return _match_any(resource, rule.resource_patterns)

    return True


def _recipient_matches_rule(
    rule: CapabilityRule,
    recipient: Optional[str],
) -> bool:
    """
    检查外发目标是否匹配能力规则。
    """

    if rule.mode != EXTERNAL_WRITE_MODE:
        return True

    if not rule.recipients:
        return False

    if not recipient:
        return False

    return recipient in rule.recipients


def _find_matching_rule(
    contract: CapabilityContract,
    tool: str,
    resource: Optional[str],
    recipient: Optional[str],
) -> Optional[CapabilityRule]:
    """
    在合约中找到可以覆盖当前工具调用的能力规则。
    """

    for rule in contract.capabilities:
        if rule.tool != tool:
            continue

        if not _resource_matches_rule(rule, tool, resource):
            continue

        if not _recipient_matches_rule(rule, recipient):
            continue

        return rule

    return None


def enforce_capability_contract(
    contract: CapabilityContract,
    tool: str,
    params: Dict[str, Any],
    input_labels: Optional[List[str]] = None,
    current_step: int = 1,
    used_risk: int = 0,
) -> CapabilityCheckResult:
    """
    检查某一次工具调用是否符合 CapabilityContract v2。

    参数说明：
    - contract：任务级能力合约
    - tool：当前请求调用的工具，例如 file.read / email.send
    - params：工具参数，例如 {"path": "public/notice.txt"}
    - input_labels：输入数据标签，例如 ["public"] / ["tainted"] / ["secret"]
    - current_step：当前是第几步工具调用
    - used_risk：任务目前已经消耗的风险预算
    """

    input_labels = input_labels or []
    reasons: List[str] = []

    resource = _extract_resource(params)
    recipient = _extract_recipient(params)

    if current_step > contract.max_steps:
        return CapabilityCheckResult(
            decision="deny",
            risk_score=100,
            reason=[
                f"Current step {current_step} exceeds contract max_steps {contract.max_steps}."
            ],
        )

    if _is_forbidden_tool(tool, contract):
        return CapabilityCheckResult(
            decision="deny",
            risk_score=100,
            reason=[f"Tool {tool} is explicitly forbidden by the capability contract."],
        )

    if _is_forbidden_resource(resource, contract):
        return CapabilityCheckResult(
            decision="deny",
            risk_score=100,
            reason=[
                f"Resource {resource} matches forbidden resources in the capability contract."
            ],
        )

    matched_rule = _find_matching_rule(
        contract=contract,
        tool=tool,
        resource=resource,
        recipient=recipient,
    )

    if matched_rule is None:
        return CapabilityCheckResult(
            decision="deny",
            risk_score=80,
            reason=[
                "No capability rule in the contract matches this tool call.",
                f"tool={tool}",
                f"resource={resource}",
                f"recipient={recipient}",
            ],
        )

    total_risk = used_risk + matched_rule.risk_cost

    if total_risk > contract.risk_budget:
        return CapabilityCheckResult(
            decision="deny",
            risk_score=total_risk,
            reason=[
                f"Risk budget exceeded: used_risk={used_risk}, "
                f"current_cost={matched_rule.risk_cost}, "
                f"budget={contract.risk_budget}."
            ],
        )

    input_label_set = set(input_labels)

    if matched_rule.mode == EXTERNAL_WRITE_MODE:
        if input_label_set & SENSITIVE_LABELS:
            return CapabilityCheckResult(
                decision="deny",
                risk_score=100,
                reason=[
                    "Sensitive or secret data is not allowed to flow into external_write tools.",
                    f"input_labels={input_labels}",
                ],
            )

        if input_label_set & TAINTED_LABELS:
            return CapabilityCheckResult(
                decision="confirm",
                risk_score=max(60, matched_rule.risk_cost),
                reason=[
                    "Tainted or unknown data is flowing into an external_write tool.",
                    "Human confirmation is required before continuing.",
                    f"input_labels={input_labels}",
                ],
            )

    if matched_rule.allowed_input_labels:
        disallowed_labels = [
            label for label in input_labels
            if label not in matched_rule.allowed_input_labels
        ]

        if disallowed_labels:
            return CapabilityCheckResult(
                decision="deny",
                risk_score=80,
                reason=[
                    "Input labels are not allowed by the matched capability rule.",
                    f"allowed_input_labels={matched_rule.allowed_input_labels}",
                    f"disallowed_labels={disallowed_labels}",
                ],
            )

    if matched_rule.require_approval:
        return CapabilityCheckResult(
            decision="confirm",
            risk_score=matched_rule.risk_cost,
            reason=[
                "Matched capability rule requires human approval.",
                f"tool={tool}",
            ],
        )

    reasons.append("Tool call is allowed by the capability contract.")
    reasons.append(f"Matched tool={matched_rule.tool}, mode={matched_rule.mode}.")

    return CapabilityCheckResult(
        decision="allow",
        risk_score=matched_rule.risk_cost,
        reason=reasons,
    )