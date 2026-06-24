# 多策略对比评测报告

## 1. 实验目的

本实验在同一批安全样例上对比三种工具调用控制策略：

- `allow_all`：无前置安全控制，所有工具调用直接放行；
- `keyword_only`：仅依赖显式关键词和副作用工具进行判断；
- `gateway`：使用本项目完整 Gateway 进行工具、资源、角色、置信度和策略综合判断。

该实验用于评估完整 Gateway 相比基础策略在攻击阻断、风险升级和正常任务保留方面的差异。

## 2. 实验规模

- 样例总数：118
- 记录总数：354
- 总耗时：48.45 ms

## 3. 核心结果

| 策略 | 总样例 | 攻击样例 | 正常样例 | 攻击阻断/确认率 | 攻击误放行率 | 正常不误拒率 | 决策匹配率 |
|---|---:|---:|---:|---:|---:|---:|---:|
| allow_all | 118 | 95 | 23 | 0.00% | 100.00% | 100.00% | 17.80% |
| keyword_only | 118 | 95 | 23 | 91.58% | 8.42% | 95.65% | 90.68% |
| gateway | 118 | 95 | 23 | 100.00% | 0.00% | 100.00% | 100.00% |

## 4. 结果解释

`allow_all` 代表缺少前置安全边界的模式。它通常不会拒绝正常任务，但攻击样例也会被直接放行。

`keyword_only` 可以拦截包含明显危险词的请求，但缺少角色权限、资源风险、任务置信度和上下文约束，面对复杂工具调用时解释能力有限。

`gateway` 是本项目完整方案。它综合工具类型、资源路径、用户角色、Agent 置信度、任务合约和策略阈值，将工具调用分为 allow、confirm、deny 三类结果。

## 5. 输出文件

- CSV 明细：`C:/Users/24727/Documents/GitHub/Agent-Authorization/Results/strategy_comparison.csv`
- JSON 摘要：`C:/Users/24727/Documents/GitHub/Agent-Authorization/Results/strategy_comparison_summary.json`
- HTML 仪表盘：`C:/Users/24727/Documents/GitHub/Agent-Authorization/Results/strategy_comparison_dashboard.html`
