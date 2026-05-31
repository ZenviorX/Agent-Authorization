from typing import Dict, List


SENSITIVE_KEYWORDS = [
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "密钥",
    "密码",
    "口令",
    "令牌",
]

PROMPT_INJECTION_KEYWORDS = [
    "忽略之前的规则",
    "忽略以上规则",
    "忽略所有规则",
    "忽略之前的指令",
    "不要遵守",
    "绕过",
    "请读取",
    "发送给 attacker",
    "attacker@example.com",
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "bypass",
]


def analyze_text_security(text: str) -> Dict[str, object]:
    """
    分析工具输出文本中是否包含敏感信息或提示注入内容。

    返回结果：
    {
        "sensitive": True/False,
        "tainted": True/False,
        "reasons": [...]
    }
    """
    result = {
        "sensitive": False,
        "tainted": False,
        "reasons": [],
    }

    if not text:
        return result

    lower_text = text.lower()
    reasons: List[str] = []

    for keyword in SENSITIVE_KEYWORDS:
        if keyword.lower() in lower_text:
            result["sensitive"] = True
            reasons.append(f"工具输出内容命中敏感关键词：{keyword}")

    for keyword in PROMPT_INJECTION_KEYWORDS:
        if keyword.lower() in lower_text:
            result["tainted"] = True
            reasons.append(f"工具输出内容疑似包含提示注入关键词：{keyword}")

    result["reasons"] = reasons
    return result


def is_external_output_tool(tool: str) -> bool:
    """
    判断某个工具是否可能造成数据外发。
    """
    return tool in {
        "email.send",
        "shell.run",
        "db.query",
        "file.write",
    }


def is_sensitive_path(path: str) -> bool:
    """
    判断路径是否疑似敏感路径。
    """
    if not path:
        return False

    lower_path = path.lower()

    sensitive_path_keywords = [
        "secret",
        "password",
        "passwd",
        "private",
        "key",
        ".env",
        "token",
    ]

    return any(keyword in lower_path for keyword in sensitive_path_keywords)