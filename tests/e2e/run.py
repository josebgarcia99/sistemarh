"""Ejecuta los recorridos completos en navegador (Playwright).

    python tests/e2e/run.py                      # todos
    python tests/e2e/run.py indicadores          # solo los que contengan ese texto
    python tests/e2e/run.py --api-python .venv/bin/python

Cada recorrido arranca desde cero: se levanta el modo demostración (datos en
memoria, IA simulada) y las pantallas ya compiladas, se ejecuta el recorrido y
se detiene todo. No usa SQL Server ni datos reales.

Requisitos:
- Las dependencias de la API en el Python indicado con ``--api-python``.
- En el Python que ejecuta este archivo: ``pip install playwright`` y
  ``playwright install chromium``.
- Las pantallas compiladas: ``cd apps/web && npm ci && npm run build``.
- Los puertos 3000 y 8000 libres.
"""

from __future__ import annotations

import argparse
import os
import secrets
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WEB = ROOT / "apps" / "web"
API_URL = "http://127.0.0.1:8000/api/v1/health/live"
WEB_URL = "http://localhost:3000/login"


def wait_for(url: str, seconds: int = 60) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    raise TimeoutError(f"No respondió a tiempo: {url}")


def start(command: list[str], cwd: Path, env: dict[str, str], log: Path) -> subprocess.Popen:
    # Grupo de procesos propio, para poder detener también a sus hijos.
    return subprocess.Popen(  # noqa: S603
        command,
        cwd=cwd,
        env=env,
        stdout=log.open("w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)


def run_one(script: Path, api_python: str, shots: Path, logs: Path) -> bool:
    env = {
        **os.environ,
        # Contraseña de un solo uso para los usuarios de demostración.
        "DEMO_PASSWORD": f"Demo-{secrets.token_urlsafe(9)}",
        "E2E_SHOTS": str(shots),
        # Para que un recorrido genere archivos de ejemplo con las utilidades de la API.
        "E2E_API_PYTHON": api_python,
        "PYTHONPATH": str(HERE),
    }
    demo = start([api_python, "scripts/demo.py"], ROOT, env, logs / f"{script.stem}_api.log")
    web = start(["npx", "next", "start", "-p", "3000"], WEB, env, logs / f"{script.stem}_web.log")
    try:
        wait_for(API_URL)
        wait_for(WEB_URL)
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(script)], env=env, capture_output=True, text=True, check=False
        )
    finally:
        stop(web)
        stop(demo)
    print(result.stdout.rstrip())
    if result.returncode != 0:
        print(result.stderr.rstrip()[-3000:])
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("filtro", nargs="?", default="", help="texto del nombre del recorrido")
    parser.add_argument("--api-python", default=sys.executable)
    args = parser.parse_args()
    if not (WEB / ".next").is_dir():
        print("Faltan las pantallas compiladas: cd apps/web && npm ci && npm run build")
        return 2
    scripts = sorted(p for p in HERE.glob("recorrido_*.py") if args.filtro in p.name)
    folder = Path(tempfile.mkdtemp(prefix="reclu-e2e-"))
    failed = []
    for script in scripts:
        print(f"\n=== {script.stem} ===")
        if not run_one(script, args.api_python, folder, folder):
            failed.append(script.stem)
        time.sleep(1)  # deja que se liberen los puertos
    print(f"\nCapturas y registros: {folder}")
    print(f"Recorridos: {len(scripts)} · con fallo: {len(failed)} {failed or ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
