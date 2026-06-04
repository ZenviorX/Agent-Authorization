from typing import Any, Dict, List


def allow_all_decider(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    无防护 Agent 基线：
    不做任何安全检查，所有工具调用直接放行。
    """
    return {
        "decision": "allow",
        "risk_score": 0,
        "risk_level": "none",
        "reason": ["baseline_allow_all"],
        "explanations": [
            {
                "factor": "baseline",
                "message": "无防护基线策略：所有请求直接放行。"
            }
        ],
    }


DANGEROUS_KEYWORDS = [
    "../",
    "..\\",
    "secret",
    "password",
    "token",
    "api_key",
    "secret_key",
    ".env",
    "private_key",
    "rm -rf",
    "del /s",
    "format",
    "shutdown",
    "reboot",
    "powershell",
    "curl",
    "wget",
    "ignore previous instructions",
    "bypass authorization",
    "忽略之前的规则",
    "绕过权限检查",
    "不要遵守安全策略",
    "drop table",
    "union select",
]


def _flatten_request_text(value: Any) -> str:
    """
    将请求中的嵌套字段拉平成字符串，方便关键词基线检测。
    """
    if value is None:
        return ""

    if isinstance(value, dict):
        return " ".join(_flatten_request_text(v) for v in value.values())

    if isinstance(value, list):
        return " ".join(_flatten_request_text(v) for v in value)

    return str(value)


def keyword_decider(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    简单关键词规则基线：
    只要命中危险关键词就拒绝，否则直接放行。
    """
    text = _flatten_request_text(request_data).lower()
    hit_keywords: List[str] = []

    for keyword in DANGEROUS_KEYWORDS:
        if keyword.lower() in text:
            hit_keywords.append(keyword)

    if hit_keywords:
        return {
            "decision": "deny",
            "risk_score": 80,
            "risk_level": "high",
            "reason": ["keyword_hit:" + ",".join(hit_keywords)],
            "explanations": [
                {
                    "factor": "keyword_baseline",
                    "message": "关键词规则基线命中危险关键词。"
                }
            ],
        }

    return {
        "decision": "allow",
        "risk_score": 0,
        "risk_level": "none",
        "reason": ["keyword_no_hit"],
        "explanations": [
            {
                "factor": "keyword_baseline",
                "message": "关键词规则基线未命中危险关键词，直接放行。"
            }
        ],
    }

