from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = "8000"
FRONTEND_PORT = "5173"


def is_windows() -> bool:
    return os.name == "nt"


def venv_python() -> str:
    if is_windows():
        candidate = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    else:
        candidate = PROJECT_ROOT / "venv" / "bin" / "python"

    if candidate.exists():
        return str(candidate)

    return sys.executable


def run_shell(command: str, cwd: Path | None = None) -> None:
    print(f"[run] {command}")
    subprocess.run(command, cwd=str(cwd or PROJECT_ROOT), shell=True, check=False)


def kill_existing_processes() -> None:
    """
    Stop common local backend/frontend dev processes.

    This is intentionally conservative:
    - backend: uvicorn / backend.main / start_project.py
    - frontend: node processes containing vite / frontend / npm
    """

    if is_windows():
        ps = r'''
Get-CimInstance Win32_Process |
  Where-Object {
    (
      $_.Name -match "node.exe" -and (
        $_.CommandLine -match "vite" -or
        $_.CommandLine -match "frontend" -or
        $_.CommandLine -match "npm"
      )
    ) -or (
      ($_.Name -match "python.exe" -or $_.Name -match "pythonw.exe") -and (
        $_.CommandLine -match "uvicorn" -or
        $_.CommandLine -match "backend.main" -or
        $_.CommandLine -match "start_project.py"
      )
    )
  } |
  ForEach-Object {
    Write-Host "Stop process PID=$($_.ProcessId) $($_.CommandLine)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }
'''
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=False,
        )
        return

    # macOS / Linux fallback
    patterns = [
        "uvicorn backend.main:app",
        "python -m uvicorn backend.main:app",
        "npm --prefix ./frontend run dev",
        "vite",
    ]

    for pattern in patterns:
        subprocess.run(["pkill", "-f", pattern], check=False)


def ensure_frontend_env() -> None:
    """
    Keep frontend API routing stable.

    vite.config.ts already proxies /test-results to 127.0.0.1:8000.
    This .env file makes direct API_BASE explicit as a fallback.
    """

    env_file = FRONTEND_DIR / ".env"
    desired = "VITE_API_BASE=http://127.0.0.1:8000\n"

    if env_file.exists():
        old = env_file.read_text(encoding="utf-8", errors="ignore")
        if "VITE_API_BASE=" in old:
            return

        env_file.write_text(old.rstrip() + "\n" + desired, encoding="utf-8")
        return

    env_file.write_text(desired, encoding="utf-8")


def start_backend() -> subprocess.Popen:
    python = venv_python()
    command = [
        python,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--reload",
        "--host",
        BACKEND_HOST,
        "--port",
        BACKEND_PORT,
    ]

    print("[backend] " + " ".join(command))
    return subprocess.Popen(command, cwd=str(PROJECT_ROOT))


def start_frontend() -> subprocess.Popen:
    command = ["npm", "--prefix", str(FRONTEND_DIR), "run", "dev"]

    print("[frontend] " + " ".join(command))
    return subprocess.Popen(command, cwd=str(PROJECT_ROOT), shell=is_windows())


def wait_message() -> None:
    print()
    print("=" * 72)
    print("Agent-Authorization started")
    print("=" * 72)
    print(f"Backend:  http://{BACKEND_HOST}:{BACKEND_PORT}")
    print(f"Frontend: http://localhost:{FRONTEND_PORT}")
    print(f"API Docs: http://{BACKEND_HOST}:{BACKEND_PORT}/docs")
    print()
    print("Useful checks:")
    print(f"  http://{BACKEND_HOST}:{BACKEND_PORT}/test-results/latest/summary")
    print("  Frontend -> 评测对比 -> 一键运行测试")
    print()
    print("Press Ctrl+C to stop both backend and frontend.")
    print("=" * 72)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Start Agent-Authorization backend and frontend.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Stop existing frontend/backend dev processes before starting.",
    )
    parser.add_argument(
        "--no-env",
        action="store_true",
        help="Do not write frontend/.env fallback VITE_API_BASE.",
    )

    args = parser.parse_args()

    if args.clean:
        kill_existing_processes()
        time.sleep(1)

    if not args.no_env:
        ensure_frontend_env()

    backend = start_backend()
    time.sleep(2)
    frontend = start_frontend()

    wait_message()

    children = [backend, frontend]

    try:
        while True:
            for proc in children:
                if proc.poll() is not None:
                    print(f"[exit] child process exited with code {proc.returncode}")
                    return int(proc.returncode or 0)

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[stop] stopping backend and frontend...")

        for proc in children:
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

        time.sleep(1)

        for proc in children:
            if proc.poll() is None:
                try:
                    if is_windows():
                        proc.kill()
                    else:
                        os.kill(proc.pid, signal.SIGKILL)
                except Exception:
                    pass

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
