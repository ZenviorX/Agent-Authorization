import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


# ============================================================
# Agent-Authorization unified startup script
# Backend : FastAPI / Uvicorn  -> http://127.0.0.1:8000
# Frontend: Vite / React       -> http://127.0.0.1:5173
# ============================================================


def fix_console_encoding():
    if os.name == "nt":
        os.system("chcp 65001 > nul")

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


fix_console_encoding()


PROJECT_ROOT = Path(__file__).resolve().parent

BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
BACKEND_BASE_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173
FRONTEND_BASE_URL = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"

FRONTEND_DIR = PROJECT_ROOT / "frontend"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"

PREFERRED_VENV_DIR = PROJECT_ROOT / "venv"
FALLBACK_VENV_DIR = PROJECT_ROOT / ".venv"

BACKEND_READY_ENDPOINTS = [
    f"{BACKEND_BASE_URL}/api/status",
    f"{BACKEND_BASE_URL}/docs",
    f"{BACKEND_BASE_URL}/openapi.json",
]

FRONTEND_READY_ENDPOINTS = [
    FRONTEND_BASE_URL,
]


def print_header():
    print("=" * 72)
    print("Agent-Authorization Startup")
    print("=" * 72)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Backend      : {BACKEND_BASE_URL}")
    print(f"Frontend     : {FRONTEND_BASE_URL}")
    print(f"API docs     : {BACKEND_BASE_URL}/docs")
    print("=" * 72)
    print()


def get_venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def detect_venv():
    candidates = [
        PREFERRED_VENV_DIR,
        FALLBACK_VENV_DIR,
    ]

    for venv_dir in candidates:
        python_path = get_venv_python(venv_dir)
        if python_path.exists():
            return venv_dir, python_path

    return PREFERRED_VENV_DIR, get_venv_python(PREFERRED_VENV_DIR)


VENV_DIR, VENV_PYTHON = detect_venv()


def run_command(command, cwd=None, check=False):
    print("> " + " ".join(map(str, command)))
    result = subprocess.run(command, cwd=cwd, shell=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(map(str, command))}")
    return result


def create_venv_if_needed():
    global VENV_DIR, VENV_PYTHON

    VENV_DIR, VENV_PYTHON = detect_venv()

    if VENV_PYTHON.exists():
        print(f"[OK] Python virtual environment found: {VENV_DIR}")
        return

    print(f"[INFO] Python virtual environment not found. Creating: {PREFERRED_VENV_DIR}")

    run_command(
        [sys.executable, "-m", "venv", str(PREFERRED_VENV_DIR)],
        cwd=PROJECT_ROOT,
        check=True,
    )

    VENV_DIR = PREFERRED_VENV_DIR
    VENV_PYTHON = get_venv_python(VENV_DIR)

    print(f"[OK] Virtual environment created: {VENV_DIR}")


def install_backend_dependencies_if_needed(skip_install=False):
    if skip_install:
        print("[SKIP] Backend dependency check skipped.")
        return

    print("[INFO] Checking backend dependencies...")

    check_code = (
        "import fastapi\n"
        "import uvicorn\n"
        "import pydantic\n"
        "import yaml\n"
    )

    result = subprocess.run(
        [str(VENV_PYTHON), "-c", check_code],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )

    if result.returncode == 0:
        print("[OK] Backend dependencies already installed.")
        return

    if not REQUIREMENTS.exists():
        raise FileNotFoundError("requirements.txt not found. Cannot install backend dependencies.")

    print("[INFO] Installing backend dependencies from requirements.txt ...")

    run_command(
        [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=PROJECT_ROOT,
        check=True,
    )

    print("[OK] Backend dependencies installed.")


def get_npm_command():
    return "npm.cmd" if os.name == "nt" else "npm"


def frontend_package_json_exists():
    return (FRONTEND_DIR / "package.json").exists()


def frontend_node_modules_ready():
    node_modules = FRONTEND_DIR / "node_modules"

    if os.name == "nt":
        vite_bin = FRONTEND_DIR / "node_modules" / ".bin" / "vite.cmd"
    else:
        vite_bin = FRONTEND_DIR / "node_modules" / ".bin" / "vite"

    return node_modules.exists() and vite_bin.exists()


def install_frontend_dependencies_if_needed(skip_install=False):
    if skip_install:
        print("[SKIP] Frontend dependency check skipped.")
        return

    if not FRONTEND_DIR.exists():
        raise FileNotFoundError(f"frontend directory not found: {FRONTEND_DIR}")

    if not frontend_package_json_exists():
        raise FileNotFoundError(f"frontend/package.json not found: {FRONTEND_DIR / 'package.json'}")

    if frontend_node_modules_ready():
        print("[OK] Frontend dependencies already installed.")
        return

    npm = get_npm_command()

    print("[INFO] Installing frontend dependencies...")
    print("[INFO] Using npm mirror: https://registry.npmmirror.com")

    run_command(
        [npm, "config", "set", "registry", "https://registry.npmmirror.com"],
        cwd=FRONTEND_DIR,
        check=False,
    )

    run_command(
        [npm, "install", "--registry=https://registry.npmmirror.com"],
        cwd=FRONTEND_DIR,
        check=True,
    )

    print("[OK] Frontend dependencies installed.")


def is_port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def request_url(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            return response.status, text
    except Exception as exc:
        return None, str(exc)


def wait_for_service(name, urls, timeout_seconds=40):
    print(f"[INFO] Waiting for {name} ...")

    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        for url in urls:
            status, _ = request_url(url, timeout=2)

            if status is not None and 200 <= status < 500:
                print(f"[OK] {name} is ready: {url}")
                return True

        time.sleep(0.5)

    print(f"[WARN] {name} startup timeout.")
    return False


def create_process(command, cwd):
    print("> " + " ".join(map(str, command)))
    print()

    if os.name == "nt":
        return subprocess.Popen(
            command,
            cwd=cwd,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    return subprocess.Popen(
        command,
        cwd=cwd,
        shell=False,
    )


def start_backend():
    command = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "backend.main:app",
        "--reload",
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
    ]

    print("[INFO] Starting backend service...")
    return create_process(command, PROJECT_ROOT)


def start_frontend():
    npm = get_npm_command()

    command = [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        FRONTEND_HOST,
        "--port",
        str(FRONTEND_PORT),
    ]

    print("[INFO] Starting frontend service...")
    return create_process(command, FRONTEND_DIR)


def stop_process(name, process):
    if process is None:
        return

    if process.poll() is not None:
        return

    print(f"[INFO] Stopping {name} ...")

    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
    except Exception:
        try:
            process.terminate()
        except Exception:
            pass

    try:
        process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        process.kill()

    print(f"[OK] {name} stopped.")


def print_links():
    print()
    print("=" * 72)
    print("Project URLs")
    print("=" * 72)
    print(f"Frontend workbench : {FRONTEND_BASE_URL}")
    print(f"Backend API docs   : {BACKEND_BASE_URL}/docs")
    print(f"Backend base       : {BACKEND_BASE_URL}")
    print("=" * 72)
    print()


def main():
    parser = argparse.ArgumentParser(description="Start Agent-Authorization backend and frontend.")
    parser.add_argument("--backend-only", action="store_true", help="Start backend only.")
    parser.add_argument("--frontend-only", action="store_true", help="Start frontend only.")
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically.")
    parser.add_argument("--skip-install", action="store_true", help="Skip dependency installation checks.")
    args = parser.parse_args()

    if args.backend_only and args.frontend_only:
        raise ValueError("Cannot use --backend-only and --frontend-only at the same time.")

    print_header()

    os.chdir(PROJECT_ROOT)

    backend_process = None
    frontend_process = None

    should_start_backend = not args.frontend_only
    should_start_frontend = not args.backend_only

    try:
        if should_start_backend:
            create_venv_if_needed()
            install_backend_dependencies_if_needed(skip_install=args.skip_install)

            if is_port_open(BACKEND_HOST, BACKEND_PORT):
                print(f"[INFO] Backend port already in use: {BACKEND_BASE_URL}")
                wait_for_service("backend", BACKEND_READY_ENDPOINTS, timeout_seconds=5)
            else:
                backend_process = start_backend()
                wait_for_service("backend", BACKEND_READY_ENDPOINTS, timeout_seconds=40)

        if should_start_frontend:
            install_frontend_dependencies_if_needed(skip_install=args.skip_install)

            if is_port_open(FRONTEND_HOST, FRONTEND_PORT):
                print(f"[INFO] Frontend port already in use: {FRONTEND_BASE_URL}")
                wait_for_service("frontend", FRONTEND_READY_ENDPOINTS, timeout_seconds=5)
            else:
                frontend_process = start_frontend()
                wait_for_service("frontend", FRONTEND_READY_ENDPOINTS, timeout_seconds=40)

        print_links()

        if should_start_frontend and not args.no_open:
            print(f"[INFO] Opening browser: {FRONTEND_BASE_URL}")
            webbrowser.open(FRONTEND_BASE_URL)

        print()
        print("=" * 72)
        print("Project started.")
        print("Keep this terminal open.")
        print("Press Ctrl + C to stop services started by this script.")
        print("=" * 72)
        print()

        if backend_process is None and frontend_process is None:
            print("[INFO] No new process was started. Existing services are being used.")
            return

        while True:
            time.sleep(1)

            if backend_process is not None and backend_process.poll() is not None:
                print("[WARN] Backend process exited.")
                break

            if frontend_process is not None and frontend_process.poll() is not None:
                print("[WARN] Frontend process exited.")
                break

    except KeyboardInterrupt:
        print()
        print("[INFO] Ctrl + C received.")

    finally:
        stop_process("frontend", frontend_process)
        stop_process("backend", backend_process)


if __name__ == "__main__":
    main()
