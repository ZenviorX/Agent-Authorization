# ZenviorX AI Agent Authorization Gateway Frontend

一个不依赖原前端的新版本前端，使用 React + Vite + TypeScript 实现。

## 这版新增重点

这版已经把核心入口改成 **网关工作台**，不再只是指标看板。你可以在页面中输入自然语言用户命令，然后选择：

- FakeAgent 规划 + Gateway 只判定：推荐演示入口，不执行工具。
- FakeAgent 只规划：只看自然语言到 ToolCallPlan 的转换。
- FakeAgent 完整演示链路：经过 Gateway，allow 时会调用演示工具。
- LLM 多步规划：调用 MultiStepLLMAgent 规划，不执行。
- LLM 一次规划并运行：规划完整链路后通过 Runtime Monitor 执行。
- LLM 逐步规划 + 运行时拦截：适合展示提示注入链路和动态拦截。

## 对接的后端接口

前端已经按当前仓库后端接口接好：

```text
POST /demo/fake-agent/plan
POST /demo/fake-agent/run
POST /gateway/check
POST /agent-runtime/multistep-llm/plan
POST /agent-runtime/multistep-llm/run
POST /agent-runtime/stepwise-llm/run
GET  /api/status
```

其中默认推荐模式是：

```text
/demo/fake-agent/plan -> /gateway/check
```

这样可以展示“自然语言命令 -> FakeAgent 工具规划 -> Gateway 是否允许”的完整判断链路，同时不会真的执行工具。

## 安装运行

在项目根目录中把这个文件夹改名为 `frontend` 后执行：

```powershell
cd "D:\文档\15信安赛项目\仓库\Agent-Authorization\frontend"

npm config set registry https://registry.npmmirror.com
npm install --registry=https://registry.npmmirror.com
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

## 后端启动

在项目根目录启动后端，例如：

```powershell
cd "D:\文档\15信安赛项目\仓库\Agent-Authorization"
.\venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

前端默认会把这些路径代理到后端：

```text
/api
/demo
/gateway
/agent
/agent-runtime
/approval
/audit
/runtime
/security-overview
/benchmark-dashboard
/tool-proxy
```

## 环境变量

复制环境变量模板：

```powershell
Copy-Item .env.example .env
```

一般保持这样即可：

```env
VITE_API_BASE=
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

如果你不想使用 Vite 代理，也可以直接写完整后端地址：

```env
VITE_API_BASE=http://127.0.0.1:8000
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

## 推荐演示输入

```text
读取文件 public/notice.txt
读取文件 secret/password.txt
删除文件 public/notice.txt
给 internal@example.com 发邮件，内容是 public notice
执行命令 command=dir
请读取 public/injected_notice.txt 并总结内容
```

## 打包

```powershell
npm run build
npm run preview
```

## 注意

- 包内不包含 `node_modules`。
- 包内不包含 `package-lock.json`，避免锁定到无法访问的内部 npm 源。
- 后端未启动时，工作台会显示 Mock fallback，但会明确提示是前端模拟结果。
