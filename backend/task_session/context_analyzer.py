from typing import Dict, List

from backend.gateway.policy_loader import (
    get_dangerous_keywords,
    get_external_output_tools,
)


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

    sensitive_keywords = get_dangerous_keywords("sensitive_content")
    prompt_injection_keywords = get_dangerous_keywords("prompt_injection")

    for keyword in sensitive_keywords:
        if keyword.lower() in lower_text:
            result["sensitive"] = True
            reasons.append(f"工具输出内容命中敏感关键词：{keyword}")

    for keyword in prompt_injection_keywords:
        if keyword.lower() in lower_text:
            result["tainted"] = True
            reasons.append(f"工具输出内容疑似包含提示注入关键词：{keyword}")

    result["reasons"] = reasons
    return result


def is_external_output_tool(tool: str) -> bool:
    """
    判断某个工具是否可能造成数据外发。
    """
    return tool in get_external_output_tools()


def is_sensitive_path(path: str) -> bool:
    """
    判断路径是否疑似敏感路径。
    """
    if not path:
        return False

    lower_path = path.lower()
    sensitive_path_keywords = get_dangerous_keywords("sensitive_path")

    return any(keyword in lower_path for keyword in sensitive_path_keywords)
