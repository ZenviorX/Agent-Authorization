# Agent-Authorization / AgentGuard

面向 AI Agent 工具调用场景的安全授权网关原型。

本项目围绕一个核心问题展开：当 AI Agent 能够调用文件、Shell、数据库、邮件等工具时，如何在工具真正执行之前进行统一的授权检查、风险评估、语义检测、人工确认和审计记录。

项目展示名为 **AgentGuard**。核心思想是：

```text
用户请求
  ↓
FakeAgent / Agent 生成工具调用计划
  ↓
PlanGuard 检查计划质量
  ↓
Gateway 执行硬策略、语义检测、风险评分、能力约束
  ↓
allow / confirm / deny
  ↓
Tool Executor 沙箱执行或拒绝执行
  ↓
Audit Logger 记录审计日志
```

---

## 1. 项目目标

传统应用中的权限控制通常围绕用户和接口展开，而 AI Agent 场景下还会出现新的风险：

- Agent 可能被 Prompt Injection 诱导绕过规则；
- Agent 可能读取敏感文件并外发；
- Agent 可能误