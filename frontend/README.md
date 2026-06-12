# AgentGuard 前端页面说明

当前前端采用多 HTML 页面结构，顶部统一导航栏贯穿所有正式页面。

| 路由 | 文件 | 覆盖功能 |
|---|---|---|
| `/showcase` | `showcase.html` | 系统总览、系统报告、状态聚合 |
| `/` | `index.html` | FakeAgent 单步任务、Gateway 直连、语义检测、人工审批、审计日志 |
| `/tool-proxy` | `tool_proxy.html` | 外部工具调用授权检查 |
| `/task-chain` | `task_chain.html` | Runtime Monitor、Task Contract、Capability Contract、真实 Agent Runtime |
| `/attack-chain-runtime` | `attack_chain_runtime.html` | 攻击链会话检测、effective_decision |
| `/sandbox-dashboard` | `sandbox_dashboard.html` | 沙箱文件、邮件 outbox、数据库、普通证据包 |
| `/authorized-evidence` | `authorized_evidence.html` | 授权证据包生成、列表、读取与哈希校验 |
| `/benchmark-dashboard` | `benchmark_dashboard.html` | 评测报告、完整性校验、效果分析、安全图谱 |
| `/security-dashboard` | `security_dashboard.html` | 安全能力矩阵、审计哈希链、安全中心 |

`runtime_demo.html` 是旧版运行态页面，不在正式导航中。
