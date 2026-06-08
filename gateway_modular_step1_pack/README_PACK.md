# Gateway Modular Step 1 Pack

这个包用于把 `backend/gateway/gateway.py` 中的纯辅助函数拆分到独立模块，降低主文件复杂度。

## 包内容

```text
files/backend/gateway/result_builder.py
files/backend/gateway/security_detectors.py
files/tests/unit/test_gateway_module_helpers.py
CODEX_PROMPT.md
```

## 目标

不改业务逻辑，只拆辅助函数：

- `result_builder.py`：负责 Gateway 响应构造、risk level、explanations、semantic_guard 默认结构；
- `security_detectors.py`：负责路径绕过关键词、破坏性 SQL 关键词判断；
- `gateway.py`：保留 `check_tool_call()` 主流程。

## 给 Codex 的任务

把 `CODEX_PROMPT.md` 的内容完整粘给 Codex，让它按步骤修改。
