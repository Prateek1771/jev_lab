"""Run Jev Lab's UIs with one command, and stop them all with Ctrl+C.

Usage: uv run python scripts/dev.py [--ui both|web|streamlit]     (default: both)

  web        the Next.js UI on :3737, plus the API it needs on :8000
  streamlit  the original Streamlit app on :8501
  both       all three; the nav toggle ("New UI | Streamlit") switches between them on the same project
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable   # the venv that runs this script (uv run), so uvicorn/streamlit are importable


def commands(ui: str) -> list[tuple[str, list[str], Path, str]]:
    api = ("api", [PY, "-m", "uvicorn", "api.main:app", "--port", "8000"], ROOT, "http://localhost:8000/api/projects")
    npm = shutil.which("npm") or "npm"
    web = ("web", [npm, "run", "dev"], ROOT / "web", "http://localhost:3737")
    streamlit = ("streamlit", [PY, "-m", "streamlit", "run", "app.py", "--server.port", "8501", "--server.headless", "true"],
                 ROOT, "http://localhost:8501")
    return {"web": [api, web], "streamlit": [streamlit], "both": [api, web, streamlit]}[ui]


def stop(p: subprocess.Popen) -> None:
    """The whole tree: on Windows `npm run dev` is npm.cmd → node, and terminate() would orphan node on :3737."""
    if p.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
    else:
        p.terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ui", choices=["both", "web", "streamlit"], default="both")
    ui = parser.parse_args().ui
    if ui != "streamlit" and not (ROOT / "web" / "node_modules").exists():
        sys.exit("web/node_modules is missing: run `npm install` in web/ once first.")
    procs = []
    try:
        for name, cmd, cwd, url in commands(ui):
            procs.append((name, subprocess.Popen(cmd, cwd=cwd)))
            print(f"  {name:<10} {url}")
        print("Ctrl+C stops everything.")
        while all(p.poll() is None for _, p in procs):
            time.sleep(0.5)
        dead = next(name for name, p in procs if p.poll() is not None)
        print(f"{dead} exited; stopping the rest.")
    except KeyboardInterrupt:
        pass
    finally:
        for _, p in procs:
            stop(p)
        for _, p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
