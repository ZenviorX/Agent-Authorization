# Agent-Authorization

## 面向 AI Agent 工具调用的任务级授权与安全防护系统

Agent-Authorization（展示名：**AgentGuard**）是一个面向 AI Agent 工具调用场景的授权与安全防护系统。项目聚焦于大语言模型 Agent 在调用文件、邮件、数据库、Shell 命令等外部工具时可能产生的越权访问、提示注入、敏感信息泄露、危险命令执行和多步攻击链风险，设计并实现了一套：

```text
授权检查 → 风险评估 → 语义检测 → 能力约束 → 沙箱执行 → 审计取证
```

的安全闭环。

系统不会让 Agent 直接执行工具调用，而是在每一次工具执行前进行统一安全检查，并输出三类决策：

| 决策 | 含义 |
|---|---|
| `allow` | 允许执行 |
| `confirm` | 需要人工确认 |
| `deny` | 拒绝执行 |

项目核心思想：

> 不把 Agent 当成完全可信主体，而是将每一次工具调用都放入任务边界、能力合约、风险评分、语义风险、攻击链上下文和审计证据中进行动态授权。

---

## 1. 项目背景

随着大语言模型从普通问答走向 AI Agent，模型不再只是生成文本，而是能够调用外部工具完成真实任务，例如读取文件、写入文件、发送邮件、查询数据库和执行 Shell 命令。

这类能力显著提升了 Agent 的实用性，但也带来了新的安全风险：

1. **越权访问敏感资源**：Agent 可能读取 `secret/`、`.env`、`password.txt`、`private/` 等敏感文件。
2. **间接提示注入攻击**：Agent 读取外部网页或公开文件后，可能被其中隐藏的恶意指令诱导，偏离原始任务。
3. **敏感信息外发**：Agent 可能将密码、密钥、token 等内容通过邮件、命令行或网络请求外发。
4. **高危工具调用**：Agent 可能执行 `rm -rf`、`shutdown`、`curl | sh`、`DROP TABLE` 等危险操作。
5. **多步攻击链风险**：单次调用看似安全，但多次调用串联后，可能形成“读取低可信内容 → 受到提示注入 → 访问敏感文件 → 外发数据”的完整攻击链。

本项目的目标是构建一个位于 Agent 与工具之间的安全运行时：

> 安全操作自动放行，危险操作自动拦截，可疑操作人工确认，所有行为可解释、可审计、可复盘。

---

## 2. 系统定位

本项目不是简单的关键词过滤器，也不是传统登录鉴权系统，而是面向 AI Agent 工具调用场景的任务级零信任安全运行时。

系统重点解决以下问题：

- Agent 是否有权限调用某个工具；
- Agent 是否有权限访问某个资源；
- 工具参数是否存在路径穿越、敏感信息、危险命令等风险；
- 当前工具调用是否偏离用户原始任务；
- 自然语言是否存在数据外发、凭证访问、策略绕过等模糊语义风险；
- 多步工具调用之间是否形成攻击链；
- 安全决策是否能够解释；
- 工具执行是否发生在受控沙箱内；
- 审计证据是否能够用于事后复查。

整体流程：

```text
用户自然语言任务
        │
        ▼
任务能力合约 Capability Contract
        │
        ▼
Agent 工具调用请求 ToolCallRequest
        │
        ▼
Agent Authorization Gateway
        │
        ├── 硬策略风险评分 policy.yaml
        ├── Embedding 语义风险检测 semantic_guard.yaml
        ├── Capability Contract 检查
        ├── Runtime Monitor / Attack Chain 检查
        │
        ├── allow   → 进入安全沙箱执行
        ├── confirm → 进入人工确认流程
        └── deny    → 阻断执行
        │
        ▼
审计日志 / 证据包 / 展示报告
```

---

## 3. 核心能力

### 3.1 工具调用前置授权网关

系统支持对以下标准工具进行统一授权检查：

| 工具 | 说明 |
|---|---|
| `file.read` | 读取文件 |
| `file.write` | 写入文件 |
| `file.delete` | 删除文件 |
| `email.send` | 发送邮件 |
| `shell.run` | 执行 Shell 命令 |
| `db.query` | 查询数据库 |

每次工具调用都会被封装为结构化请求：

```json
{
  "user": "user",
  "tool": "file.read",
  "params": {
    "path": "public/notice.txt"
  },
  "agent_confidence": 0.95
}
```

Gateway 会根据用户角色、工具类型、资源路径、参数内容、硬策略、语义检测、任务合约和攻击链状态输出最终决策。

---

### 3.2 策略化风险评分

项目使用 `config/policy.yaml` 作为确定性硬策略配置文件。当前策略版本为：

```text
v4.2-policy-and-semantic-ready
```

系统只保留两类角色：

| 角色 | 含义 |
|---|---|
| `user` | 普通用户或普通 Agent，默认最小权限 |
| `admin` | 管理员或高权限 Agent，高危操作仍需确认 |

`config/policy.yaml` 主要负责明确、可解释、可审计的硬规则，包括：

- 用户与角色映射；
- 支持工具注册表；
- 必要参数约束；
- Agent 计划置信度阈值；
- 内部可信邮箱域名；
- 工具基础风险分；
- 资源路径风险分；
- 风险决策阈值；
- 细粒度风险加分；
- 危险关键词；
- 角色权限策略；
- 任务授权合约默认策略；
- `config/policy.yaml` 与 `config/semantic_guard.yaml` 的自保护规则。

典型决策逻辑：

```text
低风险 + 权限允许       → allow
中风险或策略要求确认   → confirm
高风险或明确违规       → deny
```

---

### 3.3 Embedding 语义风险检测

仅靠明文关键词无法覆盖所有自然语言变体。为此，项目新增本地 Embedding 语义风险检测模块，用于识别关键词规则难以覆盖的数据外发、凭证访问、策略绕过、提示注入变体、破坏性操作等语义风险。

相关文件：

| 文件 | 作用 |
|---|---|
| `config/semantic_guard.yaml` | 配置语义检测开关、Embedding 模型、风险标签、阈值和语义样例 |
| `backend/gateway/semantic_guard.py` | 实现本地 Embedding 相似度检测 |
| `backend/gateway/gateway.py` | 合并硬策略风险和语义风险，输出最终决策 |

语义检测模块会将一次工具调用的上下文组合成文本，包括：

- 用户身份；
- 用户角色；
- 工具名称；
- 工具参数；
- 文件路径；
- 邮件或写入内容；
- Shell 命令；
- SQL 语句。

随后系统使用本地句向量模型将工具调用上下文编码为向量，并与 `semantic_guard.yaml` 中配置的风险样例进行余弦相似度匹配。

当前语义风险标签包括：

| 标签 | 含义 |
|---|---|
| `data_exfiltration` | 数据外发或向外部目标泄露信息 |
| `credential_access` | 读取密码、token、密钥、私钥等凭证 |
| `policy_bypass` | 绕过网关、跳过审计、跳过人工确认 |
| `prompt_injection` | 提示注入、系统消息覆盖、忽略安全规则 |
| `destructive_action` | 删除、覆盖、格式化、破坏数据 |
| `network_abuse` | 扫描、恶意外联、下载执行 |
| `privilege_escalation` | 提权、伪装管理员、绕过普通用户限制 |

语义检测不会替代确定性策略，而是作为风险升级器参与最终决策：

```text
确定性硬策略风险
        +
Embedding 语义风险
        ↓
统一风险评分
        ↓
allow / confirm / deny
```

默认情况下，语义检测处于开启状态。首次本地运行时会自动下载 Embedding 模型，下载完成后使用本地缓存。本地演示时可以通过环境变量开启：

PowerShell：

```powershell
$env:SEMANTIC_GUARD_ENABLED="false"
```

Bash：

```bash
export SEMANTIC_GUARD_ENABLED=true
```

如需临时关闭语义检测，可以在 `config/semantic_guard.yaml` 中将：

```yaml
enabled: true
```

改为：

```yaml
enabled: false
```

首次启用时，系统会下载：

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

模型下载完成后会使用本地缓存。

---

### 3.4 可解释安全决策

Gateway 不只返回 `allow / confirm / deny`，还会返回：

- `risk_score`：风险分数；
- `risk_level`：风险等级；
- `reason`：自然语言解释；
- `explanations`：结构化解释。

示例：

```json
{
  "decision": "deny",
  "risk_score": 188,
  "risk_level": "critical",
  "reason": [
    "文件读取操作存在一定信息泄露风险",
    "访问路径命中资源风险规则：secret/，风险分 +90",
    "命中 user 角色 deny 策略"
  ]
}
```

这样可以让用户和评审清楚看到：为什么放行、为什么需要确认、为什么拒绝，以及风险主要来自路径、工具、命令、SQL、邮件外发、任务合约还是语义检测。

---

### 3.5 Capability Contract 任务能力合约

传统权限控制通常是：

```text
用户 → 角色 → 工具权限
```

本项目进一步引入任务级能力合约：

```text
用户任务 → Capability Contract → 每一步工具调用检查
```

Capability Contract 描述本次任务中 Agent 被授予的最小能力边界，包括：

- 允许调用哪些工具；
- 每个工具允许访问哪些资源；
- 外发工具允许发送给哪些收件人；
- 当前步骤允许接收哪些数据标签；
- 工具执行后会产生哪些数据标签；
- 每项能力消耗多少风险预算；
- 哪些能力需要人工确认；
- 最多允许执行多少步；
- 总风险预算是多少。

示例能力边界：

```text
用户任务：读取 public/notice.txt 并整理摘要

合约生成：
- 允许 file.read 访问 data/public/notice.txt
- 禁止访问 data/secret/*
- 禁止 shell.run
- 禁止 db.query
- 最大步骤数：5
- 风险预算：80
```

这样即使 Agent 被提示注入污染，也无法轻易突破当前任务边界。

---

### 3.6 运行时状态监控

系统提供 Runtime Monitor，用于维护一个任务执行过程中的运行时状态。它可以记录：

- 当前任务编号；
- 原始用户任务；
- 当前执行到第几步；
- 已使用风险预算；
- 每一步工具调用；
- 每一步输入标签和输出标签；
- 是否存在待确认步骤；
- 是否已经被阻断；
- 攻击链检测状态。

运行时接口可以将多步工具调用串联起来，而不是只看单次请求。

---

### 3.7 多步攻击链检测

项目实现了攻击链检测器，用于识别单步检查难以发现的链式风险。

典型攻击链：

```text
读取低可信内容
        ↓
发现提示注入内容
        ↓
访问敏感资源
        ↓
外发数据或执行高危命令
```

系统能够识别以下阶段：

| 阶段 | 含义 |
|---|---|
| `external_content_read` | 读取外部或低可信内容 |
| `prompt_injection_detected` | 检测到提示注入内容 |
| `sensitive_resource_access` | 访问敏感资源 |
| `external_output` | 向外部目标发送信息 |
| `high_risk_command` | 执行高危命令 |
| `data_exfiltration_chain` | 形成完整数据外发攻击链 |
| `prompt_to_command_execution_chain` | 提示注入诱导命令执行 |

攻击链风险会影响最终运行时决策，使系统具备上下文感知能力。

---

### 3.8 安全沙箱工具执行

为了证明系统不是只做“纸面判断”，项目实现了真实沙箱工具执行器。

所有真实执行都限制在：

```text
runtime_workspace/
```

当前沙箱工具支持：

| 工具 | 执行方式 |
|---|---|
| `file.read` | 读取沙箱内文件 |
| `file.write` | 写入沙箱内文件 |
| `file.delete` | 删除沙箱内文件 |
| `email.send` | 不真实外发，写入 `runtime_workspace/outbox/` |
| `shell.run` | 只允许少量安全命令，工作目录固定在沙箱 |
| `db.query` | 查询沙箱 SQLite 数据库，只允许 SELECT |

这样既可以展示真实工具执行，又不会影响用户电脑上的真实文件。

---

### 3.9 Gateway 授权证据包

项目提供授权证据包接口，用于证明工具调用确实经过了 Gateway，而不是直接执行。

接口：

```text
GET /sandbox-evidence/authorized-run
```

该接口会自动执行一组演示样例：

1. 正常读取公开文件；
2. 越权读取敏感文件；
3. 路径穿越攻击；
4. 提示注入诱导外发；
5. 普通用户尝试执行系统命令。

每一步都会记录用户、工具、参数、Gateway 决策、是否真正执行、执行结果、解释说明和记录时间。

只有 `allow` 的调用才会进入沙箱执行器；`confirm` 和 `deny` 的调用不会执行。

---

### 3.10 沙箱运行证据包

项目还提供沙箱运行证据包接口，用于证明文件、邮件、数据库、命令确实在沙箱内执行，并产生可复查结果。

接口：

```text
GET /sandbox-evidence/run
```

证据包会保存为 JSON 文件，并计算 SHA256 哈希：

```text
runtime_workspace/evidence/
```

证据包可用于证明：

- 工具调用进入了真实沙箱；
- 邮件没有真实外发，而是写入 outbox；
- 数据库查询来自沙箱 SQLite；
- 路径穿越会被拦截；
- 证据文件内容可以通过哈希校验复核。

---

### 3.11 展示报告自动生成

项目提供国赛展示报告接口：

```text
GET /showcase-report/generate
```

系统会统计：

- 证据包总数；
- Gateway 授权证据包数量；
- 沙箱运行证据包数量；
- SHA256 校验通过数量；
- 工具调用总步数；
- 实际执行步数；
- 成功执行步数；
- 阻断步数；
- 最新证据包信息。

并生成：

```text
runtime_workspace/reports/showcase_report_*.md
runtime_workspace/reports/showcase_report_*.json
```

---

### 3.12 审计日志与哈希链

系统支持审计日志记录与哈希链防篡改。每条日志包含：

```json
{
  "prev_hash": "上一条日志的哈希值",
  "record_hash": "当前日志的哈希值"
}
```

如果历史日志被修改、删除、插入或重排，哈希链校验会失败。

校验接口：

```text
GET /audit/verify
```

---

### 3.13 安全样例库与自动评测

项目维护安全样例库：

```text
security_cases/
├── gateway_cases.json
├── gateway_cases_v2.json
├── gateway_cases_v3.json
└── attack_chain_cases.json
```

其中：

- `gateway_cases.json`：基础网关安全样例；
- `gateway_cases_v2.json`：第二批增强攻击样例；
- `gateway_cases_v3.json`：增强型攻击样例，包括编码路径、提示注入、命令绕过、SQL 风险等；
- `attack_chain_cases.json`：多步攻击链样例。

CI 仪表盘脚本会读取：

```text
security_cases/gateway_cases*.json
```

并生成 HTML 实验结果页面：

```text
python tests/dashboard/generate_ci_dashboard.py
```

生成结果位于：

```text
Results/Result_*.html
```

---

### 3.14 真实 Stepwise LLM Agent 运行时演示

为避免项目停留在固定脚本化 Demo，本项目支持真实 Stepwise LLM Agent Runtime 演示链。该模式下，系统会调用真实大模型进行逐步工具规划：Agent 每次只生成下一步候选工具调用，随后该调用必须经过 Capability Contract、Runtime Monitor、Attack Chain Detector、Gateway 和 Sandbox Executor 检查。只有 `allow` 的步骤才会进入沙箱真实执行。

该模式用于证明：

```text
真实 LLM Agent 可以接入系统，
但真实工具执行权不交给 Agent，
每一步工具调用都必须经过任务级授权边界和运行时安全检查。
```

---

## 4. 系统架构

```text
┌──────────────────────────────┐
│        用户自然语言任务        │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│ Capability Contract Compiler │
│ 生成任务级最小能力边界          │
└───────────────┬──────────────┘
                │
                ▼
┌──────────────────────────────┐
│      Agent Tool Call          │
│ user / tool / params / labels │
└───────────────┬──────────────┘
                │
                ▼
┌────────────────────────────────────┐
│ Agent Authorization Gateway         │
├────────────────────────────────────┤
│ 1. 工具名规范化                      │
│ 2. 参数规范化                        │
│ 3. 工具风险评分                      │
│ 4. 资源路径风险检查                  │
│ 5. 角色权限策略                      │
│ 6. 提示注入与敏感内容检测            │
│ 7. 命令与 SQL 风险检测               │
│ 8. Embedding 语义风险检测            │
│ 9. 任务授权合约检查                  │
│ 10. Capability Contract 检查         │
└───────────────┬────────────────────┘
                │
       ┌────────┼────────┐
       ▼        ▼        ▼
     allow   confirm    deny
       │        │        │
       ▼        ▼        ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│ 沙箱执行  │ │ 人工确认  │ │ 阻断执行  │
└────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │            │
     └────────────┴────────────┘
                  │
                  ▼
┌──────────────────────────────┐
│ Runtime Monitor / AttackChain │
│ 审计日志 / 证据包 / 展示报告     │
└──────────────────────────────┘
```

---

## 5. 项目目录结构

```text
Agent-Authorization/
├── backend/
│   ├── agent/                    # Demo Agent / FakeAgent 相关逻辑
│   ├── attack_chain/             # 多步攻击链检测
│   ├── audit/                    # 审计日志与哈希链
│   ├── capability/               # Capability Contract 能力合约
│   ├── gateway/                  # 授权网关核心逻辑
│   │   ├── gateway.py            # Gateway 主决策逻辑
│   │   ├── policy_loader.py      # 读取 config/policy.yaml
│   │   ├── plan_guard.py         # Agent 计划质量检查
│   │   └── semantic_guard.py     # Embedding 语义风险检测
│   ├── routes/                   # FastAPI 路由
│   ├── runtime/                  # 运行时状态监控
│   ├── task_contract/            # 任务授权合约 v1
│   ├── tools/                    # 安全沙箱工具执行器
│   ├── main.py                   # FastAPI 应用入口
│   └── schemas.py                # 请求与响应模型
├── config/
│   ├── policy.yaml               # 确定性硬策略配置文件
│   └── semantic_guard.yaml       # Embedding 语义检测配置文件
├── frontend/
│   ├── index.html
│   ├── security_dashboard.html
│   ├── attack_chain_runtime.html
│   ├── sandbox_dashboard.html
│   ├── authorized_evidence.html
│   └── showcase.html
├── security_cases/
│   ├── gateway_cases.json
│   ├── gateway_cases_v2.json
│   ├── gateway_cases_v3.json
│   └── attack_chain_cases.json
├── tests/
│   ├── unit/
│   ├── routes/
│   └── dashboard/
├── Results/
│   └── Result_*.html
├── runtime_workspace/            # 运行时生成，沙箱目录
├── requirements.txt
└── README.md
```

---

## 6. 运行环境

建议使用：

```text
Python 3.10+
FastAPI
Uvicorn
Pydantic
PyYAML
SQLite
sentence-transformers
numpy
```

安装依赖：

```cmd
python -m pip install -r requirements.txt
```

---

## 7. 快速启动

### 7.1 进入项目目录

```cmd
cd /d C:\Users\24727\Documents\GitHub\Agent-Authorization
```

也可以进入你自己的项目目录，例如：

```powershell
cd "D:\文档\15信安赛项目\仓库\Agent-Authorization"
```

### 7.2 激活虚拟环境

Windows CMD：

```cmd
venv\Scripts\activate.bat
```

PowerShell：

```powershell
.\venv\Scripts\Activate.ps1
```

如果 PowerShell 提示禁止运行脚本，可以执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

然后重新激活：

```powershell
.\venv\Scripts\Activate.ps1
```

### 7.3 可选：启用 Embedding 语义检测

默认语义检测关闭。如果需要本地演示语义检测，PowerShell 执行：

```powershell
$env:SEMANTIC_GUARD_ENABLED="false"
```

### 7.4 启动后端

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

启动后访问：

```text
http://127.0.0.1:8000/
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

状态接口：

```text
http://127.0.0.1:8000/api/status
```

---

## 8. 前端页面

| 页面 | 地址 | 作用 |
|---|---|---|
| 首页 | `/` | 基础演示入口 |
| 安全总览 | `/security-dashboard` | 查看安全能力和评测概览 |
| 任务链演示 | `/task-chain` | 展示任务级调用链 |
| 攻击链运行时 | `/attack-chain-runtime` | 展示多步攻击链检测 |
| 沙箱证据面板 | `/sandbox-dashboard` | 查看沙箱执行证据 |
| 授权证据面板 | `/authorized-evidence` | 查看 Gateway 授权执行证据 |
| 国赛展示页 | `/showcase` | 汇总展示项目能力与证据 |

---

## 9. 主要接口

### 9.1 网关检查

```text
POST /gateway/check
```

请求示例：

```json
{
  "user": "user",
  "tool": "file.read",
  "params": {
    "path": "secret/password.txt"
  },
  "agent_confidence": 0.95
}
```

### 9.2 网关调用

```text
POST /gateway/call
```

该接口会经过 Gateway 检查，并根据结果决定是否执行工具。

### 9.3 Agent 调用

```text
POST /agent/call
```

用于模拟 Agent 工具调用，并交给 Gateway 检查。

### 9.4 Runtime 任务启动

```text
POST /runtime/start
```

请求示例：

```json
{
  "user": "user",
  "original_task": "请读取 public/notice.txt 并总结内容",
  "max_steps": 5,
  "risk_budget": 80
}
```

### 9.5 Runtime 单步检查

```text
POST /runtime/{task_id}/step
```

请求示例：

```json
{
  "tool": "file.read",
  "params": {
    "path": "public/notice.txt"
  },
  "input_labels": [],
  "output_content": "这是一份公开通知。"
}
```

### 9.6 Runtime 状态查询

```text
GET /runtime/{task_id}/state
GET /runtime
```

### 9.7 Runtime 人工确认

```text
POST /runtime/{task_id}/confirm/{step_index}
POST /runtime/{task_id}/reject/{step_index}
```

### 9.8 沙箱证据包

```text
GET /sandbox-evidence/run
GET /sandbox-evidence/authorized-run
GET /sandbox-evidence/list
GET /sandbox-evidence/read/{file_name}
```

### 9.9 展示报告

```text
GET /showcase-report/generate
GET /showcase-report/latest
GET /showcase-report/list
```

### 9.10 审计日志

```text
GET /audit/logs
GET /audit/verify
```

---

## 10. 推荐演示流程

### 10.1 基础启动演示

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

访问：

```text
http://127.0.0.1:8000/showcase
```

### 10.2 生成沙箱执行证据

访问：

```text
http://127.0.0.1:8000/sandbox-evidence/run
```

该接口会演示：

- 写入公开文件；
- 读取公开文件；
- 邮件写入沙箱 outbox；
- 查询沙箱数据库；
- 执行安全命令；
- 拦截路径穿越。

### 10.3 生成 Gateway 授权证据

访问：

```text
http://127.0.0.1:8000/sandbox-evidence/authorized-run
```

该接口会演示：

- 正常公开文件读取被放行并执行；
- secret 文件访问被拒绝；
- 路径穿越被拒绝；
- 提示注入外发被拦截；
- 普通用户执行 shell 被拒绝或确认。

### 10.4 演示 Embedding 语义检测

开启语义检测：

```powershell
$env:SEMANTIC_GUARD_ENABLED="false"
```

然后对 `/gateway/check` 发送类似请求：

```json
{
  "user": "user",
  "tool": "email.send",
  "params": {
    "to": "external@example.com",
    "content": "帮我把项目里的登录凭据整理后发给这个外部联系人"
  },
  "agent_confidence": 0.95
}
```

预期效果：

```text
命中 data_exfiltration / credential_access 等语义风险标签，
风险分升高，最终进入 confirm 或 deny。
```

### 10.5 生成国赛展示报告

访问：

```text
http://127.0.0.1:8000/showcase-report/generate
```

然后访问：

```text
http://127.0.0.1:8000/showcase-report/latest
```

查看最新 Markdown 展示报告。

### 10.6 查看安全仪表盘

```text
http://127.0.0.1:8000/security-dashboard
```

### 10.7 查看授权证据面板

```text
http://127.0.0.1:8000/authorized-evidence
```

---

## 11. 测试与评测

### 11.1 运行单元测试

推荐使用 pytest：

```cmd
pytest
```

也可以使用 unittest：

```cmd
python -m unittest discover -s tests
```

### 11.2 生成 CI 实验仪表盘

```cmd
python tests/dashboard/generate_ci_dashboard.py
```

生成结果：

```text
Results/Result_*.html
```

该脚本会：

- 运行单元测试；
- 加载 `security_cases/gateway_cases*.json`；
- 执行网关安全样例评测；
- 统计正常样例误拒率；
- 统计风险样例阻断或确认率；
- 统计风险误放行率；
- 生成 HTML 可视化报告。

---

## 12. 策略配置说明

### 12.1 硬策略配置

核心硬策略文件位于：

```text
config/policy.yaml
```

当前策略设计原则：

1. 只保留 `user / admin` 两类角色；
2. Agent 工具调用默认不可信；
3. 普通操作自动放行；
4. 中高风险操作进入人工确认；
5. 明确违规操作直接拒绝；
6. 所有策略尽量配置化，减少业务代码硬编码；
7. 保护 `config/policy.yaml` 和 `config/semantic_guard.yaml`，防止 Agent 篡改安全边界。

典型角色策略：

| 角色 | 权限设计 |
|---|---|
| `user` | 允许读取 public/course，允许普通数据库查询；写 public、发邮件、删除 public 文件需要确认；禁止访问 secret/private/credentials/config/.env；禁止执行 shell.run |
| `admin` | 可以访问更多资源，但删除文件和 shell.run 仍然需要确认；禁止自动写入或删除策略文件、语义检测配置、secrets、env 等敏感配置 |

### 12.2 语义检测配置

语义检测配置文件位于：

```text
config/semantic_guard.yaml
```

它主要配置：

- 是否启用语义检测；
- Embedding 模型名称；
- 全局确认阈值和拒绝阈值；
- 每类语义风险标签的风险分；
- 每类语义风险标签的相似度阈值；
- 每类语义风险标签的样例句。

该文件属于配置文件，应提交到仓库；但 `.env`、模型缓存、虚拟环境、密钥文件不应提交。

---

## 13. 安全设计亮点

### 13.1 任务级最小权限

系统不直接给 Agent 长期权限，而是根据当前任务生成临时能力边界。

### 13.2 策略化风险评分

工具、路径、内容、命令、SQL、邮箱外发、Agent 置信度都会参与风险评分。

### 13.3 Embedding 语义风险检测

系统不仅依赖关键词规则，还通过本地句向量相似度识别数据外发、凭证访问、策略绕过、提示注入变体等模糊语义风险。

### 13.4 Capability Contract

能力合约可以精确描述当前任务允许调用哪些工具、访问哪些资源、向哪些目标外发、消耗多少风险预算。

### 13.5 多步攻击链检测

系统不仅判断单次工具调用，还会记录连续调用中的攻击链风险。

### 13.6 沙箱真实执行

工具调用不是只停留在判断层面，而是可以在 `runtime_workspace` 中真实执行并产生可复查痕迹。

### 13.7 审计与证据固化

审计日志支持哈希链，沙箱证据包和展示报告支持 SHA256 校验。

### 13.8 可复现实验体系

项目提供安全样例库、自动化评测脚本和 HTML 结果仪表盘，便于复现实验结果。

---

## 14. 项目创新点

### 14.1 从传统权限控制扩展到 Agent 工具调用授权

传统权限控制更多关注“用户是否有权限访问系统”，本项目关注的是“Agent 在某个任务中是否可以执行某一步工具调用”。

### 14.2 任务合约驱动的动态授权

系统通过 Capability Contract 将自然语言任务转化为可检查的工具能力边界，实现任务级最小授权。

### 14.3 硬策略与语义检测结合

项目将确定性硬规则与本地 Embedding 语义检测结合：硬规则保证可解释边界，语义检测补充自然语言变体风险识别。

### 14.4 攻击链感知的运行时安全

系统记录同一任务中的连续工具调用，能够识别提示注入、敏感访问和数据外发之间的链式关系。

### 14.5 授权后执行证据

系统不仅能说“我拦截了危险操作”，还可以生成证据包证明“只有通过 Gateway 的操作才会进入沙箱执行”。

### 14.6 面向竞赛展示的可复查闭环

系统提供前端页面、证据包、展示报告、评测仪表盘和哈希校验，便于答辩展示和结果复核。

---

## 15. 当前边界与说明

当前项目仍是比赛原型系统，不是生产级 IAM 或商业网关。当前版本有以下边界：

- 不真实发送邮件，邮件写入沙箱 outbox；
- Shell 只允许少量安全命令；
- 数据库使用沙箱 SQLite；
- Runtime 状态主要用于本地演示；
- Embedding 语义检测默认关闭，需要本地显式开启；
- 语义检测用于风险升级，不用于降低原有硬策略风险；
- 项目重点是 Agent 工具调用阶段的动态授权，不是替代 OAuth、OIDC、Keycloak 等身份系统。

这些限制是有意设计的：项目优先保证可控、可演示、可复现、可解释。

---

## 16. 后续规划

后续可以继续扩展以下方向：

1. **完善评测体系**：扩展更多提示注入、数据外发、权限绕过、SQL 攻击和命令执行样例。
2. **新增语义检测测试集**：增加 `security_cases/gateway_cases_v4.json`，专门覆盖数据外发、凭证访问、策略绕过等语义场景。
3. **强化 CI 门禁**：将单元测试、安全评测、攻击链评测和报告生成拆分为严格 CI 阶段。
4. **结构化返回语义检测结果**：在 Gateway 响应中增加 `semantic_guard` 字段，便于前端和审计系统展示。
5. **增强 Runtime 持久化**：将运行时任务状态从内存进一步扩展为 JSONL、SQLite 或 Redis。
6. **接入真实 LLM Agent**：在保留 FakeAgent 演示的基础上，引入真实 LLM 工具调用流程。
7. **MCP 工具代理适配**：将 Gateway 封装为 MCP 工具调用前置代理，保护文件系统、数据库、浏览器等 MCP 工具。
8. **策略可视化配置**：提供策略编辑页面，使用户可以更直观地配置风险阈值、角色权限和任务边界。
9. **更完整的对比实验**：对比无防护 Agent、关键词过滤器、单步 Gateway 和本系统的攻击阻断效果。

---

## 17. 项目价值

Agent-Authorization 的核心价值在于：

> 为 AI Agent 工具调用提供一层任务级、可解释、可审计、可复查的安全运行时。

它能够：

- 在工具执行前进行授权检查；
- 对危险工具调用进行自动拦截；
- 对可疑操作引入人工确认；
- 对任务能力进行最小化约束；
- 通过本地 Embedding 识别关键词规则难以覆盖的语义风险；
- 对多步攻击链进行上下文感知检测；
- 在受控沙箱中执行真实工具调用；
- 生成可复查的证据包和展示报告；
- 支持安全样例库和自动化评测。

最终目标是为 AI Agent 在真实工具调用环境中的安全运行提供一个可落地、可解释、可演示的防护框架。
