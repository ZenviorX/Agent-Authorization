# Agent-Authorization

面向 AI Agent 工具调用的安全授权网关系统。

本项目用于研究和演示：当 AI Agent 可以调用文件、数据库、邮件、命令等外部工具时，如何在工具执行前加入统一的安全授权层，避免越权访问、提示注入、危险操作和数据外发风险。

系统核心思想是：**Agent 只负责规划工具调用，能不能执行由 Gateway 决定。**

---

## 1. 项目简介

大模型 Agent 的能力正在从“回答问题”扩展到“调用工具完成任务”。如果缺少安全边界，Agent 可能会因为用户输入、外部文档内容、模型误判或多步规划偏移而调用不该调用的工具。

本项目在 Agent 和工具执行器之间加入 **Gateway 安全授权网关**，对每一次工具调用进行统一检查，并输出三类结果：

| 决策 | 含义 |
|---|---|
| `allow` | 低风险，允许继续执行 |
| `confirm` | 中等风险，需要人工确认 |
| `deny` | 高风险或越权，拒绝执行 |

项目支持从自然语言输入、Agent 规划、Gateway 判定、运行时监控、沙箱执行、人工确认、审计日志到安全评测报告的完整闭环。

---

## 2. 系统流程

```text
用户自然语言命令
        ↓
FakeAgent / LLM Agent 进行任务规划
        ↓
生成结构化工具调用
        ↓
Gateway 进行授权判断
        ↓
allow / confirm / deny
        ↓
沙箱执行 / 人工确认 / 拒绝执行
```

系统不会直接信任 Agent。无论是 FakeAgent 还是真实 LLM Agent，只要要调用工具，都必须经过 Gateway、任务合约和运行时监控检查。

---

## 3. 在一台没有部署环境的电脑上运行

本项目不需要服务器部署，不需要 Docker，不需要真实邮箱服务，也不需要外部数据库服务。只要本地安装 Python、Node.js 和 Git，即可运行。

### 3.1 环境要求

| 工具 | 推荐版本 | 用途 |
|---|---|---|
| Git | 任意较新版本 | 拉取项目 |
| Python | 3.11 或 3.12 | 运行 FastAPI 后端与测试 |
| Node.js | 20 LTS | 运行 React + Vite 前端 |
| npm | 随 Node.js 安装 | 安装前端依赖 |

检查命令：

```powershell
python --version
node -v
npm -v
git --version
```

Windows 如果没有安装 Node.js，可以执行：

```powershell
winget install -e --id OpenJS.NodeJS.LTS
```

安装完成后重新打开 PowerShell，再执行 `node -v` 和 `npm -v` 检查。

---

### 3.2 拉取项目

```powershell
git clone https://github.com/ZenviorX/Agent-Authorization.git
cd Agent-Authorization
```

如果已经拉取过：

```powershell
git pull
```

---

### 3.3 一键启动

项目根目录下提供统一启动脚本：

```powershell
python .\start_project.py
```

脚本会自动完成：

1. 检查 Python 虚拟环境；
2. 创建或复用 `venv`；
3. 检查并安装后端依赖；
4. 检查 Node.js 和 npm；
5. 检查并安装前端依赖；
6. 写入前端本地代理配置；
7. 启动后端服务；
8. 启动前端服务；
9. 自动打开浏览器。

启动成功后访问：

```text
http://127.0.0.1:5173
```

后端 API 文档：

```text
http://127.0.0.1:8000/docs
```

后端状态检查：

```text
http://127.0.0.1:8000/api/status
```

---

### 3.4 手动启动

如果一键启动失败，可以手动分两个终端启动。

#### 终端一：后端

```powershell
cd Agent-Authorization
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

macOS / Linux：

```bash
cd Agent-Authorization
python3 -m venv venv
source venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

#### 终端二：前端

```powershell
cd Agent-Authorization
npm --prefix ".\frontend" config set registry https://registry.npmmirror.com
npm --prefix ".\frontend" install --registry=https://registry.npmmirror.com
npm --prefix ".\frontend" run dev
```

浏览器访问：

```text
http://127.0.0.1:5173
```

注意：不要在项目根目录直接运行 `npm run dev`，前端的 `package.json` 位于 `frontend/` 目录。

---

## 4. 推荐演示方式

在简单测试时推荐使用前端页面中的：

```text
FakeAgent 规划 + Gateway 只判定
```

该模式不依赖外部大模型 API Key，适合稳定演示。

| 输入类型 | 展示效果 |
|---|---|
| 读取公开文件 | Gateway 判定为低风险 |
| 访问敏感演示路径 | Gateway 拒绝 |
| 删除公开演示文件 | Gateway 要求人工确认 |
| 执行命令类操作 | 普通用户被限制，管理员也需要更严格检查 |
| 含有提示注入意图的输入 | Gateway 根据原始输入和工具参数识别风险 |

---

## 5. LLM 模式说明

FakeAgent 模式不需要 API Key。

如果要使用真实 LLM Agent，需要复制环境变量示例：

```powershell
Copy-Item .\.env.example .\.env
```

然后填写自己的模型服务配置。不要把真实 `.env` 或 API Key 提交到 GitHub。

---

## 6. 项目目录结构

```text
Agent-Authorization
├─ .github/workflows/       # GitHub Actions 自动化测试与报告生成
├─ Results/                 # 实验评测结果与证据包
├─ backend/                 # FastAPI 后端、安全网关、运行时监控、工具执行器
├─ config/                  # 策略配置文件
├─ docs/                    # 项目文档与归档材料
├─ examples/                # 示例材料
├─ experiments/             # 实验评测脚本
├─ frontend/                # React + Vite 前端页面
├─ runtime_workspace/       # 本地安全沙箱
├─ scripts/                 # 辅助脚本
├─ security_cases/          # 安全测试用例
├─ tests/                   # pytest 自动化测试
├─ .env.example             # 后端环境变量示例
├─ requirements.txt         # Python 依赖
├─ start_project.py         # 一键启动脚本
└─ README.md                # 项目说明
```

---

## 7. 目录说明

### `.github/workflows/`

GitHub Actions 工作流目录。当前 CI 会在提交或 PR 时运行测试，并生成安全评测报告 artifact。

### `backend/`

后端核心目录，基于 FastAPI。主要包含：

| 子模块 | 作用 |
|---|---|
| `gateway/` | 工具调用授权网关核心逻辑 |
| `routes/` | 后端 API 路由 |
| `demo/` | FakeAgent 演示链路 |
| `agents/` | 真实 LLM Agent 规划逻辑 |
| `capability/` | Capability Contract 能力约束 |
| `task_contract/` | 任务授权合约 |
| `runtime/` | 运行时监控、数据流标签、证据包 |
| `attack_chain/` | 多步攻击链检测 |
| `tools/` | 沙箱工具执行器 |
| `audit/` | 审计日志与哈希链 |
| `approval/` | 人工确认队列 |

### `frontend/`

React + Vite 前端。用于展示命令输入、Agent 规划、Gateway 判定、风险原因、审计和评测概览。

### `config/`

策略配置目录。

- `policy.yaml`：配置工具、角色、路径、风险分、关键词、决策阈值；
- `semantic_guard.yaml`：配置语义风险标签、样例和阈值。

### `runtime_workspace/`

本地安全沙箱。真实工具执行只会影响这个目录，不会影响用户电脑其他文件。

典型内容：

```text
runtime_workspace
├─ public/
├─ private/
├─ secret/
├─ outbox/
└─ agent_runtime.db
```

### `security_cases/`

安全测试用例目录，用于批量验证 Gateway 对正常样例、可疑样例和攻击样例的判断能力。

### `experiments/`

实验评测脚本目录，用于运行对比实验、攻击链评测和运行时流程评测。

### `Results/`

实验结果目录。本地或 CI 运行后会生成 HTML/JSON 报告。普通 `Result_*.html` 和 `Result_*.json` 默认不提交到仓库，避免运行产物污染项目。

### `tests/`

pytest 自动化测试目录，用于验证后端接口、Gateway 策略、任务合约、运行时监控、攻击链检测、审计完整性等功能。

### `docs/`

项目文档和过程归档目录，便于老师或评审理解项目设计。

### `scripts/`

辅助脚本目录，用于保存运行、评测、报告生成或维护类脚本。

---

## 8. 核心功能

### 8.1 Gateway 授权网关

Gateway 是项目核心。它接收 Agent 生成的工具调用请求，综合判断后返回 `allow / confirm / deny`。

核心接口：

```text
POST /gateway/check
POST /gateway/call
POST /agent/call
```

### 8.2 FakeAgent 演示链路

FakeAgent 用于稳定演示自然语言到工具调用的转换。

核心接口：

```text
GET  /demo/cases
POST /demo/fake-agent/plan
POST /demo/fake-agent/run
POST /demo/cases/{case_id}/run
```

### 8.3 LLM Agent 多步规划

真实 LLM Agent 用于更接近真实场景的多步任务规划。

核心接口：

```text
POST /agent-runtime/multistep-llm/plan
POST /agent-runtime/multistep-llm/run
POST /agent-runtime/stepwise-llm/run
GET  /agent-runtime/sessions
GET  /agent-runtime/sessions/{session_id}
```

### 8.4 Task Contract 任务授权合约

根据用户原始任务生成任务边界，限制 Agent 不偏离当前任务。

核心接口：

```text
POST /task-contract/build
```

### 8.5 Capability Contract v2

将自然语言任务编译成更细粒度的能力合约，约束工具、资源、步骤数、风险预算和输入输出标签。

核心接口：

```text
POST /capability/compile
POST /capability/enforce
```

### 8.6 Runtime Monitor 运行时监控

用于多步任务中的动态检查、数据标签追踪、安全图谱和证据包生成。

核心接口：

```text
POST /runtime/start
POST /runtime/{task_id}/step
GET  /runtime/{task_id}/graph
GET  /runtime/{task_id}/evidence
POST /runtime/{task_id}/evidence/export
GET  /runtime/{task_id}/state
GET  /runtime
```

### 8.7 攻击链检测

识别单步看似正常，但多步组合后产生风险的行为链。

核心接口：

```text
POST /attack-chain/check
GET  /attack-chain/session/{session_id}
POST /attack-chain/reset/{session_id}
```

### 8.8 人工确认

中等风险操作进入 pending 队列，由人工确认或拒绝。确认时会再次经过 Gateway 检查。

核心接口：

```text
GET  /approval/pending
POST /approval/confirm/{pending_id}
POST /approval/reject/{pending_id}
```

### 8.9 审计日志

系统记录工具调用、Gateway 决策、执行状态和人工确认结果，并支持哈希链完整性校验。

核心接口：

```text
GET /audit/logs
GET /audit/verify
```

### 8.10 沙箱工具执行器

工具执行器支持文件、邮件、命令和数据库演示操作，但所有执行都被限制在 `runtime_workspace` 中。

沙箱状态接口：

```text
GET /runtime/sandbox/status
GET /runtime/sandbox/files
GET /runtime/sandbox/outbox
GET /runtime/sandbox/database
GET /runtime/sandbox/demo-run
```

### 8.11 安全概览与评测报告

项目提供安全概览和 Benchmark 报告读取接口：

```text
GET /security/overview
GET /benchmark/reports
GET /benchmark/latest
GET /benchmark/latest/integrity
GET /benchmark/latest/graph/{case_id}
GET /benchmark/latest/effectiveness
```

---

## 9. GitHub Actions 工作流

项目配置了 CI：

```text
.github/workflows/ci.yml
```

触发条件：

- push 到 `main`；
- push 到 `improve-risk-policy`；
- pull request 到 `main`；
- 手动触发。

CI 包含两个主要任务：

| Job | 功能 |
|---|---|
| `basic-test` | 安装依赖并运行 `python -m pytest tests -q` |
| `dashboard` | 生成安全评测仪表盘并上传 artifact |

生成的 artifact 名称为：

```text
ci-test-dashboard
```

---

## 10. 本地测试与构建

运行后端测试：

```powershell
python -m pytest
```

运行前端构建检查：

```powershell
npm --prefix ".\frontend" run build
```

只启动后端：

```powershell
python .\start_project.py --backend-only
```

只启动前端：

```powershell
python .\start_project.py --frontend-only
```

不自动打开浏览器：

```powershell
python .\start_project.py --no-open
```

---

## 11. 常见问题

### 为什么打开 8000 不是前端页面？

当前项目是前后端分离架构。正式前端入口是：

```text
http://127.0.0.1:5173
```

8000 是后端 API 服务和 Swagger 文档地址。

### 为什么 npm 找不到 package.json？

前端项目在 `frontend/` 目录。请使用：

```powershell
npm --prefix ".\frontend" run dev
```

### 为什么 LLM 模式不能用？

LLM 模式需要配置 `.env` 中的模型服务 API Key。课堂演示建议优先使用 FakeAgent 模式。

### 项目会不会操作真实文件？

不会。真实工具执行被限制在 `runtime_workspace/` 沙箱目录。

### 前端会自动读取 GitHub Actions 结果吗？

不会。Actions 生成的评测报告会作为 artifact 上传。后端可以读取本地 `Results/Result_*.json`，但 GitHub artifact 不会自动同步到本地前端。

---

## 12. 项目总结

Agent-Authorization 构建了一个 AI Agent 工具调用安全网关原型。它将自然语言任务、Agent 工具规划、Gateway 授权、任务合约、运行时数据流监控、沙箱执行、人工确认、审计日志和安全评测整合成一个完整系统。

核心价值：

1. Agent 不能直接执行工具；
2. 所有工具调用必须先经过 Gateway；
3. 支持 `allow / confirm / deny` 三态决策；
4. 支持策略配置化；
5. 支持提示注入和敏感资源风险识别；
6. 支持任务级能力约束；
7. 支持多步运行时监控和攻击链检测；
8. 支持沙箱执行与审计证据；
9. 支持自动化测试和 CI 评测报告。

一句话概括：

> 本项目在 AI Agent 和真实工具之间建立了一道可配置、可解释、可审计的安全边界，让 Agent 能用工具，但不能越权、不能绕过策略、不能随意造成高风险影响。
