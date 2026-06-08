# Codex Task: Gateway 模块化第一步（低风险重构）

## 背景

当前项目 `backend/gateway/gateway.py` 已经承担了太多职责：

- 构造 Gateway 返回结果；
- 构造 explanations；
- 判断 path bypass 关键词；
- 判断 destructive SQL 关键词；
- 执行 `check_tool_call()` 主流程。

本次重构目标不是改业务逻辑，而是把纯辅助函数拆到独立模块，让 `gateway.py` 更像主流程编排文件，降低多人协作冲突。

## 本次包内新增文件

请把以下文件复制到项目对应路径：

```text
files/backend/gateway/result_builder.py      -> backend/gateway/result_builder.py
files/backend/gateway/security_detectors.py  -> backend/gateway/security_detectors.py
files/tests/unit/test_gateway_module_helpers.py -> tests/unit/test_gateway_module_helpers.py
```

## 需要修改的文件

只修改：

```text
backend/gateway/gateway.py
```

不要修改：

```text
config/policy.yaml
config/semantic_guard.yaml
backend/gateway/semantic_guard.py
security_cases/*
README.md
```

## 具体修改步骤

### 1. 修改 imports

当前顶部类似：

```python
from backend.schemas import ToolCallRequest, GatewayResponse
...
from backend.gateway.semantic_guard import semantic_check_tool_call
```

改成：

```python
from backend.schemas import ToolCallRequest
...
from backend.gateway.semantic_guard import semantic_check_tool_call
from backend.gateway.result_builder import build_gateway_result
from backend.gateway.security_detectors import (
    is_destructive_sql_keyword as _is_destructive_sql_keyword,
    is_path_bypass_keyword as _is_path_bypass_keyword,
)
```

说明：

- `GatewayResponse` 当前没有被使用，删除即可；
- 使用 alias 是为了让 `check_tool_call()` 里原有 `_is_path_bypass_keyword(...)` 和 `_is_destructive_sql_keyword(...)` 调用不需要改。

### 2. 从 `gateway.py` 删除这些本地函数定义

删除整段函数：

```python
def get_risk_level(...):
    ...

def build_explanations(...):
    ...

def _default_semantic_guard_result(...):
    ...

def build_gateway_result(...):
    ...

def _is_path_bypass_keyword(...):
    ...

def _is_destructive_sql_keyword(...):
    ...
```

这些函数已经分别迁移到：

```text
backend/gateway/result_builder.py
backend/gateway/security_detectors.py
```

### 3. 保留 `TOOL_REASON_MAP`

不要移动 `TOOL_REASON_MAP`，因为它仍然只服务当前 `check_tool_call()` 中的工具基础风险说明。

### 4. 不改 `check_tool_call()` 业务逻辑

除非 import 名称需要适配，否则不要改变以下行为：

- 未知工具 deny；
- 低置信度 deny/confirm；
- semantic_guard 风险叠加；
- task/capability contract；
- resource_risk；
- dangerous_keywords.path/sensitive_path；
- destructive SQL hard deny；
- 最终 allow/confirm/deny 合并；
- `semantic_guard` 结构化返回。

## 验证命令

修改后运行：

```powershell
python -m py_compile .\backend\gateway\gateway.py
python -m py_compile .\backend\gateway\result_builder.py
python -m py_compile .\backend\gateway\security_detectors.py

pytest .\tests\unit\test_gateway_module_helpers.py
pytest .\tests\unit\test_gateway_semantic_guard.py .\tests\unit\test_gateway_path_keywords.py .\tests\unit\test_gateway_sql_hard_deny.py
pytest
```

## 预期结果

- 所有测试通过；
- `backend/gateway/gateway.py` 行数减少；
- `gateway.py` 中不再定义 response builder 和 detector helpers；
- Gateway 响应字段保持不变；
- `semantic_guard` 字段仍然存在；
- SQL hard deny、path keyword hard deny 仍然有效。

## 提交建议

```powershell
git add backend/gateway/gateway.py backend/gateway/result_builder.py backend/gateway/security_detectors.py tests/unit/test_gateway_module_helpers.py
git commit -m "Refactor gateway helper functions into modules"
```
