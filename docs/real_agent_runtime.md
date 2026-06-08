# 真实 Stepwise LLM Agent 运行时防护说明

## 1. 模块定位

本模块用于展示 AgentGuard 对真实大模型 Agent 工具调用过程的运行时安全防护能力。

与早期固定样例不同，真实 Stepwise LLM Agent 模式不是直接手写危险工具调用，而是让大模型根据用户自然语言任务和上一步工具输出继续规划下一步工具调用。系统不信任 Agent 的规划结果，每一步候选工具调用都必须经过 Capability Contract、Runtime Monitor、Attack Chain Detector 和 Sandbox Executor 的联合检查。

核心目标是证明：

```text
真实 LLM Agent 可以接入系统，
但真实工具执行权不交给 Agent，
每一步工具调用都必须经过任务级授权边界和运行时安全检查。