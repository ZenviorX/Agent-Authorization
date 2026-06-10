# AgentGuard / Agent-Authorization

面向 AI Agent 工具调用场景的安全授权网关、运行时监控与可审计证据系统。

AgentGuard 的目标不是替代 Agent，而是在 Agent 调用文件、命令、邮件、数据库等工具之前，提供一个外部安全控制层：对每一次工具调用进行策略检查、语义风险识别、任务能力边界校验、数据流追踪、沙箱执行和证据留存。

## 项目亮点

- **Gateway 前置授权**：统一判断工具、参数、路径、角色、关键词、SQL、命令和邮件外发风险。
- **Capability Contract**：把用户任务约束成最小权限能力合约，限制工具、资源、风险预算和步骤数。
- **Runtime Monitor**：对多步 Agent 执行过程逐步检查，而不是一次性信任完整计划。
- **Semantic Guard**：使用语义样例和本地 embedding 模型识别数据外发、凭证访问、提示注入、策略绕过等自然语言风险。
- **Sandbox Executor**：只有 `allow` 的工具调用才进入沙箱执行，`confirm` 进入人工确认，`deny` 直接阻断。
- **Data-flow Security Graph**：追踪 `tainted`、`prompt_injection`、`sensitive`、`secret` 等标签在步骤之间的传播。
- **Integrity Chain**：为 Benchmark 报告和证据包生成 SHA-256 完整性校验，支持篡改检测。
- **Benchmark Dashboard**：提供可视化前端，展示攻击缓解率、高风险流缓解率、证据完整性和安全图谱。
- **Naive Baseline 对比**：量化普通 Agent 与 AgentGuard 在安全性和可用性上的差异。

## 系统架构

```text
User Task
  |
  v
Agent Planner / LLM Agent / Fake Agent
  |
  v
Capability Contract Compiler
  |
  v
Runtime Monitor
  |
  v
Gateway Policy Engine + Semantic Guard + Data-flow Label Tracker
  |
  +--> allow   -> Sandbox Tool Executor -> Audit Evidence
  +--> confirm -> Human Approval Queue
  +--> deny    -> Blocked + Audit Evidence
  |
  v
Security Graph + Benchmark Report + Integrity Chain
  |
  v
Competition Evidence Pack + Dashboard
```

## 核心模块

| 模块 | 路径 | 说明 |
|---|---|---|
| FastAPI 入口 | `backend/main.py` | 注册 API 路由、静态前端页面和健康检查 |
| Gateway | `backend/gateway/` | 工具调用授权、策略加载、语义检测、结果构造 |
| Capability | `backend/capability/` | Capability Contract 编译与执行约束 |
| Runtime | `backend/runtime/` | 多步任务状态、运行时监控、沙箱执行、证据包 |
| Attack Chain | `backend/attack_chain/` | 多步攻击链检测 |
| Evidence | `backend/evidence/` | 安全图谱、完整性校验、覆盖矩阵、有效性统计 |
| Audit | `backend/audit/` | 审计日志与哈希链验证 |
| Routes | `backend/routes/` | Gateway、Runtime、Benchmark、Dashboard 等 API |
| Frontend | `frontend/` | 展示页、Dashboard、运行时页面和证据页面 |
| Security Cases | `security_cases/` | Gateway、Runtime、Red Team、Benchmark 样例 |
| Experiments | `experiments/` | 离线评测、方法对比和竞赛证据包生成 |
| Results | `Results/` | Benchmark 报告、Evidence Pack 输出 |

## 快速开始

### 1. 创建虚拟环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果项目中已有 `venv` 或 `.venv`，可以直接激活已有环境。

### 2. 安装依赖

```powershell
pip install -r requirements.txt
```

`sentence-transformers` 用于 Semantic Guard。首次启用语义检测时会下载并缓存 embedding 模型，耗时取决于网络环境。

### 3. 一键启动项目

```powershell
python start_project.py
```

脚本会自动检查虚拟环境、依赖和后端状态，并输出常用访问地址。

### 4. 手动启动后端

```powershell
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

- 首页：<http://127.0.0.1:8000/>
- API 文档：<http://127.0.0.1:8000/docs>
- Benchmark Dashboard：<http://127.0.0.1:8000/benchmark-dashboard>
- Security Dashboard：<http://127.0.0.1:8000/security-dashboard>
- Sandbox Dashboard：<http://127.0.0.1:8000/sandbox-dashboard>
- Authorized Evidence：<http://127.0.0.1:8000/authorized-evidence>

## 常用 API

| API | 方法 | 用途 |
|---|---:|---|
| `/api/status` | GET | 后端健康检查 |
| `/gateway/check` | POST | 检查一次工具调用是否 allow / confirm / deny |
| `/gateway/call` | POST | Gateway 检查后执行工具调用 |
| `/approval/pending` | GET | 查看待人工确认请求 |
| `/approval/confirm/{pending_id}` | POST | 通过人工确认 |
| `/approval/reject/{pending_id}` | POST | 拒绝人工确认 |
| `/capability/compile` | POST | 编译 Capability Contract |
| `/capability/enforce` | POST | 检查工具调用是否符合 Capability Contract |
| `/runtime/start` | POST | 启动运行时任务 |
| `/runtime/{task_id}/step` | POST | 执行运行时单步检查 |
| `/runtime/{task_id}/graph` | GET | 获取任务安全图谱 |
| `/runtime/{task_id}/evidence` | GET | 获取任务证据 |
| `/attack-chain/check` | POST | 检查攻击链风险 |
| `/benchmark/latest` | GET | 获取最新 Benchmark 摘要 |
| `/benchmark/latest/integrity` | GET | 获取最新报告完整性校验 |
| `/benchmark/latest/graph/{case_id}` | GET | 获取指定 case 的安全图谱 |

## Gateway 决策模型

Gateway 输出三类决策：

| 决策 | 含义 |
|---|---|
| `allow` | 风险较低且符合任务边界，可以自动执行 |
| `confirm` | 存在中等风险或需要人工确认，进入确认队列 |
| `deny` | 高风险、越权、破坏性操作或明确违规，直接拒绝 |

典型检查因素包括：

- 工具是否在 `supported_tools` 中；
- 必要参数是否完整；
- 用户角色是否允许该工具和路径；
- 路径是否包含穿越、绝对路径或敏感资源；
- Shell 命令是否包含高危操作；
- SQL 是否包含破坏性语句；
- 邮件接收人是否为外部地址；
- 内容是否包含提示注入或敏感信息；
- Agent 计划置信度是否过低；
- Capability Contract 是否允许本次调用；
- Semantic Guard 是否命中语义风险标签。

## 配置文件

| 文件 | 说明 |
|---|---|
| `config/policy.yaml` | 角色、工具、路径、关键词、风险分和决策阈值 |
| `config/semantic_guard.yaml` | 语义风险标签、样例、模型和相似度阈值 |

临时关闭语义检测：

```powershell
$env:SEMANTIC_GUARD_ENABLED="false"
```

重新开启：

```powershell
$env:SEMANTIC_GUARD_ENABLED="true"
```

## Benchmark 与证据包

### 运行离线 Runtime Benchmark

```powershell
python experiments\run_llm_runtime_benchmark.py
```

输出示例：

```text
Results/Result_XXX.json
Results/Result_XXX.html
```

### 生成竞赛证据包

```powershell
python experiments\generate_competition_evidence_pack.py
```

或一键执行：

```powershell
.\scripts\run_competition_evidence.ps1
```

输出示例：

```text
Results/EvidencePack_XXX.json
Results/EvidencePack_XXX.md
```

证据包通常包含：

- Benchmark 总体指标；
- SHA-256 完整性校验；
- 防护覆盖矩阵；
- AgentGuard 与 naive baseline 对比；
- 代表性攻击样例；
- 高风险数据流证据；
- 可复现命令；
- 答辩展示建议。

## 测试

运行全部测试：

```powershell
python -m pytest
```

运行关键单测：

```powershell
python -m pytest tests\unit
```

运行 Benchmark 相关测试：

```powershell
python -m pytest tests\benchmark
```

运行证据链相关测试：

```powershell
python -m pytest tests\evidence
```

如果 Semantic Guard 相关 benchmark 首次运行失败，请先确认：

1. 已安装 `sentence-transformers`；
2. 当前环境能下载或读取 Hugging Face 模型缓存；
3. `SEMANTIC_GUARD_ENABLED` 没有被设置为 `false`。

## 演示路线

推荐面向老师、评委或答辩场景按以下顺序展示：

1. 启动后端：

   ```powershell
   python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
   ```

2. 打开 Benchmark Dashboard：

   ```text
   http://127.0.0.1:8000/benchmark-dashboard
   ```

3. 展示关键指标：

   - Benchmark 样例数；
   - 攻击缓解率；
   - 高风险流缓解率；
   - 阻止危险执行次数；
   - Integrity VALID。

4. 打开某个 case 的安全图谱，展示数据从 `file.read` 流向 `email.send`、`shell.run` 等危险 sink 的过程。

5. 打开 `Results/EvidencePack_XXX.md`，展示完整性哈希、防护覆盖矩阵、Baseline 对比和代表性案例。

6. 对比普通 Agent：

   - 普通 Agent 倾向于按计划直接调用工具；
   - AgentGuard 会在每一步执行前做合约、策略、语义、数据流和审计检查。

## 目录结构

```text
Agent-Authorization/
├─ backend/
│  ├─ agents/               # Agent 抽象、Fake Agent、LLM Agent
│  ├─ approval/             # 人工确认队列
│  ├─ attack_chain/         # 攻击链检测
│  ├─ audit/                # 审计日志与哈希链
│  ├─ capability/           # Capability Contract
│  ├─ evidence/             # 图谱、完整性、覆盖矩阵、有效性
│  ├─ gateway/              # Gateway 授权与语义检测
│  ├─ routes/               # FastAPI 路由
│  ├─ runtime/              # Runtime Monitor 与沙箱执行
│  └─ main.py               # FastAPI 应用入口
├─ config/
│  ├─ policy.yaml           # 确定性策略
│  └─ semantic_guard.yaml   # 语义风险检测配置
├─ frontend/                # HTML Dashboard 与演示页面
├─ experiments/             # 离线实验与证据包生成
├─ security_cases/          # 安全样例与 benchmark case
├─ tests/                   # 单元、路由、证据和 benchmark 测试
├─ Results/                 # 报告和证据包输出
├─ runtime_workspace/       # 沙箱运行目录
├─ scripts/                 # 自动化脚本
├─ requirements.txt
└─ start_project.py
```

## 适用场景

AgentGuard 适合用于演示和研究以下问题：

- AI Agent 调用真实工具时如何做外部授权；
- 如何把用户任务转换为最小权限能力边界；
- 如何识别多步攻击链和数据流污染；
- 如何处理提示注入、凭证访问、数据外发和策略绕过；
- 如何生成可复现、可验真的安全评测证据；
- 如何用 benchmark 对比不同防护方法的效果。

## 注意事项

- 本项目是安全防护原型和竞赛展示项目，不应直接作为生产环境安全边界使用。
- `runtime_workspace/` 是沙箱演示目录，请不要放入真实敏感数据。
- `config/policy.yaml` 和 `config/semantic_guard.yaml` 本身被视为敏感资源，系统会阻止 Agent 自动修改安全策略。
- 语义检测依赖 embedding 模型，首次运行需要模型下载或本地缓存。
- 如果只想演示确定性策略，可临时关闭 Semantic Guard。

## License

本项目使用 `LICENSE` 文件中声明的许可证。
