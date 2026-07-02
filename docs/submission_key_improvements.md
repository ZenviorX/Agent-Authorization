# 提交前关键改进说明

## 1. 改进目标

本轮改进不再继续堆叠边缘功能，而是围绕线下评审最关注的三个问题进行增强：

1. 项目是否真的能接入真实 AI Agent，而不是只停留在 FakeAgent 演示；
2. AgentGuard 相比 NoGuard、OAuth-only、Keyword-only 是否有清晰优势；
3. 作品报告中是否能形成“威胁模型—安全机制—实验验证”的完整闭环。

## 2. 新增真实 LLM Tool Calling 适配入口

新增模块：

- `backend/real_agent/tool_call_adapter.py`
- `backend/routes/llm_tool_call_routes.py`

新增接口：

```text
POST /real-agent/tool-call/run
该接口支持 OpenAI / DeepSeek / OpenAI-compatible 模型的 tool-calling 输出格式。例如：

{
  "user": "user",
  "original_task": "请读取 public/notice.txt 并总结",
  "execute": true,
  "llm_tool_call": {
    "tool_calls": [
      {
        "type": "function",
        "function": {
          "name": "file.read",
          "arguments": "{\"path\":\"public/notice.txt\"}"
        }
      }
    ]
  }
}

执行链路为：

Real LLM tool_call
  -> OpenAI-compatible adapter
  -> Tool Proxy prepare
  -> Capability Token
  -> execute=true
  -> Hybrid Sandbox
  -> Audit / Evidence

这可以用于回答评委问题：

你们保护的是真实 Agent，还是自己模拟的 Agent？

回答要点：

项目既保留 FakeAgent 作为稳定演示入口，也新增了 OpenAI-compatible tool-call adapter。真实大模型只负责生成工具调用计划，AgentGuard 负责统一授权、Token 绑定、沙箱执行和审计证据。

3. 新增四组对比实验

新增脚本：

scripts/run_submission_key_eval.py

运行方式：

python scripts\run_submission_key_eval.py

输出文件：

docs/evaluation/submission_key_eval_summary.json
docs/evaluation/submission_key_eval_cases.csv
docs/evaluation/submission_key_eval_report.md

对比方法：

方法含义
NoGuard不做任何检查，所有工具调用直接放行
OAuth-only只检查工具调用声明的 scope 是否满足要求
Keyword-only只检查参数中是否包含危险关键词
AgentGuard使用完整网关策略进行综合判断

建议写入报告的位置：

“系统测试与实验分析”
“与现有方案对比”
“安全性验证”
4. 报告中的创新点建议

建议将创新点写成：

面向 AI Agent 工具调用的两阶段授权机制；
与用户、任务、工具、参数和沙箱绑定的 Capability Token；
Gateway + Runtime Monitor + Sandbox 的组合式安全执行链；
面向数据外发、路径穿越、危险命令和提示注入的统一风险评估；
可解释、可审计的运行证据链。
5. 提交前推荐演示顺序
正常读取公开文件：展示 allow；
读取 secret 文件：展示 deny；
外部邮箱发送敏感内容：展示 confirm / deny；
真实 LLM tool_call 进入 /real-agent/tool-call/run；
展示 Capability Token 签发与执行阶段消耗；
展示 Sandbox evidence；
展示四组对比实验报告。
6. 评委追问时的回答
问：为什么 OAuth 不够？

OAuth 只能说明 Agent 声明了某些权限，但不能判断当前任务是否允许这个调用、参数是否被篡改、输出是否外发、调用链是否形成攻击链。AgentGuard 在 OAuth scope 之外增加了任务边界、Capability Token、运行时监控、沙箱和审计证据。

问：为什么不直接相信 LLM？

LLM 只负责生成工具调用计划，不能自己决定是否执行。所有工具调用都必须经过 AgentGuard 授权层，这样可以避免提示注入、越权调用和敏感数据外发。

问：Native Sandbox 是不是不如 Docker？

是。项目明确区分 Docker Sandbox 和 Native Subprocess Sandbox。Docker 提供更强隔离；Native 是为了比赛现场和无 Docker 环境下的稳定 fallback，不把它夸大成容器级隔离。
