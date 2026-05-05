from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"


def main() -> int:
    processes: list[subprocess.Popen[str]] = []
    try:
        backend = _start_process(
            [
                "poetry",
                "run",
                "uvicorn",
                "services.api.app:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            cwd=ROOT,
        )
        processes.append(backend)

        frontend = _start_process(
            ["npm.cmd" if sys.platform == "win32" else "npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
            cwd=FRONTEND_DIR,
        )
        processes.append(frontend)

        print()
        print("Random Garden dev servers are starting.")
        print(f"Backend:  {BACKEND_URL}")
        print(f"API docs: {BACKEND_URL}/docs")
        print(f"Frontend: {FRONTEND_URL}")
        print()
        print("Press Ctrl+C to stop both servers.")

        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"Process exited with code {return_code}. Stopping remaining servers.")
                    return return_code
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping Random Garden dev servers...")
        return 0
    finally:
        _stop_processes(processes)


def _start_process(command: list[str], *, cwd: Path) -> subprocess.Popen[str]:
    kwargs: dict[str, object] = {"cwd": cwd, "text": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(command, **kwargs)


def _stop_processes(processes: list[subprocess.Popen[str]]) -> None:
    for process in processes:
        if process.poll() is None:
            _terminate_process(process)
    for process in processes:
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def _terminate_process(process: subprocess.Popen[str]) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        import os

        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


if __name__ == "__main__":
    raise SystemExit(main())
