# AgentGuard：面向 AI Agent 工具调用的授权网关与沙箱审计系统

> 仓库目录名为 `Agent-Authorization`，作品正式名称建议使用 **AgentGuard**。  
> 本项目面向 AI Agent 工具调用场景，在 Agent 与真实工具之间加入授权网关、Tool Proxy、Capability Token、运行时监控、沙箱执行与审计证据链，防止智能体越权读取、敏感数据外发、危险命令执行和不可追溯操作。

---

## 1. 项目定位

随着 AI Agent 从“回答问题”发展到“调用工具”，模型输出可能直接影响文件、邮件、数据库、命令行和网络接口。传统权限控制通常只判断“用户有没有权限”，但在 Agent 场景下，还必须进一步判断：

```text
这一次工具调用是否符合当前任务？
工具参数是否越权？
数据是否从低可信来源传播到了危险工具？
是否存在提示注入、路径绕过、凭证访问或数据外发？
是否需要人工确认？
是否能够留下可复盘证据？
```

AgentGuard 的核心思想是：

```text
Agent 只负责提出工具调用计划；
真正能否执行，由独立 Gateway、Capability Token、Runtime Monitor 和 Sandbox 共同决定。
```

本项目不是普通聊天机器人，也不是单纯 OAuth 实现，而是一套 **AI Agent 工具调用前置授权与运行时安全控制系统**。

---

## 2. 系统主链路

```text
User Task
   ↓
AI Agent / External Agent
   ↓
Tool Proxy / Adapter
   ↓
OAuth-style Scope Check
   ↓
Gateway + Task Boundary Guard
   ↓
Capability Token 两阶段授权
   ↓
Runtime Monitor / Attack Chain Detector
   ↓
Hybrid Sandbox 执行允许的工具
   ↓
Audit Evidence / Hash Chain 留证
```

系统最终对每一次工具调用输出三态决策：

| 决策 | 含义 |
|---|---|
| `allow` | 低风险，允许进入受控执行流程 |
| `confirm` | 中风险或存在副作用，需要人工确认 |
| `deny` | 高风险、越权或策略违规，拒绝执行 |

---

## 3. 当前核心能力

| 能力 | 说明 |
|---|---|
| Gateway 前置授权 | 对单次工具调用进行工具、参数、角色、路径、内容、命令、SQL、风险分和任务边界检查 |
| Tool Proxy | 统一接入外部 Agent 工具调用，并执行 OAuth-style scope 初筛与两阶段授权 |
| OAuth-style Scope Check | 检查外部 Agent 声明权限是否覆盖本次工具调用需求，但不作为最终执行授权 |
| Capability Token | 将授权绑定到用户、Agent 平台、原始任务、工具、参数和 sandbox profile，防止授权后篡改或重放 |
| Task Boundary Guard | 判断当前工具调用是否偏离用户原始任务和临时授权边界 |
| Runtime Monitor | 维护多步任务状态，记录步骤、风险、标签传播和数据流关系 |
| Attack Chain Detector | 识别“提示注入 → 敏感访问 → 外部发送 / 高危命令”等组合攻击链 |
| Hybrid Sandbox | 有 Docker 时使用 Docker Sandbox；无 Docker 时自动 fallback 到 Native Subprocess Sandbox |
| Audit Evidence | 记录每次授权、拒绝、执行、证据 hash 和可复盘原因 |
| React/Vite 前端 | 提供授权演示、运行证据、测试报告和项目说明四个提交版页面 |
| 独立测试模块 | `python -m test.run` 自动读取 `test/cases/gateway_cases*.json` 并生成结构化评测结果 |
| GitHub Actions CI | 自动执行后端回归测试、Gateway 样例评测和前端构建 |

---

## 4. 快速启动

以下命令建议在 Windows PowerShell 中执行。

### 4.1 进入项目目录

```powershell
cd Agent-Authorization
```

### 4.2 创建并激活虚拟环境

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

如 PowerShell 阻止脚本执行，可先运行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

### 4.3 安装后端依赖

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4.4 安装前端依赖

```powershell
npm install --prefix ".\frontend"
```

也可以进入前端目录安装：

```powershell
cd ".\frontend"
npm install
cd ..
```

### 4.5 一键启动项目

```powershell
python .\start_project.py --clean
```

启动后访问：

```text
前端页面：http://localhost:5173
后端接口：http://127.0.0.1:8000
接口文档：http://127.0.0.1:8000/docs
```

> 本机浏览器优先打开 `http://localhost:5173` 或 `http://127.0.0.1:5173`，不要使用 Vite 输出的虚拟网卡 Network 地址。

---

## 5. 推荐演示路线

前端提交版已经收敛为四个主页面：

```text
1. 授权演示
2. 运行证据
3. 测试报告
4. 项目说明
```

### 5.1 授权演示

进入 **授权演示** 页面，建议依次点击：

```text
真沙箱读取
敏感文件拦截
OAuth 外发拒绝
```

讲解重点：

```text
Agent 提出工具调用
→ Tool Proxy 统一入口
→ Gateway 判断 allow / confirm / deny
→ Capability Token 绑定授权
→ Hybrid Sandbox 受控执行
→ Audit Evidence 留证
```

### 5.2 运行证据

进入 **运行证据** 页面，点击“刷新数据”。该页面读取本机真实运行数据，包括：

```text
logs/audit.log
runtime_workspace/native_sandbox_runs/
runtime_workspace/sandbox_runs/
test/results/latest_summary.json
```

讲解重点：系统不是只显示固定 mock 数据，而是会根据本地审计日志、沙箱 evidence 和测试结果动态聚合指标。

### 5.3 测试报告

进入 **测试报告** 页面，点击“一键运行测试”。当前独立测试模块读取：

```text
test/cases/gateway_cases*.json
```

并输出：

```text
test/results/latest_summary.json
test/results/latest_cases.json
test/results/latest_detail.csv
test/results/latest_report.md
test/results/latest_dashboard.html
```

当前提交版评测目标：

```text
131 cases
131 passed
0 failed
100.00% 样例通过率
100.00% 风险阻断/确认率
0.00% 风险误放行率
0.00% 正常误拒率
```

### 5.4 项目说明

进入 **项目说明** 页面，重点讲清楚：

```text
NoGuard：Agent 生成工具调用后直接执行，风险最高。
OAuth-only：只能说明权限声明，不足以判断当前任务、参数和数据流是否安全。
AgentGuard：在 scope 之后继续检查 Gateway、任务边界、Token、Runtime、Sandbox 和 Audit Evidence。
```

---

## 6. 提交前验证命令

### 6.1 独立 Gateway 样例测试

```powershell
python -m test.run
```

预期输出示例：

```text
=== Agent-Authorization Test Finished ===
cases: 131
passed: 131
failed: 0
accuracy: 100.00%
risk_block_or_confirm: 100.00%
risk_unsafe_allow: 0.00%
normal_false_deny: 0.00%
```

### 6.2 后端授权回归测试

```powershell
python scripts/run_backend_authorization_tests.py
```

预期结果：

```text
44 passed
```

### 6.3 前端构建检查

```powershell
npm --prefix ".\frontend" run build
```

如果 `--prefix` 在本地环境中不稳定，可使用：

```powershell
cd ".\frontend"
npm run build
cd ..
```

---

## 7. GitHub Actions CI

项目已配置 GitHub Actions 自动检查流程，位于：

```text
.github/workflows/ci.yml
```

触发条件：

```text
push 到 main
pull_request 到 main
手动 workflow_dispatch
```

CI 会依次执行：

```text
1. Checkout repository
2. Set up Python 3.11
3. Install requirements.txt
4. python scripts/run_backend_authorization_tests.py
5. python -m test.run --case-dir test/cases --output-dir test/results
6. Set up Node.js 20
7. npm install --no-audit --no-fund
8. npm run build
9. Upload test/results/** as artifact
```

该流程用于保证每次提交后：

```text
后端授权逻辑没有回归
Capability Token 和两阶段授权仍然有效
Gateway 样例测试可通过
React/Vite 前端可以正常构建
测试结果可以作为 artifact 下载复盘
```

---

## 8. 主要目录结构

```text
Agent-Authorization/
├── backend/                    # FastAPI 后端
│   ├── gateway/                # Gateway 授权网关核心逻辑
│   ├── proxy/                  # Tool Proxy 与外部 Agent 授权入口
│   ├── real_agent/             # 真实 LLM tool-calling 适配
│   ├── capability/             # Capability Contract v2
│   ├── guardrails/             # Task Boundary 与 Capability Token
│   ├── runtime/                # Runtime Monitor 与安全图谱
│   ├── attack_chain/           # 多步攻击链检测
│   ├── audit/                  # 审计日志与哈希链校验
│   ├── approval/               # 人工确认模块
│   ├── sandbox/                # Docker / Native / Hybrid Sandbox
│   ├── tools/                  # 受控工具执行逻辑
│   └── routes/                 # API 路由
│
├── config/
│   ├── policy.yaml             # 核心策略配置
│   └── semantic_guard.yaml     # 语义风险配置
│
├── frontend/                   # React + Vite 前端
│   └── src/
│       ├── pages/              # 授权演示 / 运行证据 / 测试报告 / 项目说明
│       ├── components/         # 页面组件
│       └── services/           # API 调用封装
│
├── test/                       # 独立 Gateway 样例评测模块
│   ├── cases/                  # gateway_cases*.json
│   ├── results/                # latest_summary / cases / detail / report / dashboard
│   └── run.py                  # python -m test.run
│
├── tests/                      # pytest 后端回归测试
├── runtime_workspace/          # 本地沙箱工作区
├── docs/                       # 项目文档与阶段性材料
├── .github/workflows/          # GitHub Actions CI
├── start_project.py            # 一键启动脚本
└── README.md
```

---

## 9. 关键 API 概览

| 模块 | 接口 | 说明 |
|---|---|---|
| 状态检查 | `GET /api/status` | 查看后端状态和已注册能力 |
| Gateway | `POST /gateway/check` | 对单次工具调用进行 allow / confirm / deny 判断 |
| Gateway | `POST /gateway/call` | 授权后执行、确认或拒绝工具调用 |
| Tool Proxy | `POST /tool-proxy/authorize` | 外部 Agent 统一授权入口 |
| 两阶段授权 | `POST /tool-proxy/two-phase/prepare` | 第一阶段授权检查并签发 Capability Token |
| 两阶段授权 | `POST /tool-proxy/two-phase/execute` | 第二阶段校验 Token 并进入沙箱执行 |
| Capability Token | `POST /tool-proxy/capability-token/status` | 查看 token 状态 |
| Capability Token | `POST /tool-proxy/capability-token/events` | 查看 token issue / consume 事件 |
| 真实 LLM 接入 | `POST /real-agent/tool-call/run` | 接收 OpenAI-compatible tool_calls / function_call |
| Native Sandbox | `POST /sandbox-native/execute` | 在 Native Subprocess Sandbox 中执行工具 |
| Native Sandbox | `GET /sandbox-native/runs` | 查看本地沙箱运行记录 |
| Docker Sandbox | `POST /sandbox-docker/execute` | 在 Docker Sandbox 中执行工具 |
| 测试结果 | `GET /test-results/latest/summary` | 读取最新独立测试摘要 |
| 前端聚合数据 | `GET /api/overview` | 聚合本地 audit、sandbox evidence 和测试摘要 |
| 前端聚合数据 | `GET /api/requests` | 读取最近本地授权 / 沙箱记录 |
| 前端聚合数据 | `GET /api/audit-logs` | 读取本地审计时间线 |

---

## 10. 测试样例说明

当前独立测试入口为：

```powershell
python -m test.run
```

测试脚本会自动读取：

```text
test/cases/gateway_cases*.json
```

当前样例覆盖方向包括：

```text
正常公开文件读取
公开目录写入
只读数据库查询
提示注入
路径穿越
URL 编码绕过
Windows / Linux 绝对路径
secret / private / .env 敏感资源访问
外部邮件敏感内容外发
HTTP webhook / 外部 API 外发
高危 shell / PowerShell / curl / wget
危险 SQL / SQL 注入
未知工具 fail closed
低置信度计划
Capability Contract 边界
外部 Agent / OAuth-style 场景
Hybrid Sandbox 边界
多步攻击链
```

测试输出用于前端“测试报告”页面和作品报告实验数据。

---

## 11. 沙箱说明

项目实现 Hybrid Sandbox：

```text
有 Docker：优先使用 Docker Sandbox
无 Docker：自动 fallback 到 Native Subprocess Sandbox
```

### Docker Sandbox

Docker Sandbox 提供更强的执行隔离能力，典型限制包括：

```text
--network none
--read-only
--cap-drop ALL
--security-opt no-new-privileges
内存 / CPU / PID 限制
临时目录 tmpfs
```

### Native Subprocess Sandbox

Native Subprocess Sandbox 不依赖 Docker，适合本地演示和比赛复现。它通过以下方式限制执行：

```text
受限子进程
工具白名单
路径白名单
写入目录限制
命令白名单
超时控制
evidence.json 证据文件
```

需要说明：

```text
Native Subprocess Sandbox 是轻量级本地执行沙箱，不声称等同于 Docker、gVisor 或 Firecracker 级别的系统强隔离。
```

---

## 12. 运行证据数据来源

前端“运行证据”页面读取本地真实运行数据，不再以固定 mock 数据作为主来源。

主要数据源：

```text
logs/audit.log
runtime_workspace/native_sandbox_runs/
runtime_workspace/sandbox_runs/
test/results/latest_summary.json
config/policy.yaml
```

当用户运行授权演示、真沙箱执行或一键测试后，刷新运行证据页面即可看到本地数据变化。

---

## 13. 当前系统边界

本项目当前是信安赛参赛原型，边界如下：

```text
1. 不训练或微调大模型本身。
2. 不声称识别所有自然语言攻击变体。
3. 当前实验结论仅对已构建的样例集和原型实现成立。
4. Native Subprocess Sandbox 是本地 fallback，不是系统级强隔离。
5. WorkBuddy、OpenClaw 等外部 Agent 主要作为接入场景和协议模拟，不代表已完成官方平台深度集成。
6. 真实 LLM tool-calling 接入提供 OpenAI-compatible 格式适配入口，生产级多模型长期稳定性评测属于后续工作。
7. 100% 测试通过率表示当前 131 条样例范围内的结果，不代表真实世界全场景绝对安全。
```

---

## 14. 答辩讲解建议

可以用下面这段话快速介绍项目：

```text
AgentGuard 解决的是 AI Agent 调用真实工具时的授权和安全边界问题。
普通 Agent 生成工具调用后可能直接执行，容易造成越权读取、敏感数据外发或危险命令执行。
我们的系统把 Agent 的规划权和工具执行权分离：Agent 只能提出计划，所有工具调用必须经过 Tool Proxy、Gateway、Capability Token、Runtime Monitor 和 Hybrid Sandbox，最终输出 allow、confirm 或 deny，并留下可审计证据。
```

对比 OAuth 时可以说：

```text
OAuth 主要解决“外部应用是否被授权访问某类资源”；
AgentGuard 进一步解决“当前任务、当前参数、当前数据流和当前执行环境下，这一次工具调用是否安全”。
```

---

## 15. 常用命令汇总

```powershell
# 启动项目
python .\start_project.py --clean

# 独立样例测试
python -m test.run

# 后端授权回归测试
python scripts/run_backend_authorization_tests.py

# 前端构建
npm --prefix ".\frontend" run build

# 后端健康检查
Invoke-RestMethod http://127.0.0.1:8000/api/status

# Native Sandbox 健康检查
Invoke-RestMethod http://127.0.0.1:8000/sandbox-native/health

# 最新测试摘要
Invoke-RestMethod http://127.0.0.1:8000/test-results/latest/summary
```

---

## 16. 项目总结

AgentGuard 的核心价值不在于声称“完全解决 Agent 安全”，而在于提供了一条清晰可运行、可解释、可复现的工程路径：

```text
让模型负责规划；
让独立网关负责授权；
让 Capability Token 绑定单次执行；
让运行时监控负责上下文风险；
让沙箱限制真实执行；
让审计系统负责证据复盘。
```

该系统为 AI Agent 工具调用安全落地提供了一个可展示、可测试、可持续扩展的实践样板。
