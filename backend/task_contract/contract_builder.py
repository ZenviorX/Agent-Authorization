import re
import uuid
from backend.task_contract.contract_models import TaskAuthContract


def extract_email(text: str) -> list[str]:
    """
    从用户任务中提取邮箱地址。
    """
    pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    return re.findall(pattern, text)


def extract_file_path(text: str) -> list[str]:
    """
    从用户任务中简单提取文件路径。

    当前只是原型版本，先支持：
    - public/xxx.txt
    - data/xxx.txt
    - logs/xxx.txt
    """
    pattern = r"(public/[a-zA-Z0-9_.\-/]+|data/[a-zA-Z0-9_.\-/]+|logs/[a-zA-Z0-9_.\-/]+)"
    return re.findall(pattern, text)


def build_task_contract(user: str, task_text: str) -> TaskAuthContract:
    """
    根据用户原始任务生成任务授权合约。

    第一版先不接入大模型，只用规则提取。
    这样更稳定，也更适合比赛演示。
    """

    task_id = str(uuid.uuid4())

    emails = extract_email(task_text)
    file_paths = extract_file_path(task_text)

    allowed_tools = []
    reason = []

    # 如果任务里出现了文件路径，就允许 file.read
    if file_paths:
        allowed_tools.append("file.read")
        reason.append("用户任务中明确指定了需要读取的文件路径，因此允许 file.read。")

    # 如果任务里出现了邮箱，就允许 email.send
    if emails:
        allowed_tools.append("email.send")
        reason.append("用户任务中明确指定了邮件收件人，因此允许 email.send。")

    # 如果既没有文件，也没有邮箱，先认为是普通任务
    if not allowed_tools:
        reason.append("用户任务中没有明确出现文件路径或邮箱地址，因此暂不授予高风险工具权限。")

    contract = TaskAuthContract(
        task_id=task_id,
        user=user,
        original_task=task_text,
        task_goal="根据用户原始任务生成的受限执行目标",
        allowed_tools=allowed_tools,
        denied_tools=[
            "shell.run",
            "code.exec",
            "db.query"
        ],
        allowed_read_paths=file_paths,
        denied_paths=[
            "secret/*",
            "private/*",
            "../*"
        ],
        allowed_email_to=emails,
        allow_external_send=False,
        risk_budget=80,
        require_human_confirm=False,
        reason=reason
    )

    return contract