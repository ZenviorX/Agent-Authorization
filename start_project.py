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
FRONTEND_URL = f"{BASE_URL}/"
DOCS_URL = f"{BASE_URL}/docs"
STATUS_URL = f"{BASE_URL}/api/status"

VENV_DIR = PROJECT_ROOT / "venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"


def print_header():
    print("=" * 60)
    print("Agent-Authorization Startup Script")
    print("=" * 60)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Frontend     : {FRONTEND_URL}")
    print(f"API docs     : {DOCS_URL}")
    print("=" * 60)
    print()


def run_command(command, cwd=None):
    print("> " + " ".join(map(str, command)))
    return subprocess.run(command, cwd=cwd, shell=False)


def create_venv_if_needed():
    if VENV_PYTHON.exists():
        print("[1/4] venv found.")
        return

    print("[1/4] venv not found. Creating virtual environment...")
    result = run_command([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=PROJECT_ROOT)

    if result.returncode != 0:
        raise RuntimeError("Failed to create virtual environment.")

    print("venv created.")


def install_requirements_if_needed():
    print("[2/4] Checking Python dependencies...")

    check_code = "import fastapi, uvicorn, pydantic, yaml"
    result = subprocess.run(
        [str(VENV_PYTHON), "-c", check_code],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )

    if result.returncode == 0:
        print("Dependencies OK.")
        return

    if not REQUIREMENTS.exists():
        raise FileNotFoundError("requirements.txt not found.")

    print("Dependencies missing. Installing requirements.txt ...")
    result = run_command(
        [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        raise RuntimeError("Failed to install dependencies.")

    print("Dependencies installed.")


def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def is_backend_ready():
    try:
        with urllib.request.urlopen(STATUS_URL, timeout=1) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def wait_for_backend(timeout_seconds=30):
    print("[3/4] Waiting for backend service...")

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        if is_backend_ready():
            print("Backend is ready.")
            return True

        time.sleep(0.5)

    print("Backend startup timeout. It may still be starting.")
    return False


def open_pages():
    print("[4/4] Opening browser pages...")

    print(f"Open frontend: {FRONTEND_URL}")
    webbrowser.open(FRONTEND_URL)

    time.sleep(0.5)

    print(f"Open API docs: {DOCS_URL}")
    webbrowser.open(DOCS_URL)


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
        print(f"Backend already running: {BASE_URL}")
        open_pages()
        print()
        print("No new backend process started.")
        return

    if is_port_open(HOST, PORT):
        print(f"Port {PORT} is already in use.")
        print("Please close the program using this port, or change PORT in this script.")
        return

    backend_process = start_backend()

    try:
        wait_for_backend()
        open_pages()

        print()
        print("=" * 60)
        print("Project started.")
        print("Do not close this terminal window.")
        print("Press Ctrl + C to stop backend service.")
        print("=" * 60)
        print()

        backend_process.wait()

    except KeyboardInterrupt:
        stop_backend(backend_process)


if __name__ == "__main__":
    main()