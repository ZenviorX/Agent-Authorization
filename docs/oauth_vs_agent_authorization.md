# OAuth 与 Agent Authorization 的关系说明

## 1. 为什么老师会提到 OAuth

OAuth 2.0 是目前常见的第三方应用授权框架。它解决的是：

> 某个应用能不能代表用户访问某个资源？

例如一个应用想读取用户邮箱、日历或云盘，就需要 access token 和对应的 scope。

但是 AI Agent 场景更复杂。Agent 不只是访问 API，还可能调用文件、Shell、数据库、邮件发送等工具。因此只靠 OAuth scope 还不够。

---

## 2. OAuth 控制什么

OAuth 主要控制：

- 调用者是谁；
- 代表哪个用户；
- 有哪些 scope；
- 能访问哪个资源服务器；
- token 是否有效。

例如：

```text
scope = tool:file:read tool:email:send
这表示调用者可以读取文件，也可以发送邮件。

3. 本项目控制什么

本项目 AgentGuard 控制的是：

Agent 是否允许调用某个工具；
工具参数是否安全；
是否越过当前任务边界；
是否访问敏感路径；
是否执行破坏性命令；
是否把污染数据发送到外部；
是否需要人工确认；
是否留下审计证据。

因此，本项目不是替代 OAuth，而是把 OAuth 的权限思想扩展到 AI Agent 工具调用场景。

4. 二者关系
对比项OAuthAgentGuard
控制对象API 访问Agent 工具调用
核心凭证access tokentask contract + gateway decision
权限表达scopecapability / tool / resource / risk
请求粒度单次 API 请求多步任务链
风险类型越权访问资源越权、数据泄露、命令执行、提示注入、多步攻击
执行前拦截Resource ServerTool Proxy + Gateway + Runtime Monitor
5. 本项目新增设计

本项目新增 OAuth-style Agent Authorization Profile。

流程如下：

External Agent
    |
    | tool + params + OAuth-style scopes
    v
Tool Proxy
    |
    | scope check
    v
Capability Contract
    |
    | task boundary check
    v
Runtime Monitor
    |
    | data-flow / sink / path / risk check
    v
allow / confirm / deny

这说明本项目可以接入 OpenClaw、WorkBuddy 或其他 Agent 平台。

这些外部 Agent 不需要直接接触本地文件系统，而是必须通过 Tool Proxy 提交工具调用请求。

6. 对 OpenClaw / WorkBuddy 的封装思路

如果要封装 OpenClaw、WorkBuddy 或其他 Agent：

不直接让它们调用本地工具；
给它们提供统一 Tool Proxy API；
要求每次工具调用都带上：
agent_platform；
original_task；
tool；
params；
requested_scopes；
sandbox_profile；
Tool Proxy 先做 OAuth-style scope 检查；
再进入 Capability Contract；
最后进入 Runtime Monitor；
只有 allow 才进入沙箱执行。

这样可以把外部 Agent 封装到安全沙箱中。

7. 项目表达方式

可以在展示中这样讲：

OAuth 解决“谁可以访问资源”的问题，而我们的系统进一步解决“AI Agent 在当前任务中能不能安全调用工具”的问题。
我们将 OAuth 的 scope 思想接入 Tool Proxy，但不止步于 scope，而是继续检查任务边界、工具副作用、路径风险、数据流污染和人工确认，因此更适合 AI Agent 的真实安全需求。
