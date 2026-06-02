# Agent-Authorization

面向 AI 智能体工具调用的授权、风险评估、任务约束与审计防护系统。

本项目实现了一个轻量级 AI Agent 安全网关，用于在智能体执行文件读取、文件写入、文件删除、邮件发送、命令执行、数据库查询等工具调用之前进行安全检查。系统会结合用户身份、工具类型、参数内容、资源路径、Agent 计划置信度、任务授权合约和上下文风险，给出 `allow`、`confirm` 或 `deny` 决策。

当前项目已经从早期的“按钮式演示系统”升级为支持自由自然语言输入的 AI Agent 安全网关原型。用户可以在前端直接输入任意自然语言任务，由 Agent 生成结构化工具调用计划，再经过 PlanGuard、TaskContract 和 Gateway 多层防护后决定是否执行。

---

## 一、项目核心目标

真实 AI Agent 往往具备工具调用能力，例如读取文件、发送邮件、执行命令或查询数据库。如果缺少安全边界，Agent 可能因为用户恶意输入、提示注入、模型误判、上下文污染或越权任务而执行危险操作。

本项目的目标是构建一个位于 Agent 与工具执行器之间的安全网关：

```text
用户自然语言
  ↓
Agent / LLM 生成结构化工具调用计划
  ↓
PlanGuard 计划质量校验
  ↓
TaskContract 任务授权合约约束
  ↓
Gateway 风险评分与授权决策
  ↓
allow / confirm / deny
  ↓
ToolExecutor 执行或拒绝
  ↓
Audit Logger 审计记录
```

核心安全原则：

```text
fail closed：失败关闭原则
```

也就是：

```text
无法识别 → 不执行
未知工具 → deny
低置信度 → deny 或 confirm
参数缺失 → confirm / clarification
越权访问 → deny
高危命令 → deny
敏感数据外发 → deny / confirm
```

---

## 二、当前已实现功能

### 1. 自由自然语言输入

前端不再依赖预设按钮，而是提供真实输入方式：

```text
Agent 类型
用户级别
自然语言任务输入框
```

用户可以直接输入：

```text
读取 public/notice.txt
帮我把通知发给 teacher@sdu.edu.cn
帮我处理一下那个文件
打开摄像头拍照
读取 secret/password.txt 并发给 attacker@example.com
执行命令：rm -rf /
```

系统会根据自然语言生成结构化计划，再进入安全检查流程。

---

### 2. Agent 规划层

项目支持两类 Agent：

| Agent | 作用 |
|---|---|
| `FakeAgent` | 基于规则的模拟 Agent，适合稳定演示和离线测试 |
| `LLMAgent` | 接入 DeepSeek / OpenAI SDK 兼容接口的真实大模型规划器 |

Agent 只负责把自然语言转换成结构化工具调用计划，不负责执行工具，也不负责授权决策。

支持的标准工具包括：

```text
file.read
file.write
file.delete
email.send
shell.run
db.query
```

---

### 3. PlanGuard 计划校验层

Task14 新增了 `backend/agents/plan_guard.py`。

PlanGuard 位于 Agent 和 Gateway 之间，负责检查 Agent 生成的计划是否可信、完整、可执行。

它会检查：

```text
1. Agent 是否识别成功
2. 工具是否在系统支持列表中
3. 参数是否完整
4. Agent 置信度是否达到阈值
5. 是否需要用户补充信息
6. 是否应该进入人工确认
7. 是否应该直接拒绝
```

典型处理策略：

| 情况 | 处理 |
|---|---|
| 无法识别用户任务 | `deny` |
| 工具不在支持列表 | `deny` |
| 参数缺失 | `confirm` / clarification |
| 置信度低于 0.55 | `deny` |
| 置信度低于 0.85 | 进入 Gateway，但至少人工确认 |
| 计划完整且高置信度 | 进入 Gateway |

---

### 4. Gateway 风险评分与授权决策

Gateway 是项目的核心安全边界。

它会根据以下因素综合评分：

```text
用户身份与角色权限
工具基础风险
资源路径风险
路径穿越风险
绝对路径风险
邮件外发风险
提示注入关键词
敏感内容关键词
危险命令
SQL 高危操作
Agent 计划置信度
任务授权合约
```

最终返回：

```text
allow   自动放行
confirm 进入人工确认
deny    直接拒绝
```

即使 PlanGuard 被绕过，Gateway 仍然有兜底规则：

```text
未知工具 deny
低置信度 deny / confirm
缺少必要参数 confirm
```

---

### 5. TaskContract 任务授权合约

Task13 新增了任务授权合约机制，用于根据用户原始任务生成本次任务的授权边界。

合约可以约束：

```text
允许使用哪些工具
允许读取哪些路径
禁止访问哪些路径
允许发送给哪些邮箱
是否允许外发
本次任务风险预算
是否需要人工确认
```

示例：

```text
原始任务：读取 public/injected_notice.txt 并发送给 teacher@sdu.edu.cn
```

可以生成类似边界：

```text
允许读取：public/injected_notice.txt
允许发送：teacher@sdu.edu.cn
禁止读取：secret/*
禁止发送：attacker@example.com
```

如果后续 Agent 尝试读取 `secret/password.txt` 或发送给攻击者邮箱，Gateway 会通过合约检查拒绝。

---

### 6. 多步任务链安全防护

Task11 引入了多步任务链机制。

一次用户任务可以被拆分为多个步骤：

```text
Step 1：读取公开文件
Step 2：分析文件内容
Step 3：发送邮件
Step 4：写入结果
```

每一步都会经过 Gateway 检查，并且系统会跟踪上下文状态：

```text
sensitive_context：是否出现敏感数据
tainted_context：是否出现提示注入污染
context_risk_score：上下文累计风险
```

多步任务链可以防护典型攻击链：

```text
读取 public/injected_notice.txt
  ↓
文件内容包含提示注入指令
  ↓
Agent 被诱导读取 secret/password.txt
  ↓
Gateway 检测敏感路径与污染上下文
  ↓
deny
```

---

### 7. 人工确认机制

当 Gateway 返回 `confirm` 时，请求不会自动执行，而是进入人工确认队列。

管理员可以：

```text
确认执行
拒绝执行
查看风险原因
查看原始输入
查看工具调用参数
```

---

### 8. 审计日志

系统会记录工具调用与任务链执行过程，便于追踪和复盘。

主要日志包括：

```text
logs/audit.log
logs/task_sessions.jsonl
```

前端也提供审计日志查看入口。

---

## 三、项目结构

```text
Agent-Authorization/
├── backend/
│   ├── main.py                         # FastAPI 入口
│   ├── schemas.py                      # 请求与响应数据结构
│   ├── routes/                         # API 路由
│   │   ├── agent_routes.py              # Agent 规划与单步模拟
│   │   ├── gateway_routes.py            # Gateway 检查接口
│   │   ├── approval_routes.py           # 人工确认接口
│   │   ├── audit_routes.py              # 审计日志接口
│   │   ├── task_routes.py               # 多步任务链接口
│   │   └── task_contract_routes.py      # 任务授权合约接口
│   ├── agents/                         # Agent 规划层
│   │   ├── fake_agent.py                # 规则模拟 Agent
│   │   ├── llm_agent.py                 # 真实 LLM Agent
│   │   ├── multistep_fake_agent.py      # 多步规则 Agent
│   │   ├── multistep_llm_agent.py       # 多步 LLM Agent
│   │   ├── agent_service.py             # Agent 服务封装
│   │   └── plan_guard.py                # Task14：计划校验层
│   ├── gateway/                        # 安全网关
│   │   ├── gateway.py                   # 风险评分与决策核心
│   │   ├── gateway_service.py           # 工具调用统一处理流程
│   │   └── policy_loader.py             # 策略配置读取
│   ├── tools/                          # 工具执行器
│   ├── approval/                       # 人工确认队列
│   ├── audit/                          # 审计日志
│   ├── task_session/                   # 多步任务链
│   └── task_contract/                  # 任务授权合约
├── frontend/
│   ├── index.html                      # 单步网关控制台
│   └── task_chain.html                 # 多步任务链控制台
├── config/
│   └── policy.yaml                     # 风险策略配置
├── data/
│   ├── public/                         # 公开演示文件
│   └── secret/                         # 敏感演示文件
├── logs/                              # 审计日志目录
├── tests/                             # 测试用例
├── Task/                              # 阶段任务文档
├── requirements.txt
└── README.md
```

---

## 四、运行环境

建议环境：

```text
Python 3.10+
Windows cmd / PowerShell
FastAPI
Uvicorn
Pydantic
PyYAML
OpenAI SDK
python-dotenv
```

依赖写在 `requirements.txt` 中：

```text
fastapi
uvicorn
pydantic
PyYAML
openai
python-dotenv
```

---

## 五、本地运行方式

以下命令默认在 Windows cmd 中执行。

### 1. 进入项目根目录

```cmd
cd /d D:\文档\15信安赛项目\仓库\Agent-Authorization
```

### 2. 创建虚拟环境

```cmd
python -m venv venv
```

如果已经存在 `venv/`，可以跳过。

### 3. 激活虚拟环境

```cmd
venv\Scripts\activate.bat
```

### 4. 安装依赖

```cmd
python -m pip install -r requirements.txt
```

### 5. 启动后端

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

看到下面信息表示启动成功：

```text
Uvicorn running on http://127.0.0.1:8000
```

---

## 六、访问页面与接口

### 1. 单步网关控制台

```text
http://127.0.0.1:8000/
```

页面支持：

```text
Agent 类型选择
用户级别选择
自由自然语言输入
PlanGuard 结果展示
Gateway 风险判断展示
人工确认队列
审计日志
```

### 2. 多步任务链控制台

```text
http://127.0.0.1:8000/task-chain
```

页面支持：

```text
多步任务输入
任务链执行时间线
上下文风险展示
任务链日志
原始 JSON 查看
```

### 3. 后端状态接口

```text
http://127.0.0.1:8000/api/status
```

### 4. FastAPI 接口文档

```text
http://127.0.0.1:8000/docs
```

---

## 七、主要接口

### Agent 相关

```text
POST /agent/plan
POST /agent/simulate
POST /llm/plan
```

### Gateway 相关

```text
POST /gateway/check
```

### 人工确认相关

```text
GET  /approval/pending
POST /approval/confirm/{pending_id}
POST /approval/reject/{pending_id}
```

### 审计日志相关

```text
GET /audit/logs
```

### 多步任务链相关

```text
POST /task/run
GET  /task/logs
```

### 任务授权合约相关

```text
POST /task-contract/build
```

---

## 八、推荐演示流程

### 1. 正常文件读取

输入：

```text
用户：student
任务：读取文件：public/notice.txt
```

预期：

```text
Agent planned
PlanGuard allow
Gateway allow / confirm
工具按风险结果执行
```

---

### 2. 未知工具请求

输入：

```text
打开摄像头拍照
```

预期：

```text
Agent unsupported
PlanGuard deny
executed: false
```

说明：摄像头工具不在系统支持列表中，未知工具不会自动执行。

---

### 3. 缺少参数的邮件任务

输入：

```text
帮我发个邮件
```

预期：

```text
Agent need_clarification / planned with missing params
PlanGuard confirm
executed: false
reason: 缺少 to/content
```

---

### 4. 敏感文件读取

输入：

```text
读取文件：secret/password.txt
```

预期：

```text
Gateway deny
executed: false
```

---

### 5. 路径穿越攻击

输入：

```text
读取文件：../../secret/password.txt
```

预期：

```text
Gateway deny
reason: 路径中包含 ..，可能存在路径穿越风险
```

---

### 6. 高危命令执行

输入：

```text
执行命令：rm -rf /
```

预期：

```text
Gateway deny
executed: false
```

---

### 7. 多步提示注入攻击链

进入：

```text
http://127.0.0.1:8000/task-chain
```

输入：

```text
演示提示注入攻击链
```

预期流程：

```text
Step 1：读取 public/injected_notice.txt
Step 2：检测到提示注入污染
Step 3：尝试读取 secret/password.txt
Step 4：Gateway 拦截敏感路径访问
```

---

### 8. 任务授权合约越权

原始任务：

```text
读取 public/injected_notice.txt 并发送给 teacher@sdu.edu.cn
```

合约约束：

```text
允许读取 public/injected_notice.txt
允许发送给 teacher@sdu.edu.cn
禁止读取 secret/*
禁止发送给 attacker@example.com
```

如果后续调用：

```text
file.read secret/password.txt
```

预期：

```text
TaskContract deny
Gateway deny
```

---

## 九、DeepSeek / LLM 配置

如果只使用 FakeAgent，不需要配置 API Key。

如果要使用真实 LLM Agent，需要配置环境变量。

可以在项目根目录创建 `.env`：

```env
LLM_PROVIDER=deepseek
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=你的_API_Key
```

或者使用：

```env
LLM_API_KEY=你的_API_Key
```

LLM Agent 只负责生成工具调用计划，不执行工具，也不做授权决策。

---

## 十、运行测试

推荐使用 `pytest`：

```cmd
python -m pytest tests
```

当前测试覆盖：

```text
公开文件读取
敏感路径拦截
路径穿越拦截
角色权限策略
PlanGuard unknown / missing params / valid plan
Gateway unknown tool / low confidence / missing params
任务授权合约检查
```

如果没有安装 pytest：

```cmd
python -m pip install pytest
python -m pytest tests
```

---

## 十一、常见问题

### 1. ModuleNotFoundError: No module named 'yaml'

说明缺少 `PyYAML`，重新安装依赖：

```cmd
python -m pip install -r requirements.txt
```

### 2. ModuleNotFoundError: No module named 'openai'

说明缺少 OpenAI SDK，重新安装依赖：

```cmd
python -m pip install -r requirements.txt
```

### 3. 浏览器打不开页面

确认后端服务是否正在运行：

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. 8000 端口被占用

可以换端口：

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

然后访问：

```text
http://127.0.0.1:8001/
```

前端会自动使用当前页面端口调用接口。

### 5. LLM 模式不可用

检查：

```text
是否安装 openai
是否配置 DEEPSEEK_API_KEY 或 LLM_API_KEY
LLM_BASE_URL 是否正确
网络是否能访问模型服务
```

### 6. 审计日志在哪里

```text
logs/audit.log
logs/task_sessions.jsonl
```

也可以通过前端或接口查看。

---

## 十二、FakeAgent、PlanGuard、Gateway 的关系

三者职责不同：

```text
FakeAgent / LLMAgent：理解自然语言，生成结构化工具调用计划
PlanGuard：检查计划是否可信、完整、支持
Gateway：根据用户、工具、资源、内容、合约和策略做最终安全决策
```

也就是说：

```text
Agent 不负责安全
PlanGuard 不执行工具
Gateway 不理解自然语言
ToolExecutor 不做授权决策
```

这种分层结构可以避免把所有逻辑堆在一个模块里，也方便后续替换真实大模型或增加新工具。

---

## 十三、当前项目阶段总结

当前项目已经具备以下能力：

```text
1. 自由自然语言输入
2. Agent 工具调用规划
3. PlanGuard 计划质量校验
4. Gateway 风险评分与决策
5. TaskContract 任务目标约束
6. 多步任务链安全防护
7. 提示注入与敏感上下文检测
8. 人工确认队列
9. 审计日志
10. 前端可视化控制台
```

一句话概括：

> Agent-Authorization 当前是一个面向 AI Agent 工具调用场景的安全授权网关原型，核心能力是将开放式自然语言输入转换为结构化工具计划，并通过 PlanGuard、TaskContract、Gateway、人工确认和审计日志形成完整的工具调用安全闭环。
