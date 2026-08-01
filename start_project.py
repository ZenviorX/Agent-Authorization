from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = "8000"
FRONTEND_PORT = "5173"
OAUTH_HOST = "127.0.0.1"
OAUTH_PORT = "9000"


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
    """Stop old local backend/frontend/OAuth demo processes without killing this launcher."""

    current_pid = os.getpid()
    parent_pid = os.getppid()

    if is_windows():
        ps = rf'''
$currentPid = {current_pid}
$parentPid = {parent_pid}

Get-CimInstance Win32_Process |
  Where-Object {{
    $_.ProcessId -ne $currentPid -and
    $_.ProcessId -ne $parentPid -and
    (
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
          $_.CommandLine -match "backend.oauth.demo_authorization_server" -or
          $_.CommandLine -match "start_project.py"
        )
      )
    )
  }} |
  ForEach-Object {{
    Write-Host "Stop process PID=$($_.ProcessId) $($_.CommandLine)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }}
'''
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            check=False,
        )
        return

    patterns = [
        "uvicorn backend.main:app",
        "python -m uvicorn backend.main:app",
        "uvicorn backend.oauth.demo_authorization_server:app",
        "python -m uvicorn backend.oauth.demo_authorization_server:app",
        "npm --prefix ./frontend run dev",
        "vite --host",
    ]

    for pattern in patterns:
        subprocess.run(["pkill", "-f", pattern], check=False)


def ensure_frontend_env() -> None:
    """Keep frontend API routing stable."""

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


def start_oauth_server() -> subprocess.Popen:
    python = venv_python()
    command = [
        python,
        "-m",
        "uvicorn",
        "backend.oauth.demo_authorization_server:app",
        "--reload",
        "--host",
        OAUTH_HOST,
        "--port",
        OAUTH_PORT,
    ]

    print("[oauth-demo] " + " ".join(command))
    return subprocess.Popen(command, cwd=str(PROJECT_ROOT))


def start_frontend() -> subprocess.Popen:
    command = ["npm", "--prefix", str(FRONTEND_DIR), "run", "dev"]

    print("[frontend] " + " ".join(command))
    return subprocess.Popen(command, cwd=str(PROJECT_ROOT), shell=is_windows())


def wait_for_http(url: str, timeout_seconds: float = 20.0) -> bool:
    """Wait until a local HTTP endpoint responds with a non-5xx status."""

    deadline = time.monotonic() + timeout_seconds
    request = Request(url, headers={"User-Agent": "AgentGuard-Launcher/1.0"})

    while time.monotonic() < deadline:
        try:
            with urlopen(request, timeout=1.5) as response:
                return int(getattr(response, "status", 200)) < 500
        except HTTPError as exc:
            if int(exc.code) < 500:
                return True
        except (URLError, TimeoutError, OSError):
            pass

        time.sleep(0.4)

    return False


def _state(ready: bool) -> str:
    return "[OK]" if ready else "[WAIT]"


def wait_message(
    *,
    with_oauth: bool,
    backend_ready: bool,
    frontend_ready: bool,
    oauth_ready: bool,
) -> None:
    backend_base = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
    frontend_url = f"http://localhost:{FRONTEND_PORT}"
    oauth_base = f"http://{OAUTH_HOST}:{OAUTH_PORT}"

    print()
    print("=" * 78)
    print("AgentGuard started")
    print("=" * 78)

    print("Browser pages (safe to Ctrl+Click):")
    print(f"  {_state(frontend_ready)} Frontend:           {frontend_url}")
    print(f"  {_state(backend_ready)} API documentation:  {backend_base}/docs")
    print(f"  {_state(backend_ready)} MCP gateway info:   {backend_base}/mcp")
    if with_oauth:
        print(f"  {_state(oauth_ready)} OAuth demo console:  {oauth_base}/")

    print()
    print("Protocol endpoints (called by clients; not normal web pages):")
    print(f"  Backend API base:       {backend_base}")
    print(f"  MCP JSON-RPC endpoint:  POST {backend_base}/mcp")
    if with_oauth:
        print(f"  OAuth token endpoint:   POST {oauth_base}/token")

    print()
    print("Machine-readable metadata and health:")
    print(f"  Backend status:         {backend_base}/api/status")
    print(f"  MCP status:             {backend_base}/mcp/status")
    print(f"  OAuth resource metadata:{backend_base}/.well-known/oauth-protected-resource")
    print(f"  Native sandbox health:  {backend_base}/sandbox-native/health")
    if with_oauth:
        print(f"  OAuth server health:    {oauth_base}/health")
        print(f"  OAuth server metadata:  {oauth_base}/.well-known/oauth-authorization-server")

    print()
    print("Optional generated result (available after running tests):")
    print(f"  {backend_base}/test-results/latest/summary")

    if with_oauth:
        print()
        print("Run the real OAuth + MCP client flow in another terminal:")
        print("  python examples/mcp_oauth_demo_client.py")

    print()
    print("Frontend demo paths:")
    print("  Frontend -> 授权工作台 -> 真沙箱执行（自动选择）")
    print("  Frontend -> 测试报告 -> 一键运行测试")
    print()
    print("[OK] means the launcher received an HTTP response.")
    print("[WAIT] means the process may still be starting; inspect its terminal output.")
    print("Press Ctrl+C to stop all child processes.")
    print("=" * 78)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Start AgentGuard backend and frontend.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Stop existing frontend/backend/OAuth demo processes before starting.",
    )
    parser.add_argument(
        "--no-env",
        action="store_true",
        help="Do not write frontend/.env fallback VITE_API_BASE.",
    )
    parser.add_argument(
        "--with-oauth",
        action="store_true",
        help="Also start the localhost-only demo OAuth Authorization Server on port 9000.",
    )

    args = parser.parse_args()

    if args.clean:
        kill_existing_processes()
        time.sleep(1)

    if not args.no_env:
        ensure_frontend_env()

    children: list[subprocess.Popen] = []

    if args.with_oauth:
        children.append(start_oauth_server())
        time.sleep(0.6)

    children.append(start_backend())
    time.sleep(0.8)
    children.append(start_frontend())

    backend_ready = wait_for_http(
        f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/status",
        timeout_seconds=20,
    )
    frontend_ready = wait_for_http(
        f"http://localhost:{FRONTEND_PORT}",
        timeout_seconds=20,
    )
    oauth_ready = (
        wait_for_http(
            f"http://{OAUTH_HOST}:{OAUTH_PORT}/health",
            timeout_seconds=20,
        )
        if args.with_oauth
        else False
    )

    wait_message(
        with_oauth=args.with_oauth,
        backend_ready=backend_ready,
        frontend_ready=frontend_ready,
        oauth_ready=oauth_ready,
    )

    try:
        while True:
            for proc in children:
                if proc.poll() is not None:
                    print(f"[exit] child process exited with code {proc.returncode}")
                    return int(proc.returncode or 0)

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[stop] stopping child processes...")

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