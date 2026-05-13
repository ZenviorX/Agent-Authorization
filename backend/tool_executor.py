from pathlib import Path

from backend.utils import normalize_tool_name, normalize_params, get_path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def execute_tool(tool: str, params: dict):
    """
    工具执行入口。
    这里只执行被网关 allow 或人工确认后的工具调用。
    """
    tool = normalize_tool_name(tool)
    params = normalize_params(tool, params)

    if tool == "file.read":
        return read_file(params)

    if tool == "email.send":
        return send_email(params)

    if tool == "file.delete":
        return delete_file(params)

    if tool == "shell.run":
        return run_shell(params)

    if tool == "db.query":
        return query_db(params)

    if tool == "file.write":
        return write_file(params)

    return {
        "success": False,
        "result": f"未知工具：{tool}"
    }


def _safe_data_path(path: str):
    """
    将用户传入路径限制在 data/ 目录内。
    防止路径穿越：
    ../../Windows/System32
    ../secret/password.txt
    C:\\Users\\xxx\\.env
    """
    if not path:
        return None, "文件路径为空"

    raw_path = Path(path)

    if raw_path.is_absolute():
        return None, "非法路径：禁止使用绝对路径"

    base_dir = DATA_DIR.resolve()
    target_path = (DATA_DIR / path).resolve()

    try:
        target_path.relative_to(base_dir)
    except ValueError:
        return None, "非法路径：禁止访问 data 目录之外的文件"

    return target_path, None


def read_file(params: dict):
    path = get_path(params)
    file_path, error = _safe_data_path(path)

    if error:
        return {
            "success": False,
            "result": error
        }

    if not file_path.exists():
        return {
            "success": False,
            "result": "文件不存在"
        }

    if not file_path.is_file():
        return {
            "success": False,
            "result": "目标不是普通文件"
        }

    content = file_path.read_text(encoding="utf-8")

    return {
        "success": True,
        "result": content
    }


def send_email(params: dict):
    to = params.get("to", "")
    subject = params.get("subject", "模拟智能体邮件")
    content = params.get("content", "")

    return {
        "success": True,
        "result": {
            "message": "模拟发送邮件成功",
            "to": to,
            "subject": subject,
            "content": content
        }
    }


def delete_file(params: dict):
    """
    比赛原型阶段不真实删除文件，只模拟。
    真实项目中，即使人工确认，也应进行更严格的二次校验。
    """
    path = get_path(params)

    return {
        "success": True,
        "result": f"模拟删除文件：{path}。注意：原型系统未真实删除文件。"
    }


def run_shell(params: dict):
    """
    比赛原型阶段不真实执行系统命令，只模拟。
    """
    command = params.get("command", "")

    return {
        "success": True,
        "result": f"模拟执行系统命令：{command}。注意：原型系统未真实执行命令。"
    }


def query_db(params: dict):
    sql = params.get("sql", "")

    return {
        "success": True,
        "result": f"模拟执行数据库查询：{sql}"
    }


def write_file(params: dict):
    """
    原型阶段只模拟写文件，不真实写入。
    """
    path = get_path(params)
    content = params.get("content", "")

    return {
        "success": True,
        "result": {
            "message": "模拟写入文件成功，原型系统未真实写入",
            "path": path,
            "content": content
        }
    }