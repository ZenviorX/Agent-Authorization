# AgentGuard 前端说明

这是 Agent-Authorization 项目的提交版前端，使用 React + Vite + TypeScript 实现。

前端目标是：**简洁展示 AI Agent 工具调用授权链路**，而不是做复杂后台系统。

---

## 页面结构

提交版只保留 4 个主入口：

| 页面 | 作用 |
|---|---|
| 授权演示 | 输入任务，查看 Gateway 判定和沙箱证据 |
| 运行证据 | 查看请求、审计、整体链路说明 |
| 测试报告 | 一键运行独立测试模块，查看通过率和风险指标 |
| 项目说明 | 说明 NoGuard、OAuth-only、AgentGuard 的区别 |

推荐展示顺序：

```text
授权演示 → 运行证据 → 测试报告 → 项目说明
```

---

## 授权演示模式

授权演示页只保留 3 个常用模式：

| 模式 | 说明 |
|---|---|
| 普通授权判定 | 只判断 allow / confirm / deny，不执行工具 |
| 真沙箱执行 | 通过 Capability Token 后进入 Docker / Native 沙箱执行 |
| 外部 Agent 授权 | 展示 OAuth-style scope 检查和外部 Agent 接入 |

---

## 启动方式

推荐从项目根目录启动：

```powershell
python .\start_project.py --clean
```

或单独启动前端：

```powershell
npm --prefix ".\frontend" install
npm --prefix ".\frontend" run dev
```

浏览器访问：

```text
http://localhost:5173
```

---

## 后端代理

前端默认通过 Vite proxy 调用后端：

```text
http://127.0.0.1:8000
```

主要接口包括：

```text
/tool-proxy/authorize
/gateway/check
/sandbox-native/*
/sandbox-docker/*
/test-results/*
/external-agent/*
```

---

## 构建

```powershell
npm --prefix ".\frontend" run build
```
