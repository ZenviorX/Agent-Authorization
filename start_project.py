import os
import sys
import time
import socket
import signal
import subprocess
import webbrowser
import urllib.request
from pathlib import Path


# ------------------------------------------------------------
# Fix Windows terminal encoding
# ------------------------------------------------------------
def fix_console_encoding():
    """
    Try to force UTF-8 output on Windows terminal.
    Also keep output mostly English to avoid mojibake.
    """

    if os.name == "nt":
        os.system("chcp 65001 > nul")

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    except Exception:
        pass


fix_console_encoding()


PROJECT_ROOT = Path(__file__).resolve().parent

HOST = "127.0.0.1"
PORT = 8000

BASE_URL = f"http://{HOST}:{PORT}"

SHOWCASE_URL = f"{BASE_URL}/showcase"
FRONTEND_URL = f"{BASE_URL}/"
BENCHMARK_DASHBOARD_URL = f"{BASE_URL}/benchmark-dashboard"
ATTACK_CHAIN_RUNTIME_URL = f"{BASE_URL}/attack-chain-runtime"
DOCS_URL = f"{BASE_URL}/docs"
STATUS_URL = f"{BASE_URL}/api/status"

AUTHORIZED_EVIDENCE_URL = f"{BASE_URL}/authorized-evidence"
SANDBOX_DASHBOARD_URL = f"{BASE_URL}/sandbox-dashboard"
TASK_CHAIN_URL = f"{BASE_URL}/task-chain"
SECURITY_DASHBOARD_URL = f"{BASE_URL}/security-dashboard"

SANDBOX_STATUS_URL = f"{BASE_URL}/runtime/sandbox/status"
EVIDENCE_LIST_URL = f"{BASE_URL}/sandbox-evidence/list"
SHOWCASE_REPORT_LIST_URL = f"{BASE_URL}/showcase-report/list"
BENCHMARK_LATEST_URL = f"{BASE_URL}/benchmark/latest"
SECURITY_OVERVIEW_URL = f"{BASE_URL}/security/overview"
AUDIT_VERIFY_URL = f"{BASE_URL}/audit/verify"

DISPLAY_PAGES = [
    ("1. 系统总览", SHOWCASE_URL),
    ("2. 单步授权", FRONTEND_URL),
    ("3. 任务链", TASK_CHAIN_URL),
    ("4. 评测中心", BENCHMARK_DASHBOARD_URL),
    ("5. 安全中心", SECURITY_DASHBOARD_URL),
]

EMBEDDED_MODULES = [
    ("工具接入检测", f"{BASE_URL}/tool-proxy", "已合并到单步授权页选项卡"),
    ("攻击链检测", ATTACK_CHAIN_RUNTIME_URL, "已合并到任务链页选项卡"),
    ("授权证据", AUTHORIZED_EVIDENCE_URL, "已合并到单步授权页和任务链页选项卡"),
    ("API docs", DOCS_URL, "开发调试入口，不作为汇报主导航"),
]

DEFAULT_VENV_DIR = PROJECT_ROOT / ".venv"
LEGACY_VENV_DIR = PROJECT_ROOT / "venv"

REQUIREMENTS = PROJECT_ROOT / "requirements.txt"

FALLBACK_PACKAGES = [
    "fastapi",
    "uvicorn",
    "pydantic",
    "pyyaml",
    "httpx",
]


def get_venv_python_path(venv_dir):
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"

    return venv_dir / "bin" / "python"


def detect_venv():
    """
    Prefer existing .venv.
    Also support old venv directory for compatibility.
    """

    candidates = [
        DEFAULT_VENV_DIR,
        LEGACY_VENV_DIR,
    ]

    for venv_dir in candidates:
        python_path = get_venv_python_path(venv_dir)

        if python_path.exists():
            return venv_dir, python_path

    return DEFAULT_VENV_DIR, get_venv_python_path(DEFAULT_VENV_DIR)


VENV_DIR, VENV_PYTHON = detect_venv()


def print_header():
    print("=" * 72)
    print("AgentGuard / Agent-Authorization Startup Script")
    print("=" * 72)
    print(f"Project root          : {PROJECT_ROOT}")
    print(f"Virtual environment   : {VENV_DIR}")
    print("Default open page     : 系统总览 /showcase")
    print("-" * 72)
    for label, url in DISPLAY_PAGES:
        print(f"{label:<22}: {url}")
    print("=" * 72)
    print()


def run_command(command, cwd=None):
    print("> " + " ".join(map(str, command)))

    return subprocess.run(
        command,
        cwd=cwd,
        shell=False,
    )


def create_venv_if_needed():
    global VENV_DIR
    global VENV_PYTHON

    VENV_DIR, VENV_PYTHON = detect_venv()

    if VENV_PYTHON.exists():
        print("[1/5] Virtual environment found.")
        print(f"      {VENV_DIR}")
        return

    print("[1/5] Virtual environment not found. Creating .venv ...")

    result = run_command(
        [
            sys.executable,
            "-m",
            "venv",
            str(DEFAULT_VENV_DIR),
        ],
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        raise RuntimeError("Failed to create virtual environment.")

    VENV_DIR = DEFAULT_VENV_DIR
    VENV_PYTHON = get_venv_python_path(VENV_DIR)

    print("Virtual environment created.")
    print(f"      {VENV_DIR}")


def install_requirements_if_needed():
    print("[2/5] Checking Python dependencies...")

    check_code = (
        "import fastapi\n"
        "import uvicorn\n"
        "import pydantic\n"
        "import yaml\n"
    )

    result = subprocess.run(
        [
            str(VENV_PYTHON),
            "-c",
            check_code,
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )

    if result.returncode == 0:
        print("Dependencies OK.")
        return

    if REQUIREMENTS.exists():
        print("Dependencies missing. Installing requirements.txt ...")

        result = run_command(
            [
                str(VENV_PYTHON),
                "-m",
                "pip",
                "install",
                "-r",
                str(REQUIREMENTS),
            ],
            cwd=PROJECT_ROOT,
        )

    else:
        print("requirements.txt not found.")
        print("Installing fallback dependencies...")

        result = run_command(
            [
                str(VENV_PYTHON),
                "-m",
                "pip",
                "install",
                *FALLBACK_PACKAGES,
            ],
            cwd=PROJECT_ROOT,
        )

    if result.returncode != 0:
        raise RuntimeError("Failed to install dependencies.")

    print("Dependencies installed.")


def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)

        return sock.connect_ex((host, port)) == 0


def request_url(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")

    except Exception as exc:
        return None, str(exc)


def is_backend_ready():
    status, _ = request_url(STATUS_URL, timeout=1)

    return status is not None and 200 <= status < 500


def wait_for_backend(timeout_seconds=30):
    print("[3/5] Waiting for backend service...")

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        if is_backend_ready():
            print("Backend is ready.")
            return True

        time.sleep(0.5)

    print("Backend startup timeout. It may still be starting.")
    return False


def initialize_runtime_environment():
    """
    Preload the current showcase route and runtime endpoints.
    """

    print("[4/5] Initializing runtime workspace...")

    endpoints = [
        ("API status", STATUS_URL),
        ("Benchmark latest", BENCHMARK_LATEST_URL),
        ("Sandbox status", SANDBOX_STATUS_URL),
        ("Evidence list", EVIDENCE_LIST_URL),
        ("Security overview", SECURITY_OVERVIEW_URL),
        ("Audit verify", AUDIT_VERIFY_URL),
        ("Showcase report list", SHOWCASE_REPORT_LIST_URL),
    ]

    for name, url in endpoints:
        status, body = request_url(url, timeout=3)

        if status is not None and 200 <= status < 300:
            print(f"OK   {name}: {url}")

        elif name == "Benchmark latest" and status == 404:
            print(f"INFO {name}: no generated benchmark result yet.")
            print("     The frontend will fall back to packaged evidence when available.")

        elif status is not None and 300 <= status < 500:
            print(f"INFO {name}: {url} returned HTTP {status}")

        else:
            print(f"WARN {name}: {url}")
            print(f"     {body}")

    print("Runtime workspace check finished.")


def open_pages():
    print("[5/5] Opening browser page...")

    print(f"Open showcase overview: {SHOWCASE_URL}")
    webbrowser.open(SHOWCASE_URL)


def print_project_links():
    print()
    print("=" * 72)
    print("Frontend route map")
    print("=" * 72)
    for label, url in DISPLAY_PAGES:
        print(f"{label:<22}: {url}")
    print("-" * 72)
    print(f"API status            : {STATUS_URL}")
    print("=" * 72)
    print()


def print_existing_backend_warning():
    print()
    print("WARNING: Backend is already running on this port.")
    print("The startup script will not replace an existing backend process.")
    print()
    print("If you changed code today but the old backend is still running,")
    print("the browser may still show old frontend pages or old API results.")
    print()
    print("Recommended fix:")
    print("1. Close the old terminal window running uvicorn/start_project.py")
    print("2. Or press Ctrl + C in that terminal")
    print("3. Run this startup script again")
    print("4. Press Ctrl + F5 in the browser")
    print()


def start_backend():
    print("Starting backend service...")

    command = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "backend.main:app",
        "--reload",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]

    print("> " + " ".join(command))
    print()

    if os.name == "nt":
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    else:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            shell=False,
        )

    return process


def stop_backend(process):
    print()
    print("Stopping backend service...")

    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)

        else:
            process.terminate()

    except Exception:
        process.terminate()

    try:
        process.wait(timeout=5)

    except subprocess.TimeoutExpired:
        process.kill()

    print("Backend stopped.")


def main():
    print_header()

    os.chdir(PROJECT_ROOT)

    create_venv_if_needed()
    install_requirements_if_needed()

    if is_backend_ready():
        print_existing_backend_warning()
        print(f"Backend already running: {BASE_URL}")

        initialize_runtime_environment()
        open_pages()
        print_project_links()

        print("No new backend process started.")
        return

    if is_port_open(HOST, PORT):
        print(f"Port {PORT} is already in use.")
        print("Please close the program using this port, or change PORT in this script.")
        return

    backend_process = start_backend()

    try:
        wait_for_backend()
        initialize_runtime_environment()
        open_pages()
        print_project_links()

        print()
        print("=" * 72)
        print("Project started.")
        print("Do not close this terminal window.")
        print("Press Ctrl + C to stop backend service.")
        print("=" * 72)
        print()

        backend_process.wait()

    except KeyboardInterrupt:
        stop_backend(backend_process)


if __name__ == "__main__":
    main()
