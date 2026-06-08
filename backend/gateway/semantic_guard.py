from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import yaml

_TRUE_VALUES = {"1", "true", "yes", "on", "enable", "enabled"}
_FALSE_VALUES = {"0", "false", "no", "off", "disable", "disabled"}


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_semantic_config() -> Dict[str, Any]:
    """
    读取 config/semantic_guard.yaml。
    文件不存在、格式错误或未启用时，语义检测自动关闭。
    """
    config_path = _project_root() / "config" / "semantic_guard.yaml"

    if not config_path.exists():
        return {"enabled": False, "fail_closed": False}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    except Exception:
        return {"enabled": False, "fail_closed": False}

    if not isinstance(config, dict):
        return {"enabled": False, "fail_closed": False}

    return config


def _env_enabled(default: bool) -> bool:
    """
    环境变量 SEMANTIC_GUARD_ENABLED 优先于配置文件。
    """
    value = os.getenv("SEMANTIC_GUARD_ENABLED")
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


@lru_cache(maxsize=1)
def get_embedding_model():
    """
    懒加载 embedding 模型。
    放在函数里 import，避免未启用语义检测时强依赖 sentence-transformers。
    """
    config = load_semantic_config()
    model_name = (config.get("model", {}) or {}).get(
        "name", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )

    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _as_vector_list(vector: Any) -> List[float]:
    if hasattr(vector, "tolist"):
        vector = vector.tolist()
    return [float(item) for item in vector]


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return float(dot / (norm_a * norm_b))


def _build_semantic_text(
    *,
    user: str,
    role: str,
    tool: str,
    params: Dict[str, Any],
    path: str = "",
    content: str = "",
    command: str = "",
    sql: str = "",
) -> str:
    """
    将一次工具调用整理成用于 embedding 的语义文本。
    """
    return "\n".join(
        [
            f"用户: {user}",
            f"角色: {role}",
            f"工具: {tool}",
            f"参数: {params}",
            f"路径: {path}",
            f"内容: {content}",
            f"命令: {command}",
            f"SQL: {sql}",
        ]
    )


def _collect_examples(config: Dict[str, Any]) -> List[Tuple[str, str]]:
    labels = config.get("labels", {})
    result: List[Tuple[str, str]] = []

    if not isinstance(labels, dict):
        return result

    for label_name, label_config in labels.items():
        if not isinstance(label_config, dict):
            continue

        examples = label_config.get("examples", [])
        if not isinstance(examples, list):
            continue

        for example in examples:
            result.append((str(label_name), str(example)))

    return result


@lru_cache(maxsize=1)
def _get_example_embeddings() -> Tuple[List[str], List[str], List[List[float]]]:
    config = load_semantic_config()
    examples = _collect_examples(config)

    if not examples:
        return [], [], []

    labels = [item[0] for item in examples]
    texts = [item[1] for item in examples]

    model = get_embedding_model()
    raw_embeddings = model.encode(texts, normalize_embeddings=True)
    embeddings = [_as_vector_list(item) for item in raw_embeddings]

    return labels, texts, embeddings


def _disabled_result(reason: str | None = None) -> Dict[str, Any]:
    return {
        "enabled": False,
        "risk_score": 0,
        "force_confirm": False,
        "hard_deny": False,
        "labels": [],
        "matches": [],
        "reasons": [reason] if reason else [],
    }


def semantic_check_tool_call(
    *,
    user: str,
    role: str,
    tool: str,
    params: Dict[str, Any],
    path: str = "",
    content: str = "",
    command: str = "",
    sql: str = "",
) -> Dict[str, Any]:
    """
    Embedding 语义风险检测。

    原则：
    1. 语义检测只增加风险，不降低原有规则风险。
    2. 默认 fail-open：模型不可用时不阻断项目运行。
    3. 若配置 fail_closed=true，模型不可用时转人工确认。
    """
    config = load_semantic_config()
    config_enabled = bool(config.get("enabled", False))
    enabled = _env_enabled(config_enabled)

    if not enabled:
        return _disabled_result()

    fail_closed = bool(config.get("fail_closed", False))

    try:
        labels, texts, example_embeddings = _get_example_embeddings()

        if not example_embeddings:
            return _disabled_result("语义样例为空，跳过语义检测。")

        semantic_text = _build_semantic_text(
            user=user,
            role=role,
            tool=tool,
            params=params,
            path=path,
            content=content,
            command=command,
            sql=sql,
        )

        model = get_embedding_model()
        query_embedding = _as_vector_list(
            model.encode([semantic_text], normalize_embeddings=True)[0]
        )

    except Exception as exc:
        if fail_closed:
            return {
                "enabled": True,
                "risk_score": 35,
                "force_confirm": True,
                "hard_deny": False,
                "labels": ["semantic_guard_error"],
                "matches": [],
                "reasons": [f"语义检测模块不可用，按 fail_closed 转人工确认：{exc}"],
            }
        return _disabled_result(f"语义检测模块不可用，已跳过：{exc}")

    thresholds = config.get("thresholds", {}) or {}
    global_confirm_score = float(thresholds.get("global_confirm_score", 0.62))
    global_deny_score = float(thresholds.get("global_deny_score", 0.78))
    max_total_semantic_risk = int(thresholds.get("max_total_semantic_risk", 120))

    label_configs = config.get("labels", {}) or {}
    best_by_label: Dict[str, Dict[str, Any]] = {}

    for label, example_text, example_embedding in zip(labels, texts, example_embeddings):
        similarity = _cosine_similarity(query_embedding, example_embedding)

        current_best = best_by_label.get(label)
        if current_best is None or similarity > current_best["score"]:
            best_by_label[label] = {
                "label": label,
                "example": example_text,
                "score": similarity,
            }

    matched_labels: List[str] = []
    matches: List[Dict[str, Any]] = []
    reasons: List[str] = []
    total_risk = 0
    force_confirm = False
    hard_deny = False

    for label, match in best_by_label.items():
        if label == "benign":
            continue

        label_config = label_configs.get(label, {}) or {}
        confirm_score = float(label_config.get("confirm_score", global_confirm_score))
        deny_score = float(label_config.get("deny_score", global_deny_score))
        label_risk = int(label_config.get("risk_score", 0))
        label_hard_deny = bool(label_config.get("hard_deny", False))

        score = float(match["score"])
        if score < confirm_score:
            continue

        matched_labels.append(label)
        matches.append(
            {
                "label": label,
                "score": round(score, 4),
                "matched_example": match["example"],
            }
        )
        total_risk += label_risk
        force_confirm = True
        reasons.append(
            f"语义相似度命中 {label}：{score:.2f}，相似样例：{match['example']}"
        )

        if score >= deny_score and label_hard_deny:
            hard_deny = True
            reasons.append(
                f"语义风险 {label} 超过拒绝阈值 {deny_score:.2f}，触发拒绝建议。"
            )

    total_risk = min(total_risk, max_total_semantic_risk)

    return {
        "enabled": True,
        "risk_score": total_risk,
        "force_confirm": force_confirm,
        "hard_deny": hard_deny,
        "labels": matched_labels,
        "matches": matches,
        "reasons": reasons,
    }


def clear_semantic_cache() -> None:
    """
    测试或热更新配置时使用。
    """
    load_semantic_config.cache_clear()
    get_embedding_model.cache_clear()
    _get_example_embeddings.cache_clear()
