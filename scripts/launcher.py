"""Double-clickable launcher for the dubbing control panel.

Deliberately starts nothing heavy itself: it locates the project's validated .venv and
runs the panel from it. Bundling torch/CUDA/Chatterbox into the executable would produce
a multi-gigabyte binary that drifts out of sync with the environment the pipeline needs.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

PORT = 8765
HOST = "127.0.0.1"
OLLAMA = "http://127.0.0.1:11434/api/version"


def _say(msg: str = "", color: str | None = None) -> None:
    codes = {"ok": "92", "warn": "93", "err": "91", "info": "96"}
    if color and codes.get(color) and sys.stdout.isatty():
        print(f"\033[{codes[color]}m{msg}\033[0m", flush=True)
    else:
        print(msg, flush=True)


class LauncherError(Exception):
    """Something the user has to fix, reported without a Python traceback."""


def _pause() -> None:
    """Keep a double-clicked window open, but never block a redirected run."""
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            input("\nPulsa Enter para cerrar...")
    except (EOFError, OSError):
        pass


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def find_project() -> tuple[Path, Path]:
    """Locate the project root and its venv interpreter, starting next to the exe."""
    start = _base_dir()
    for root in (start, *start.parents):
        python = root / ".venv" / "Scripts" / "python.exe"
        if python.exists() and (root / "src" / "ytdubber").is_dir():
            return root, python
    raise LauncherError(
        "No encuentro el proyecto.\n"
        f"Busque un .venv a partir de: {start}\n"
        "Deja este .exe dentro de la carpeta youtube-dubber-win, o ejecuta antes "
        ".\\scripts\\setup_windows.ps1"
    )


def port_busy(port: int = PORT) -> bool:
    with socket.socket() as s:
        s.settimeout(0.6)
        return s.connect_ex((HOST, port)) == 0


def panel_alive() -> bool:
    """A real API response, not a bare TCP connect: another process may hold the port."""
    return url_alive(f"http://{HOST}:{PORT}/api/job", 1.5)


def stop_tree(proc: subprocess.Popen) -> None:
    """Kill the whole tree.

    On Windows the venv's python.exe is a redirector that runs the base interpreter as a
    child, so terminating our direct child leaves the actual server alive and still
    holding the port.
    """
    if proc.poll() is not None:
        return
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def url_alive(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def ensure_ollama() -> None:
    if url_alive(OLLAMA):
        _say("[OK] Ollama en marcha.", "ok")
        return
    _say("[..] Ollama no responde; arrancandolo...", "warn")
    exe = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    if not exe.exists():
        from shutil import which

        found = which("ollama")
        if not found:
            _say("[!!] No encuentro ollama.exe. La traduccion fallara.", "err")
            return
        exe = Path(found)
    try:
        subprocess.Popen([str(exe), "serve"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except OSError as exc:
        _say(f"[!!] No pude arrancar Ollama: {exc}", "err")
        return
    for _ in range(20):
        time.sleep(0.5)
        if url_alive(OLLAMA):
            _say("[OK] Ollama listo.", "ok")
            return
    _say("[!!] Ollama sigue sin responder; la traduccion fallara.", "err")


def main() -> int:
    _say("== YouTube Dubber ==", "info")

    if panel_alive():
        _say(f"[OK] El panel ya estaba abierto en http://{HOST}:{PORT}", "ok")
        webbrowser.open(f"http://{HOST}:{PORT}")
        return 0
    if port_busy():
        raise LauncherError(
            f"El puerto {PORT} esta ocupado por otro programa que no es el panel.\n"
            "Cierralo, o arranca el panel en otro puerto con:\n"
            "  .\\.venv\\Scripts\\ytdubber.exe web --port 8766"
        )

    root, python = find_project()
    _say(f"[OK] Proyecto: {root}", "ok")
    ensure_ollama()

    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    proc = subprocess.Popen(
        [str(python), "-m", "ytdubber.cli", "web", "--no-browser",
         "--host", HOST, "--port", str(PORT)],
        cwd=str(root), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )

    ready = False
    for _ in range(120):
        if proc.poll() is not None:
            break
        if panel_alive():
            ready = True
            break
        time.sleep(0.5)

    if not ready:
        # The child either died or never answered. Show its own words, not a guess.
        _say("[!!] El panel no llego a arrancar. Salida del servidor:", "err")
        if proc.stdout is not None:
            for line in proc.stdout:
                print("   " + line.rstrip(), flush=True)
        stop_tree(proc)
        _pause()
        return 1

    _say(f"[OK] Panel listo: http://{HOST}:{PORT}", "ok")
    webbrowser.open(f"http://{HOST}:{PORT}")
    _say()
    _say("Deja esta ventana abierta. Ctrl+C para cerrar el panel.", "info")
    _say()

    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line.rstrip(), flush=True)
        return proc.wait()
    except KeyboardInterrupt:
        _say("\nCerrando el panel...", "warn")
        stop_tree(proc)
        _say("Cerrado.", "ok")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LauncherError as exc:
        _say(f"\n[!!] {exc}", "err")
        _pause()
        sys.exit(1)
