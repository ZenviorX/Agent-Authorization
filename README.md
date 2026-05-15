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



\- Python 3.10 及以上

\- Windows PowerShell

\- FastAPI

\- Uvicorn



## 三、安装依赖



进入项目根目录：



```powershell

cd D:\\信安赛\\agent-authorization\\Agent-Authorization

```



激活虚拟环境：



```PowerShell

.\\venv\\Scripts\\Activate.ps1

```

安装依赖：



```PowerShell

pip install -r requirements.txt

```



在项目根目录下运行：



```PowerShell

python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

```



启动成功后，可以访问：



http://127.0.0.1:8000/

该地址会直接打开前端演示页面。

后端状态接口：

http://127.0.0.1:8000/api/status



接口文档页面：



http://127.0.0.1:8000/docs



## 四、运行测试

安装依赖后，可在项目根目录执行：

```PowerShell

python -m unittest discover -s tests

```

测试覆盖公开文件读取、敏感文件拦截、人工确认、路径穿越硬拒绝和管理员高风险操作确认等核心网关策略。




