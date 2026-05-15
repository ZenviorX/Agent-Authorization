# Task9 Agent、Gateway、ToolExecutor 三层架构硬拆分总结

## 一、本次调整目标

Task9 的目标是把项目从“功能已经拆开，但文件仍然平铺在 backend 根目录”的状态，进一步整理成清晰的三层解耦架构：

```text
用户自然语言
   ↓
Agent 层：FakeAgent / LLMAgent
   ↓ 只输出结构化 tool_call，不执行
Gateway 层：鉴权、风险评分、人工确认、审计
   ↓ allow 或人工 confirm 后才继续
ToolExecutor 层：真正执行工具
```

本次重构重点强调：

```text
FakeAgent 不是 LLMAgent 的低配版
LLMAgent 不是 Gateway 的一部分
Gateway 不关心请求是谁生成的
ToolExecutor 不允许被 Agent 直接绕过调用
```

一句话总结：

> 本系统不信任任何 Agent。无论工具调用来自 FakeAgent、真实 LLM，还是外部系统，都必须先转换为统一结构，再经过 Gateway 授权。

---

## 二、最终目录结构

重构后，`backend/` 根目录只保留入口文件和公共结构：

```text
backend/
├── main.py
├── schemas.py
├── utils.py
├── __init__.py
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py
│   ├── agent_factory.py
│   ├── fake_agent.py
│   └── llm_agent.py
│
├── gateway/
│   ├── __init__.py
│   ├── gateway.py
│   ├── gateway_service.py
│   └── policy_loader.py
│
├── tools/
│   ├── __init__.py
│   └── tool_executor.py
│
├── audit/
│   ├── __init__.py
│   └── audit_logger.py
│
└── approval/
    ├── __init__.py
    └── approval_store.py
```

已经删除 backend 根目录下的旧平铺文件：

```text
backend/fake_agent.py
backend/llm_agent.py
backend/gateway.py
backend/gateway_service.py
backend/tool_executor.py
backend/audit_logger.py
backend/approval_store.py
backend/policy_loader.py
backend/gateway.py.bak
```

这些文件不再保留兼容转发层，避免目录看起来混乱。

---

## 三、Agent 层改造

### 1. 新增 BaseAgent

新增文件：

```text
backend/agents/base_agent.py
```

核心代码：

```python
from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseAgent(ABC):
    """
    Agent interface.

    Agents may only turn natural-language input into a structured tool-call
    plan. They must not execute tools or make authorization decisions.
    """

    @abstractmethod
    def plan(self, user_input: str) -> Dict[str, Any]:
        pass
```

这让所有 Agent 的职责都被限制为：

```text
自然语言 → 结构化工具调用计划
```

不能执行工具，也不能做最终安全决策。

### 2. FakeAgent 和 LLMAgent 继承 BaseAgent

`FakeAgent` 现在位于：

```text
backend/agents/fake_agent.py
```

类定义改为：

```python
class FakeAgent(BaseAgent):
```

`LLMAgent` 现在位于：

```text
backend/agents/llm_agent.py
```

类定义改为：

```python
class LLMAgent(BaseAgent):
```

二者是同级替换关系：

```text
FakeAgent：规则模拟器，适合演示、测试、答辩稳定复现
LLMAgent：真实大模型规划器，适合真实模型接入
```

它们都只返回统一结构：

```json
{
  "agent": "FakeAgent 或 LLMAgent",
  "status": "planned",
  "original_input": "用户自然语言",
  "tool_call": {
    "tool_name": "file.read",
    "description": "读取文件内容",
    "arguments": {
      "file_path": "public/notice.txt"
    },
    "need_auth": true
  }
}
```

### 3. 新增 agent_factory

新增文件：

```text
backend/agents/agent_factory.py
```

作用是根据参数选择 Agent：

```python
def get_agent(agent_type: str = "fake") -> BaseAgent:
    normalized_type = (agent_type or "fake").strip().lower()

    if normalized_type in {"fake", "fake_agent", "fakeagent"}:
        return FakeAgent()

    if normalized_type in {"llm", "llm_agent", "llmagent"}:
        return LLMAgent()

    raise ValueError(f"Unsupported agent_type: {agent_type}")
```

这样主流程不再写死：

```python
fake_agent = FakeAgent()
llm_agent = LLMAgent()
```

而是统一使用：

```python
agent = get_agent(agent_type)
```

---

## 四、Gateway 层改造

Gateway 相关代码移动到：

```text
backend/gateway/
```

其中：

```text
gateway.py          风险判断核心
gateway_service.py  统一调用流程编排
policy_loader.py    策略加载
```

`gateway_service.py` 现在只依赖：

```python
from backend.schemas import ToolCallRequest
from backend.gateway.gateway import check_tool_call
from backend.tools.tool_executor import execute_tool
from backend.audit.audit_logger import write_log
from backend.utils import normalize_tool_name, normalize_params
from backend.approval.approval_store import create_pending_request
```

这里没有导入：

```text
FakeAgent
LLMAgent
```

这说明 Gateway 已经不关心请求来自哪个 Agent，只接收统一的 `ToolCallRequest`。

---

## 五、ToolExecutor、Audit、Approval 独立

### 1. ToolExecutor

移动到：

```text
backend/tools/tool_executor.py
```

作用：

```text
只执行已经被 Gateway allow 或人工 confirm 的工具调用
```

### 2. AuditLogger

移动到：

```text
backend/audit/audit_logger.py
```

作用：

```text
记录工具调用、网关决策、是否执行、pending_id、执行结果
```

### 3. ApprovalStore

移动到：

```text
backend/approval/approval_store.py
```

作用：

```text
保存需要人工确认的工具调用请求
```

---

## 六、main.py 主流程调整

`main.py` 现在只负责 API 路由和流程拼接，不再直接持有固定的 `fake_agent` 或 `llm_agent` 实例。

新增辅助函数：

```python
def plan_with_agent(request: AgentTextRequest, agent_type: str):
    try:
        agent = get_agent(agent_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return agent.plan(request.user_input)
```

新增计划结果转换函数：

```python
def build_tool_request_from_plan(
    request: AgentTextRequest,
    plan_result: dict,
) -> ToolCallRequest | None:
    tool_call = plan_result.get("tool_call")

    if plan_result.get("status") != "planned" or not tool_call:
        return None

    tool_name = tool_call.get("tool_name")
    if not tool_name:
        return None

    return ToolCallRequest(
        user=request.user,
        tool=tool_name,
        params=tool_call.get("arguments", {}),
    )
```

这一步非常关键：

```text
Agent 输出的 tool_call
   ↓
统一转换为 ToolCallRequest
   ↓
交给 Gateway Service
```

也就是说，Agent 永远不能直接执行工具。

---

## 七、保留和新增的接口

### 1. 通用 Agent 规划接口

```text
POST /agent/plan?agent_type=fake
POST /agent/plan?agent_type=llm
```

作用：

```text
只查看 Agent 生成的工具调用计划，不进入 Gateway，不执行工具。
```

### 2. 通用 Agent 完整演示接口

```text
POST /agent/simulate?agent_type=fake
POST /agent/simulate?agent_type=llm
```

流程：

```text
自然语言
  → FakeAgent 或 LLMAgent 生成 tool_call
  → 转换为 ToolCallRequest
  → Gateway 检查
  → allow / confirm / deny
  → 执行 / pending / 拦截
```

### 3. FakeAgent 旧演示接口保留

```text
POST /demo/fake-agent/plan
POST /demo/fake-agent/simulate
```

作用：

```text
用于答辩稳定演示和离线测试。
```

### 4. LLM 单独规划接口保留

```text
POST /llm/plan
```

作用：

```text
只查看真实大模型生成的工具调用计划。
```

### 5. Gateway 正式入口保留

```text
POST /gateway/check
POST /gateway/call
```

其中：

```text
/gateway/check 只测试网关判断，不执行工具
/gateway/call  是正式结构化工具调用入口
```

---

## 八、旧路径清理

本次不仅移动了文件，还全仓库检查并替换了旧导入路径。

旧路径示例：

```python
from backend.fake_agent import FakeAgent
from backend.llm_agent import LLMAgent
from backend.gateway_service import handle_tool_request
from backend.tool_executor import execute_tool
from backend.audit_logger import write_log
from backend.approval_store import create_pending_request
from backend.policy_loader import get_tool_risk
```

已经统一改为新路径：

```python
from backend.agents.fake_agent import FakeAgent
from backend.agents.llm_agent import LLMAgent
from backend.gateway.gateway_service import handle_tool_request
from backend.tools.tool_executor import execute_tool
from backend.audit.audit_logger import write_log
from backend.approval.approval_store import create_pending_request
from backend.gateway.policy_loader import get_tool_risk
```

同时，`Task/*.md` 文档中的示例导入也已经同步更新。

---

## 九、路径修复

因为文件从 backend 根目录移动到了子目录，所以部分基于 `__file__` 推导项目根目录的代码需要修正。

已修复：

```text
backend/tools/tool_executor.py
backend/audit/audit_logger.py
backend/gateway/policy_loader.py
```

现在使用：

```python
Path(__file__).resolve().parents[2]
```

确保仍然正确访问项目根目录下的：

```text
data/
logs/
config/policy.yaml
```

---

## 十、验证结果

### 1. 旧路径引用检查

已检查全仓库，以下旧路径不再出现：

```text
backend.fake_agent
backend.llm_agent
backend.gateway_service
backend.tool_executor
backend.audit_logger
backend.approval_store
backend.policy_loader
```

### 2. 单元测试

执行：

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_gateway
```

结果：

```text
Ran 5 tests in 0.004s

OK
```

### 3. Python 文件语法解析

执行 AST 解析检查：

```text
parsed 19 python files
```

说明当前 backend 目录下 Python 文件语法正常。

### 4. 主流程手动验证

验证内容：

```text
agent_plan(fake)
agent_simulate(fake)
llm_plan
```

结果：

```text
FakeAgent
gateway allow True
LLMAgent
```

说明：

```text
FakeAgent 可以正常规划
Agent 模拟流程可以进入 Gateway 并执行 allow 工具
LLMAgent 可以正常被加载并返回规划结果或配置错误结果
```

---

## 十一、当前架构价值

Task9 完成后，项目边界更加清晰：

```text
Agent 层可替换
Gateway 层不可绕过
ToolExecutor 层不直接暴露给 Agent
AuditLogger 全程记录
ApprovalStore 只处理人工确认队列
```

这使系统从：

```text
FakeAgent 驱动的演示原型
```

升级为：

```text
可接入任意 Agent 的工具调用授权网关原型
```

这也是答辩时最重要的安全亮点：

> 即使接入真实大模型，系统也不会直接信任大模型输出。LLM 输出只是候选工具调用，Gateway 才是安全决策点。

---

## 十二、后续可继续优化方向

1. 前端增加 Agent 类型选择：

```text
[ FakeAgent 规则模拟 ] [ LLM 真实大模型 ]
```

2. 在前端展示四段式结果：

```text
Agent 规划结果
Gateway 风险判断
执行或 pending 状态
审计日志记录
```

3. 增加针对 `/agent/simulate?agent_type=llm` 的接口测试。

4. 将 Task9 的架构图整理进 README 或最终报告。

5. 后续如果接入多个模型，可以继续扩展 `agent_factory.py`：

```text
fake
llm
deepseek
openai
local
```

但无论接入多少 Agent，都必须保持核心原则：

```text
Agent 只负责 plan
Gateway 负责 check
ToolExecutor 负责 execute
AuditLogger 负责 record
```
