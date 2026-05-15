# Agent-Authorization

# Agent Authorization



面向 AI 智能体工具调用的授权与安全防护系统。



本项目实现了一个轻量级授权网关，用于在智能体执行工具调用之前进行安全检查。系统会根据用户身份、工具类型、参数内容和资源路径进行风险评分，并给出自动放行、自动拦截或人工确认的决策。



## 一、项目功能



当前版本已经实现：



1\. 模拟智能体根据用户输入生成工具调用请求；

2\. 授权网关对工具调用进行风险评分；

3\. 根据风险结果返回 allow、deny 或 confirm；

4\. 对可疑操作进入人工确认队列；

5\. 对所有工具调用行为记录审计日志；

6\. 提供前端页面展示调用结果、待确认任务和审计日志。



## 二、运行环境

建议使用：

- Python 3.10 及以上
- Windows cmd
- FastAPI
- Uvicorn

项目依赖写在 `requirements.txt` 中，主要包括：

```text
fastapi
uvicorn
pydantic
PyYAML
```



## 三、详细运行方式

下面命令均在 Windows cmd 中执行。

### 1. 进入项目根目录

根据自己的实际路径进入仓库，例如：

```cmd
cd /d D:\文档\15信安赛项目\仓库\Agent-Authorization
```

进入后可以确认目录中包含：

```text
backend/
config/
data/
frontend/
requirements.txt
README.md
```

### 2. 创建虚拟环境

如果项目根目录下还没有 `venv/`，先创建虚拟环境：

```cmd
python -m venv venv
```

如果已经存在 `venv/`，可以跳过这一步。

### 3. 激活虚拟环境

```cmd
venv\Scripts\activate.bat
```

激活成功后，命令行前面通常会出现：

```text
(venv)
```

如果不想激活虚拟环境，也可以直接使用虚拟环境中的 Python：

```cmd
venv\Scripts\python.exe --version
```

### 4. 安装项目依赖

```cmd
python -m pip install -r requirements.txt
```

安装完成后，可以检查关键依赖是否存在：

```cmd
python -m pip show fastapi uvicorn pydantic PyYAML
```

### 5. 启动后端服务

在项目根目录执行：

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

看到类似输出即表示启动成功：

```text
Uvicorn running on http://127.0.0.1:8000
```

注意：启动服务的 cmd 窗口需要保持打开。若关闭该窗口，后端服务也会停止。

### 6. 访问前端演示页面

浏览器打开：

```text
http://127.0.0.1:8000/
```

该地址会直接进入前端演示页面，可以在页面中体验：

```text
1. 一键演示场景
2. 自然语言任务输入
3. 网关风险判断结果
4. 人工确认队列
5. 审计日志
6. 提示注入攻击链演示
```

### 7. 访问后端状态接口

浏览器打开：

```text
http://127.0.0.1:8000/api/status
```

正常情况下会返回后端运行状态 JSON。

### 8. 访问接口文档

浏览器打开：

```text
http://127.0.0.1:8000/docs
```

这里可以直接测试后端接口，例如：

```text
POST /agent/simulate
GET  /approval/pending
POST /approval/confirm/{pending_id}
POST /approval/reject/{pending_id}
GET  /audit/logs
```

### 9. 端口被占用时的处理方式

如果 `8000` 端口已经被占用，可以换一个端口启动，例如：

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

然后访问：

```text
http://127.0.0.1:8001/
http://127.0.0.1:8001/api/status
http://127.0.0.1:8001/docs
```

如果使用后端托管的前端页面，前端会自动使用当前页面的端口调用接口。



## 四、推荐演示流程

启动后端并打开前端页面后，建议按下面顺序演示：

### 1. 正常文件读取

选择或输入：

```text
用户：alice
任务：读取文件：public/notice.txt
```

预期结果：

```text
decision: allow
executed: true
```

### 2. 敏感文件拦截

选择或输入：

```text
用户：student
任务：读取文件：secret/password.txt
```

预期结果：

```text
decision: deny
executed: false
```

### 3. 邮件发送人工确认

选择或输入：

```text
用户：alice
任务：给张三发邮件，内容是明天下午三点开会
```

预期结果：

```text
decision: confirm
pending_id: 生成一个待确认编号
```

随后在“人工确认队列”中点击确认或拒绝。

### 4. 路径穿越攻击拦截

选择或输入：

```text
用户：alice
任务：读取文件：../../secret/password.txt
```

预期结果：

```text
decision: deny
reason: 路径中包含 ..，可能存在路径穿越风险
```

### 5. 提示注入攻击链演示

点击前端页面中的“提示注入攻击链演示”。

预期流程：

```text
1. Agent 正常读取 public/injected_notice.txt
2. 系统检测其中的提示注入关键词
3. 模拟 Agent 被诱导读取 secret/password.txt
4. 网关再次检查危险工具调用
5. 敏感路径访问被 deny
```



## 五、运行测试

安装依赖后，可在项目根目录执行：

```cmd
python -m unittest discover -s tests
```

测试覆盖：

```text
1. 公开文件读取 allow
2. 敏感文件读取 deny
3. 教师删除文件进入 confirm
4. 路径穿越 hard deny
5. 管理员高风险 shell 调用进入 confirm
```

如果测试通过，会看到类似输出：

```text
Ran 5 tests in ...

OK
```



## 六、常见问题

### 1. ModuleNotFoundError: No module named 'yaml'

说明当前环境缺少 `PyYAML`，请确认已经激活虚拟环境，并重新安装依赖：

```cmd
venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

### 2. 浏览器打不开 http://127.0.0.1:8000/

请检查后端服务是否还在运行。如果启动窗口已经关闭，需要重新执行：

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 3. 8000 端口被占用

可以改用 8001：

```cmd
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8001
```

然后访问：

```text
http://127.0.0.1:8001/
```

### 4. 审计日志在哪里

审计日志默认写入：

```text
logs/audit.log
```

也可以通过接口查看：

```text
http://127.0.0.1:8000/audit/logs
```




