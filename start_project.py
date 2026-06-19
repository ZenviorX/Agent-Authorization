# -*- coding: utf-8 -*-
"""
Agent-Authorization unified startup script.

Backend:  FastAPI / Uvicorn -> http://127.0.0.1:8000
Frontend: React + Vite      -> http://127.0.0.1:5173

This script checks Node.js/npm before starting backend, so a missing npm
will not start and then immediately stop the backend.
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


def fix_console_encoding() -> None:
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if os.name == "nt":
        os.system("chcp 65001 > nul")
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
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


def print_header() -> None:
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
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def detect_venv() -> tuple[Path, Path]:
    for venv_dir in [PREFERRED_VENV_DIR, FALLBACK_VENV_DIR]:
        python_path = get_venv_python(venv_dir)
        if python_path.exists():
            return venv_dir, python_path
    return PREFERRED_VENV_DIR, get_venv_python(PREFERRED_VENV_DIR)


def run_command(command: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    print("> " + " ".join(map(str, command)))
    result = subprocess.run(command, cwd=cwd, shell=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(map(str, command))}")
    return result


def ensure_venv(skip_install: bool = False) -> tuple[Path, Path]:
    venv_dir, venv_python = detect_venv()
    if not venv_python.exists():
        print(f"[INFO] Python virtual environment not found. Creating: {venv_dir}")
        run_command([sys.executable, "-m", "venv", str(venv_dir)], cwd=PROJECT_ROOT, check=True)
        venv_dir, venv_python = detect_venv()
    print(f"[OK] Python virtual environment found: {venv_dir}")

    if skip_install:
        print("[SKIP] Backend dependency check skipped.")
        return venv_dir, venv_python

    print("[INFO] Checking backend dependencies...")
    check_code = "import fastapi\nimport uvicorn\nimport pydantic\nimport yaml\n"
    result = subprocess.run(
        [str(venv_python), "-c", check_code],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )
    if result.returncode == 0:
        print("[OK] Backend dependencies already installed.")
        return venv_dir, venv_python
    if not REQUIREMENTS.exists():
        raise FileNotFoundError("requirements.txt not found.")
    print("[INFO] Installing backend dependencies from requirements.txt ...")
    run_command([str(venv_python), "-m", "pip", "install", "-r", str(REQUIREMENTS)], cwd=PROJECT_ROOT, check=True)
    return venv_dir, venv_python


def get_npm_command() -> str:
    npm = shutil.which("npm.cmd") or shutil.which("npm") if os.name == "nt" else shutil.which("npm")
    if not npm:
        raise FileNotFoundError(
            "未检测到 npm。请先安装 Node.js LTS，然后重新打开终端。\n"
            "Windows 可执行：winget install -e --id OpenJS.NodeJS.LTS\n"
            "安装后检查：node -v && npm -v"
        )
    return npm


def ensure_frontend_dependencies(skip_install: bool = False) -> None:
    if not FRONTEND_DIR.exists():
        raise FileNotFoundError(f"frontend directory not found: {FRONTEND_DIR}")
    if not (FRONTEND_DIR / "package.json").exists():
        raise FileNotFoundError(f"frontend/package.json not found: {FRONTEND_DIR / 'package.json'}")
    npm = get_npm_command()
    print(f"[OK] npm found: {npm}")
    if skip_install:
        print("[SKIP] Frontend dependency check skipped.")
        return
    vite_bin = FRONTEND_DIR / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
    if vite_bin.exists():
        print("[OK] Frontend dependencies already installed.")
        return
    print("[INFO] Installing frontend dependencies...")
    print("[INFO] Using npm mirror: https://registry.npmmirror.com")
    run_command([npm, "config", "set", "registry", "https://registry.npmmirror.com"], cwd=FRONTEND_DIR, check=False)
    run_command([npm, "install", "--registry=https://registry.npmmirror.com"], cwd=FRONTEND_DIR, check=True)


def write_frontend_env() -> None:
    env_path = FRONTEND_DIR / ".env"
    env_path.write_text("VITE_API_BASE=\nVITE_API_PROXY_TARGET=http://127.0.0.1:8000\n", encoding="utf-8", newline="\n")
    print("[OK] frontend/.env ready.")


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def request_url(url: str, timeout: int = 2) -> tuple[int | None, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return None, str(exc)


def wait_for_service(name: str, urls: list[str], timeout_seconds: int = 40) -> bool:
    print(f"[INFO] Waiting for {name} ...")
    start = time.time()
    while time.time() - start < timeout_seconds:
        for url in urls:
            status, _ = request_url(url, timeout=2)
            if status is not None and 200 <= status < 500:
                print(f"[OK] {name} is ready: {url}")
                return True
        time.sleep(0.5)
    print(f"[WARN] {name} startup timeout.")
    return False


def create_process(command: list[str], cwd: Path) -> subprocess.Popen:
    print("> " + " ".join(map(str, command)))
    print()
    if os.name == "nt":
        return subprocess.Popen(command, cwd=cwd, shell=False, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return subprocess.Popen(command, cwd=cwd, shell=False)


def start_backend(venv_python: Path) -> subprocess.Popen | None:
    if is_port_open(BACKEND_HOST, BACKEND_PORT):
        print(f"[INFO] Backend port already in use: {BACKEND_BASE_URL}")
        return None
    command = [str(venv_python), "-m", "uvicorn", "backend.main:app", "--reload", "--host", BACKEND_HOST, "--port", str(BACKEND_PORT)]
    print("[INFO] Starting backend service...")
    return create_process(command, PROJECT_ROOT)


def start_frontend() -> subprocess.Popen | None:
    if is_port_open(FRONTEND_HOST, FRONTEND_PORT):
        print(f"[INFO] Frontend port already in use: {FRONTEND_BASE_URL}")
        return None
    npm = get_npm_command()
    command = [npm, "run", "dev", "--", "--host", FRONTEND_HOST, "--port", str(FRONTEND_PORT)]
    print("[INFO] Starting frontend service...")
    return create_process(command, FRONTEND_DIR)


def stop_process(name: str, process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    print(f"[INFO] Stopping {name} ...")
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.terminate()
    except Exception:
        process.terminate()
    try:
        process.wait(timeout=6)
    except subprocess.TimeoutExpired:
        process.kill()
    print(f"[OK] {name} stopped.")


def print_links() -> None:
    print()
    print("=" * 72)
    print("Project URLs")
    print("=" * 72)
    print(f"Frontend workbench : {FRONTEND_BASE_URL}")
    print(f"Backend API docs   : {BACKEND_BASE_URL}/docs")
    print(f"Backend status     : {BACKEND_BASE_URL}/api/status")
    print("=" * 72)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Agent-Authorization backend and frontend.")
    parser.add_argument("--backend-only", action="store_true", help="Start backend only.")
    parser.add_argument("--frontend-only", action="store_true", help="Start frontend only.")
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically.")
    parser.add_argument("--skip-install", action="store_true", help="Skip dependency installation checks.")
    args = parser.parse_args()
    if args.backend_only and args.frontend_only:
        raise ValueError("Cannot use --backend-only and --frontend-only together.")

    print_header()
    os.chdir(PROJECT_ROOT)
    should_backend = not args.frontend_only
    should_frontend = not args.backend_only
    backend_process = None
    frontend_process = None

    try:
        if should_frontend:
            write_frontend_env()
            ensure_frontend_dependencies(skip_install=args.skip_install)
        venv_python = None
        if should_backend:
            _, venv_python = ensure_venv(skip_install=args.skip_install)
        if should_backend:
            backend_process = start_backend(venv_python)
            wait_for_service("backend", [f"{BACKEND_BASE_URL}/api/status", f"{BACKEND_BASE_URL}/openapi.json", f"{BACKEND_BASE_URL}/docs"], timeout_seconds=40)
        if should_frontend:
            frontend_process = start_frontend()
            wait_for_service("frontend", [f"{FRONTEND_BASE_URL}/api/status", FRONTEND_BASE_URL], timeout_seconds=40)
        print_links()
        if should_frontend and not args.no_open:
            print(f"[INFO] Opening browser: {FRONTEND_BASE_URL}")
            webbrowser.open(FRONTEND_BASE_URL)
        print("\n" + "=" * 72)
        print("Project started.")
        print("Keep this terminal open.")
        print("Press Ctrl + C to stop services started by this script.")
        print("=" * 72 + "\n")
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
        print("\n[INFO] Ctrl + C received.")
    finally:
        stop_process("frontend", frontend_process)
        stop_process("backend", backend_process)


if __name__ == "__main__":
    main()
