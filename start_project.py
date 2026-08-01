from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173
OAUTH_HOST = "127.0.0.1"
OAUTH_PORT = 9000
MANAGED_PORTS = (BACKEND_PORT, FRONTEND_PORT, OAUTH_PORT)


def is_windows() -> bool:
    return os.name == "nt"


def venv_python() -> str:
    candidates = (
        PROJECT_ROOT / "venv" / ("Scripts/python.exe" if is_windows() else "bin/python"),
        PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if is_windows() else "bin/python"),
    )

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    return sys.executable


def _process_creation_kwargs() -> dict[str, object]:
    if is_windows():
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def _listening_pids_windows(ports: tuple[int, ...]) -> set[int]:
    port_list = ",".join(str(port) for port in ports)
    command = rf'''
$ports = @({port_list})
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object {{ $ports -contains [int]$_.LocalPort }} |
  Select-Object -ExpandProperty OwningProcess -Unique
'''
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
    )
    return {int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()}


def _listening_pids_posix(ports: tuple[int, ...]) -> set[int]:
    pids: set[int] = set()
    for port in ports:
        result = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
            check=False,
        )
        pids.update(int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit())
    return pids


def _project_process_pids_windows() -> set[int]:
    env = os.environ.copy()
    env["AGENTGUARD_PROJECT_ROOT"] = str(PROJECT_ROOT)
    command = r'''
$root = $env:AGENTGUARD_PROJECT_ROOT
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and
    $_.CommandLine.Contains($root) -and
    (
      (
        $_.Name -match "python.exe|pythonw.exe" -and
        $_.CommandLine -match "uvicorn|backend.main|backend.oauth.demo_authorization_server|start_project.py"
      ) -or (
        $_.Name -match "node.exe|npm.exe|cmd.exe" -and
        $_.CommandLine -match "vite|npm|frontend"
      )
    )
  } |
  Select-Object -ExpandProperty ProcessId -Unique
'''
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return {int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()}


def _project_process_pids_posix() -> set[int]:
    result = subprocess.run(
        ["pgrep", "-f", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    return {int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()}


def _describe_process(pid: int) -> str:
    if is_windows():
        command = (
            f"Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" | "
            "Select-Object -ExpandProperty CommandLine"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout.strip() or f"PID {pid}"

    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or f"PID {pid}"


def _kill_process_tree(pid: int) -> None:
    if pid <= 0:
        return

    if is_windows():
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    try:
        os.killpg(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            return


def kill_existing_processes() -> None:
    """Stop old AgentGuard processes and anything listening on managed ports."""

    current_pid = os.getpid()
    parent_pid = os.getppid()

    if is_windows():
        pids = _listening_pids_windows(MANAGED_PORTS)
        pids.update(_project_process_pids_windows())
    else:
        pids = _listening_pids_posix(MANAGED_PORTS)
        pids.update(_project_process_pids_posix())

    pids.discard(current_pid)
    pids.discard(parent_pid)

    if not pids:
        print("[cleanup] no previous AgentGuard process found")
        return

    print(f"[cleanup] stopping {len(pids)} previous process(es)...")
    for pid in sorted(pids):
        print(f"[cleanup] PID={pid} {_describe_process(pid)}")
        _kill_process_tree(pid)

    time.sleep(1.2)


def _port_is_free(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if is_windows() and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def wait_for_ports_free(timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        busy = [port for port in MANAGED_PORTS if not _port_is_free("127.0.0.1", port)]
        if not busy:
            print("[cleanup] ports 8000, 5173 and 9000 are free")
            return True
        time.sleep(0.25)

    busy = [port for port in MANAGED_PORTS if not _port_is_free("127.0.0.1", port)]
    print(f"[cleanup] unable to release port(s): {', '.join(map(str, busy))}")
    return False


def ensure_frontend_env() -> None:
    """Force the frontend to use the local backend launched by this script."""

    env_file = FRONTEND_DIR / ".env"
    desired_line = f"VITE_API_BASE=http://{BACKEND_HOST}:{BACKEND_PORT}"
    existing_lines: list[str] = []

    if env_file.exists():
        existing_lines = env_file.read_text(encoding="utf-8", errors="ignore").splitlines()

    output: list[str] = []
    replaced = False

    for line in existing_lines:
        if line.strip().startswith("VITE_API_BASE="):
            if not replaced:
                output.append(desired_line)
                replaced = True
            continue
        output.append(line)

    if not replaced:
        output.append(desired_line)

    env_file.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def check_backend_dependencies() -> bool:
    python = venv_python()
    result = subprocess.run(
        [
            python,
            "-c",
            "import fastapi, uvicorn, pydantic, yaml, jwt, cryptography; print('backend dependencies ok')",
        ],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode == 0:
        print(f"[deps] {result.stdout.strip()}")
        return True

    print("[deps] backend dependencies are incomplete")
    if result.stderr.strip():
        print(result.stderr.strip())
    print(f'[deps] run: "{python}" -m pip install -r requirements.txt')
    return False


def start_backend(*, reload_enabled: bool) -> subprocess.Popen:
    python = venv_python()
    command = [
        python,
        "-m",
        "uvicorn",
        "backend.main:app",
        "--host",
        BACKEND_HOST,
        "--port",
        str(BACKEND_PORT),
    ]
    if reload_enabled:
        command.append("--reload")

    print("[backend] " + " ".join(command))
    return subprocess.Popen(command, cwd=str(PROJECT_ROOT), **_process_creation_kwargs())


def start_oauth_server(*, reload_enabled: bool) -> subprocess.Popen:
    python = venv_python()
    command = [
        python,
        "-m",
        "uvicorn",
        "backend.oauth.demo_authorization_server:app",
        "--host",
        OAUTH_HOST,
        "--port",
        str(OAUTH_PORT),
    ]
    if reload_enabled:
        command.append("--reload")

    print("[oauth-demo] " + " ".join(command))
    return subprocess.Popen(command, cwd=str(PROJECT_ROOT), **_process_creation_kwargs())


def start_frontend() -> subprocess.Popen:
    command = ["npm", "--prefix", str(FRONTEND_DIR), "run", "dev"]
    print("[frontend] " + " ".join(command))
    return subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        shell=is_windows(),
        **_process_creation_kwargs(),
    )


def wait_for_http(
    url: str,
    *,
    process: subprocess.Popen | None = None,
    timeout_seconds: float = 25.0,
) -> bool:
    """Wait until a local endpoint responds, or stop early if its process exits."""

    deadline = time.monotonic() + timeout_seconds
    request = Request(url, headers={"User-Agent": "AgentGuard-Launcher/2.0"})

    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            print(
                f"[startup] process exited before {url} became ready "
                f"(code={process.returncode})"
            )
            return False

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


def stop_children(children: list[subprocess.Popen]) -> None:
    for proc in reversed(children):
        if proc.poll() is None:
            _kill_process_tree(proc.pid)

    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        if all(proc.poll() is not None for proc in children):
            return
        time.sleep(0.2)

    for proc in reversed(children):
        if proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass


def _state(ready: bool) -> str:
    return "[OK]" if ready else "[FAIL]"


def wait_message(
    *,
    with_oauth: bool,
    backend_ready: bool,
    frontend_ready: bool,
    oauth_ready: bool,
) -> None:
    backend_base = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
    frontend_url = f"http://{FRONTEND_HOST}:{FRONTEND_PORT}"
    oauth_base = f"http://{OAUTH_HOST}:{OAUTH_PORT}"

    print()
    print("=" * 78)
    print("AgentGuard startup result")
    print("=" * 78)
    print("Browser pages:")
    print(f"  {_state(frontend_ready)} Frontend:           {frontend_url}")
    print(f"  {_state(backend_ready)} API documentation:  {backend_base}/docs")
    print(f"  {_state(backend_ready)} Backend status:      {backend_base}/api/status")
    if with_oauth:
        print(f"  {_state(oauth_ready)} OAuth demo console:  {oauth_base}/")
    print()
    print("Protocol endpoints:")
    print(f"  MCP JSON-RPC endpoint:  POST {backend_base}/mcp")
    if with_oauth:
        print(f"  OAuth token endpoint:   POST {oauth_base}/token")
    print()
    print("Press Ctrl+C to stop all child processes.")
    print("=" * 78)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Restart AgentGuard backend, frontend and optional OAuth server."
    )

    clean_group = parser.add_mutually_exclusive_group()
    clean_group.add_argument(
        "--clean",
        action="store_true",
        help="Explicitly request cleanup. Cleanup is already enabled by default.",
    )
    clean_group.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not stop existing processes or release managed ports before startup.",
    )
    parser.add_argument(
        "--no-env",
        action="store_true",
        help="Do not update frontend/.env VITE_API_BASE.",
    )
    parser.add_argument(
        "--with-oauth",
        action="store_true",
        help="Also start the localhost OAuth Authorization Server on port 9000.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable Uvicorn auto-reload. Disabled by default to avoid orphan processes.",
    )

    args = parser.parse_args()

    if not args.no_clean:
        kill_existing_processes()
        if not wait_for_ports_free():
            return 2

    if not args.no_env:
        ensure_frontend_env()

    if not check_backend_dependencies():
        return 2

    children: list[subprocess.Popen] = []

    try:
        oauth_ready = False
        if args.with_oauth:
            oauth_process = start_oauth_server(reload_enabled=args.reload)
            children.append(oauth_process)
            oauth_ready = wait_for_http(
                f"http://{OAUTH_HOST}:{OAUTH_PORT}/health",
                process=oauth_process,
                timeout_seconds=20,
            )
            if not oauth_ready:
                print("[startup] OAuth server failed to start; stopping all services")
                return 1

        backend_process = start_backend(reload_enabled=args.reload)
        children.append(backend_process)
        backend_ready = wait_for_http(
            f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/status",
            process=backend_process,
            timeout_seconds=30,
        )
        if not backend_ready:
            print("[startup] backend failed to start; frontend will not be launched")
            return 1

        frontend_process = start_frontend()
        children.append(frontend_process)
        frontend_ready = wait_for_http(
            f"http://{FRONTEND_HOST}:{FRONTEND_PORT}",
            process=frontend_process,
            timeout_seconds=30,
        )
        if not frontend_ready:
            print("[startup] frontend failed to start")
            return 1

        wait_message(
            with_oauth=args.with_oauth,
            backend_ready=backend_ready,
            frontend_ready=frontend_ready,
            oauth_ready=oauth_ready,
        )

        while True:
            for proc in children:
                if proc.poll() is not None:
                    print(
                        f"[exit] child process PID={proc.pid} "
                        f"exited with code {proc.returncode}"
                    )
                    return int(proc.returncode or 1)
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[stop] stopping child processes...")
        return 0

    finally:
        stop_children(children)


if __name__ == "__main__":
    raise SystemExit(main())
