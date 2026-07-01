# Agent-Authorization

面向 AI Agent 工具调用的授权、安全边界、沙箱执行与审计系统。

本项目解决的问题是：当 AI Agent 能够调用文件、邮件、数据库、Shell 命令等外部工具时，如何在工具真正执行前加入一个统一、可解释、可审计的安全授权层，避免越权访问、提示注入、敏感信息泄露、危险命令执行和多步攻击链风险。

核心原则：

> Agent 只负责提出工具调用计划；是否允许执行、是否需要确认、是否进入沙箱，由 Agent-Authorization Gateway 决定。

---

## 1. 项目定位

Agent-Authorization 不是普通聊天机器人，也不是单纯关键词过滤器。它是位于 **AI Agent 与真实工具之间** 的安全运行时网关。

系统对每一次工具调用输出三类决策：

| 决策 | 含义 |
|---|---|
| `allow` | 低风险，允许进入受控执行流程 |
| `confirm` | 存在副作用或中等风险，需要人工确认 |
| `deny` | 高风险、越权或违反任务边界，拒绝执行 |

系统重点解决：

- Agent 是否有权调用某个工具；
- 当前任务是否允许这次工具调用；
- 工具参数是否包含路径穿越、敏感路径、危险命令、外发风险；
- OAuth-style scope 是否足够；
- 多步工具调用是否形成攻击链；
- 真实执行是否被限制在沙箱中；
- 每一次判定和执行是否能形成审计证据。

---

## 2. 总体架构

```text
User Task
   ↓
FakeAgent / LLM Agent / External Agent
   ↓
External Agent Adapter / Tool Proxy
   ↓
OAuth-style Scope Check
   ↓
Capability Contract / Task Boundary Guard
   ↓
Runtime Monitor / Attack Chain Detector
   ↓
Sandbox Policy
   ↓
allow / confirm / deny
   ↓
Hybrid Sandbox Executor
   ├─ Docker Sandbox, if Docker is available
   └─ Native Subprocess Sandbox, if Docker is not available
   ↓
Audit Log / Evidence / Frontend Display
```

一句话概括：

> Gateway 决定能不能执行；Capability Token 绑定这一次授权；Hybrid Sandbox 限制在哪里执行；Audit Evidence 证明发生了什么。

---

## 3. 核心能力

### 3.1 Gateway 授权网关

支持标准工具调用：

| 工具 | 用途 |
|---|---|
| `file.read` | 读取文件 |
| `file.write` | 写入文件 |
| `file.delete` | 删除文件 |
| `email.send` | 邮件发送或 outbox 模拟 |
| `shell.run` | 命令执行 |
| `db.query` | 数据库查询 |
| `http.post` | HTTP 外发场景建模 |

Gateway 会结合用户身份、工具类型、资源路径、参数内容、策略配置、任务合约和运行时上下文输出最终决策。

### 3.2 OAuth-style 外部 Agent 授权

项目支持模拟 OpenClaw、WorkBuddy、Custom Agent 等外部 Agent 平台。外部 Agent 不直接访问本地工具，而是必须经过：

```text
External Agent → Adapter → Tool Proxy → Gateway → Runtime Monitor → Sandbox
```

OAuth-style scope 只解决“Agent 声明自己有什么权限”，本项目进一步判断：

- 当前任务是否允许这个动作；
- 工具参数是否安全；
- 数据是否可能外发；
- 是否偏离任务边界；
- 是否需要 Capability Token；
- 是否必须进入沙箱执行。

### 3.3 两阶段授权与 Capability Token

真执行流程采用两阶段设计：

```text
Phase 1: execute=false
    Gateway 检查通过后签发 Capability Token

Phase 2: execute=true + capability_token
    Gateway 重新校验 token
    token 与 user、agent_platform、task、tool、params、sandbox_profile 绑定
    校验通过后才进入沙箱执行
```

这样可以避免 Agent 在拿到一次授权后修改工具、参数或执行环境。

### 3.4 Hybrid Sandbox 真执行沙箱

项目实现了两类执行沙箱，并自动选择：

| 执行引擎 | 是否需要额外软件 | 隔离强度 | 用途 |
|---|---:|---|---|
| Docker Sandbox | 需要 Docker Desktop | 较强，容器级隔离 | 有 Docker 环境时使用 |
| Native Subprocess Sandbox | 不需要额外软件 | 中等，项目内置受限子进程 | 默认本地演示 fallback |

Native Subprocess Sandbox 不等同于 Docker、gVisor 或 Firecracker；它是基础版、无需安装额外软件的本地可运行沙箱。它通过工具白名单、路径白名单、写入目录限制、超时控制和 evidence 文件实现受控执行。

### 3.5 独立测试模块

项目将评测系统独立到 `test/` 目录：

```text
test/
  cases/                 # Gateway 测试样例
  results/               # 运行结果，默认 git ignore
  run.py                 # 独立测试运行器
  api.py                 # 测试结果 API 预留
  README.md
```

运行：

```powershell
python -m test.run
```

输出：

```text
test/results/latest_summary.json
test/results/latest_cases.json
test/results/latest_detail.csv
test/results/latest_report.md
test/results/latest_dashboard.html
```

前端“测试报告”页面可一键触发测试并刷新结果。

---

## 4. 快速启动

### 4.1 环境要求

| 工具 | 推荐版本 | 用途 |
|---|---|---|
| Git | 较新版本 | 拉取项目 |
| Python | 3.11 / 3.12 | 后端、测试、Native Sandbox |
| Node.js | 20 LTS | React + Vite 前端 |
| npm | 随 Node.js 安装 | 安装前端依赖 |
| Docker Desktop | 可选 | Docker Sandbox，非必需 |

### 4.2 安装依赖

```powershell
cd "D:\文档\15信安赛项目\仓库\Agent-Authorization"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

npm --prefix ".\frontend" install
```

### 4.3 一键启动

```powershell
python .\start_project.py --clean
```

启动后访问：

```text
前端：http://localhost:5173
后端：http://127.0.0.1:8000
API 文档：http://127.0.0.1:8000/docs
```

---

## 5. 提交前验证命令

### 5.1 后端状态

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/status
```

### 5.2 Native Sandbox，无需 Docker

```powershell
Invoke-RestMethod http://127.0.0.1:8000/sandbox-native/health

Invoke-RestMethod -Method Post http://127.0.0.1:8000/sandbox-native/execute `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"tool":"file.read","params":{"path":"public/notice.txt"},"sandbox_profile":"local_readonly"}'
```

敏感读取阻断：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/sandbox-native/execute `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"tool":"file.read","params":{"path":"secret/password.txt"},"sandbox_profile":"strict"}'
```

### 5.3 独立评测

```powershell
python -m test.run
```

### 5.4 pytest 回归测试

```powershell
python -m pytest tests/test_native_sandbox_executor.py
python -m pytest tests/test_docker_sandbox_executor.py
python -m pytest tests -q
```

### 5.5 前端构建

```powershell
npm --prefix ".\frontend" run build
```

---

## 6. 前端提交版导航

提交版前端已按展示逻辑整理成四组：

| 分组 | 页面 | 说明 |
|---|---|---|
| 一、核心演示 | 授权工作台、两阶段授权 | 先展示 Agent → Gateway → Token → Sandbox → Evidence 主链路 |
| 二、运行数据 | 总览仪表盘、授权请求、审计日志 | 展示请求、风险、人工确认和审计证据 |
| 三、规则与评测 | 策略管理、测试报告、项目说明 | 展示策略、自动测试和 OAuth 对比逻辑 |
| 四、系统配置 | 系统设置 | 展示当前演示配置 |

推荐展示顺序：

```text
1. 授权工作台
   选择“真沙箱执行（自动选择）”
   运行：真沙箱读取 public / 真沙箱写入 outbox / 敏感读取阻断

2. 两阶段授权
   说明 execute=false 签发 token，execute=true 消费 token

3. 总览仪表盘
   说明项目整体架构和审计闭环

4. 测试报告
   点击一键运行测试，展示 Gateway 自动评测结果

5. 项目说明
   说明 NoGuard、OAuth-only、AgentGuard 的差异
```

没有 Docker 时，前端仍然会展示：

```json
"sandbox_evidence": {
  "sandbox_type": "native_subprocess"
}
```

---

## 7. 后端接口概览

| 模块 | 路径 | 说明 |
|---|---|---|
| Gateway | `/gateway/check` | 单次工具调用授权判断 |
| Tool Proxy | `/tool-proxy/authorize` | 外部 Agent 统一工具调用入口 |
| External Agent | `/external-agent/simulate` | OpenClaw / WorkBuddy / Custom Agent 模拟接入 |
| Native Sandbox | `/sandbox-native/*` | 无 Docker 的内置执行沙箱 |
| Docker Sandbox | `/sandbox-docker/*` | Docker 执行沙箱，可选 |
| Test Results | `/test-results/*` | 独立测试结果读取与一键运行 |
| Runtime | `/runtime/*` | 运行时状态与多步检测 |
| Audit | `/audit/*` | 审计日志 |
| Approval | `/approval/*` | 人工确认流程 |

---

## 8. 项目目录结构

```text
Agent-Authorization/
  .github/workflows/        # CI
  backend/                  # FastAPI 后端
    adapters/               # 外部 Agent Adapter
    capability/             # Capability Contract
    guardrails/             # 任务边界、token、授权轨迹
    proxy/                  # Tool Proxy 与 OAuth-style profile
    routes/                 # API routes
    runtime/                # Runtime Monitor
    sandbox/                # Sandbox Policy / Docker / Native / Hybrid Executor
    tools/                  # 受控工具执行器
  config/                   # policy.yaml / semantic_guard.yaml
  docs/                     # 架构、OAuth 对比、沙箱说明
  examples/                 # 演示脚本
  frontend/                 # React + Vite 前端
  runtime_workspace/        # 本地沙箱工作区，运行产物默认忽略
  scripts/                  # 辅助脚本
  test/                     # 独立评测模块
  tests/                    # pytest 回归测试
  start_project.py          # 一键启动脚本
  requirements.txt
  README.md
```

说明：

- `test/` 是产品化评测模块，面向展示、报告和前端结果读取；
- `tests/` 是 pytest 自动化测试，面向开发回归；
- `runtime_workspace/` 是本地沙箱目录，不应存放真实敏感文件；
- Docker 不是必需依赖，Native Subprocess Sandbox 可直接运行。

---

## 9. 与 OAuth 的关系

OAuth 解决的是：

```text
某个应用 / Agent 是否被授权访问某类资源。
```

Agent-Authorization 进一步解决的是：

```text
这个 Agent 在当前任务、当前上下文、当前工具参数下，能不能安全执行这一次具体动作。
```

例如，Agent 拥有 `tool:file:read` scope，并不代表它可以在任意任务中读取任意文件。系统仍会检查：

- 读取路径是否在任务边界内；
- 是否访问 `secret/`、`private/`、`.env` 等敏感资源；
- 是否来自提示注入链路；
- 结果是否可能被外发；
- 是否需要人工确认；
- 是否必须进入沙箱执行。

---

## 10. 展示话术

可以这样介绍项目：

```text
我们做的不是一个新的 OAuth，也不是普通聊天机器人。
我们做的是 AI Agent 工具调用前的授权网关。
当 OpenClaw、WorkBuddy 或企业自研 Agent 想调用文件、邮件、数据库或命令行工具时，它们不能直接执行，而是必须通过 Adapter 和 Tool Proxy 转成标准授权请求。
系统再进行 OAuth-style scope 检查、任务边界检查、Capability Token 校验、Runtime Monitor、Sandbox Policy 和 Hybrid Sandbox 执行，最后输出 allow / confirm / deny，并生成可审计证据。
```

---

## 11. 当前边界

- Native Subprocess Sandbox 不等同于 Docker、gVisor 或 Firecracker；它是无需安装额外软件的本地可运行 fallback。
- Docker Sandbox 是可选增强，适合有 Docker Desktop 的环境。
- WorkBuddy / OpenClaw 当前是接入协议与模拟场景，不代表已经真实调用官方 API。
- 前端仍保留少量 mock fallback，用于后端不可用时的演示兜底；核心授权、测试、沙箱接口已经接入真实后端。

---

## 12. License

This project is for research, teaching, and security demonstration purposes.
