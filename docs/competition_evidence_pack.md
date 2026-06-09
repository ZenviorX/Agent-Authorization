# Competition Evidence Pack

本模块用于将最新的离线 Runtime Benchmark 报告升级为“竞赛证据包”。

## 运行命令

```powershell
python experiments\run_llm_runtime_benchmark.py
python experiments\generate_competition_evidence_pack.py
或直接运行：

.\scripts\run_competition_evidence.ps1
输出文件

默认读取最新的：

Results/Result_XXX.json

并生成：

Results/EvidencePack_XXX.json
Results/EvidencePack_XXX.md
证据包内容

证据包包括：

Benchmark 总体指标；
SHA-256 完整性校验结果；
防护覆盖矩阵；
AgentGuard 与 naive baseline 对比；
代表性攻击样例；
高风险数据流证据；
可复现命令；
答辩展示建议。
答辩价值

证据包用于回答评审常见问题：

你的系统覆盖了哪些攻击面？
你的防护链路是否完整？
没有你的系统会发生什么？
你的报告是否可以验真？
能否复现实验结果？
能否解释为什么阻断某个工具调用？

它将后端测试、Benchmark 报告、完整性哈希、数据流图谱和量化有效性指标整合为一个可提交、可展示、可复查的材料。
