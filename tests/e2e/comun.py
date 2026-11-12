"""Valores comunes de los recorridos en navegador."""

import os
import tempfile

# Los fija ``run.py``; por separado se pueden definir a mano.
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:3000")
PW = os.environ["DEMO_PASSWORD"]
SHOTS = os.environ.get("E2E_SHOTS") or tempfile.mkdtemp(prefix="reclu-e2e-")
os.makedirs(SHOTS, exist_ok=True)
