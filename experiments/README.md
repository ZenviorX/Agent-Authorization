# experiments

本目录用于存放 AgentGuard 的实验评测脚本与实验结果。

## 1. 当前实验：compare_methods.py

`compare_methods.py` 用于比较不同防护方法在同一批安全样例上的表现。

当前比较的方法包括：

| 方法 | 说明 |
|---|---|
| no_protection | 无防护基线，所有工具调用直接放行 |
| keyword_filter | 关键词过滤基线，命中危险关键词则拒绝 |
| single_gateway | 单步授权网关，只检查当前工具调用 |
| full_system | 完整系统，保留任务合约、数据标签、步骤和风险预算等上下文 |

## 2. 运行方式

在项目根目录执行：

```powershell
python experiments/compare_methods.py

运行后会在以下目录生成实验结果：

experiments/results/

输出包括：

compare_methods_*.json
compare_methods_*.md
3. 实验指标

当前脚本会统计：

总体一致率；
攻击阻断/确认率；
风险误放行率；
正常误拒率；
平均判断延迟；
allow / confirm / deny 决策分布。
4. 后续扩展方向

后续可以继续加入：

带 task_contract 的任务级授权样例；
带 input_labels 的数据流污染样例；
带 current_step / used_risk 的风险预算样例；
多步攻击链对比实验；
消融实验：去掉 Capability Contract、去掉 Attack Chain、去掉数据标签等。

该目录的目标是为信安赛作品报告提供可复现的实验数据。