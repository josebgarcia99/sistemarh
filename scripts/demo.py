"""Modo demostración: para ver las pantallas sin instalar SQL Server.

    python scripts/demo.py          # API en http://127.0.0.1:8000
    cd apps/web && npm run dev      # pantallas en http://localhost:3000

QUÉ ES Y QUÉ NO ES
- Arranca la API real, pero con los datos en memoria (el mismo motor que usan
  las pruebas automáticas). Todo se borra al cerrar.
- NO es SQL Server y no valida nada de SQL Server. No sustituye a la base de
  datos real en ningún entorno: solo sirve para mirar las pantallas.
- Los proveedores de IA están simulados: no se conecta a Anthropic ni a OpenAI.
- Los documentos se guardan en una carpeta temporal que se elimina al cerrar.
- Se niega a arrancar si el entorno está configurado como producción.
- Solo escucha en este equipo (127.0.0.1).
"""

# ruff: noqa: E402  (las importaciones de la API van después de ajustar la ruta)
from __future__ import annotations

import os
import secrets
import shutil
import signal
import sys
import tempfile
from pathlib import Path

if os.environ.get("RECLU_ENVIRONMENT", "").lower() == "production":
    sys.exit("El modo demostración no se ejecuta en producción.")
# La demostración no usa la configuración del equipo: ni base de datos, ni
# carpeta de documentos, ni claves. Se descartan antes de cargar la API.
for _name in [name for name in os.environ if name.startswith("RECLU_")]:
    del os.environ[_name]

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import anyio.to_thread
import uvicorn

from app.core.config.settings import Environment, Settings
from app.core.security.master_key import MasterKey, generate_key_text
from app.infrastructure.storage.local import LocalFileStorage
from app.main import create_app
from app.modules.ai_settings.domain.models import (
    DiscoveredModel,
    ProviderCode,
    ProviderError,
)
from app.modules.file_management.domain.models import DocumentType
from app.modules.users.domain.models import Role
from app.modules.vacancies.application.service import VacancyData
from app.modules.vacancies.domain.models import AccessType, VacancyStatus, WorkMode
from app.tests.support.sql_memory import build_test_backend

ADMIN_EMAIL = "admin@demo.test"
ANA_EMAIL = "ana@demo.test"
BETO_EMAIL = "beto@demo.test"
SAMPLE_PDF = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"% Documento ficticio del modo demostracion\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
)


class SimulatedProvider:
    """No se conecta a ningún servicio. Una clave terminada en MALA se rechaza."""

    def __init__(self, name: str) -> None:
        self._name = name

    def list_models(self, api_key: str) -> list[DiscoveredModel]:
        if api_key.endswith("MALA"):
            raise ProviderError(
                "clave",
                "El proveedor rechazó la clave: no es válida o no tiene permisos.",
            )
        return [
            DiscoveredModel(f"demo-{self._name}-grande", f"Modelo simulado grande ({self._name})"),
            DiscoveredModel(f"demo-{self._name}-rapido", f"Modelo simulado rápido ({self._name})"),
        ]


def seed(app, password: str) -> None:
    context = app.state.context
    with context.require_backend().transaction() as repos:
        users = context.user_service(repos)
        admin = users.create_master_user(
            email=ADMIN_EMAIL, full_name="Administradora Demo", password=password
        )
        ana = users.create_user(
            admin,
            email=ANA_EMAIL,
            full_name="Ana Demo",
            password=password,
            role=Role.RECLUTADOR,
        )
        beto = users.create_user(
            admin,
            email=BETO_EMAIL,
            full_name="Beto Demo",
            password=password,
            role=Role.RECLUTADOR,
        )
        vacancies = context.vacancy_service(repos)
        payroll = vacancies.create(
            ana,
            VacancyData(
                name="Analista de Nómina",
                department="Finanzas",
                location="Monterrey",
                work_mode=WorkMode.HIBRIDA,
                contract_type="Tiempo completo",
                description="Vacante ficticia del modo demostración.",
                positions=2,
            ),
        ).vacancy
        vacancies.change_status(ana, payroll.id, VacancyStatus.ABIERTA, expected_version=1)
        vacancies.set_member(ana, payroll.id, beto.id, AccessType.LECTURA)
        vacancies.create(
            ana,
            VacancyData(
                name="Auxiliar Contable",
                department="Finanzas",
                location="Ciudad de México",
                work_mode=WorkMode.PRESENCIAL,
                contract_type="Temporal",
                description="Vacante ficticia en borrador.",
                positions=1,
            ),
        )
        vacancies.create(
            beto,
            VacancyData(
                name="Desarrollador Backend",
                department="Tecnología",
                location="Remoto",
                work_mode=WorkMode.REMOTA,
                contract_type="Tiempo completo",
                description="Vacante ficticia de otro reclutador.",
                positions=3,
            ),
        )
        asset = context.file_service(repos).begin_upload(
            ana,
            vacancy_id=payroll.id,
            document_type=DocumentType.CV,
            original_name="CV Persona Ficticia.pdf",
            declared_size=len(SAMPLE_PDF),
        )
    pipeline = context.upload_pipeline()
    receiver = pipeline.receiver(asset)
    receiver.write(SAMPLE_PDF)
    receiver.close()
    outcome = pipeline.store(asset, receiver)
    with context.require_backend().transaction() as repos:
        context.file_service(repos).finish_upload(ana, asset.id, outcome)


def main() -> int:
    folder = Path(tempfile.mkdtemp(prefix="reclutamiento-demo-"))
    storage = LocalFileStorage(folder)
    storage.prepare()
    app = create_app(
        settings=Settings(
            environment=Environment.DEVELOPMENT,
            database_url=None,
            redis_url=None,
            storage_root=None,
            master_key_file=None,
            storage_min_free_bytes=0,
        ),
        health_checks={"demostracion": lambda: True},
        backend=build_test_backend(),
        storage=storage,
        master_key=MasterKey.from_text(generate_key_text()),
        ai_clients={
            ProviderCode.ANTHROPIC: SimulatedProvider("anthropic"),
            ProviderCode.OPENAI: SimulatedProvider("openai"),
        },
    )
    # La contraseña se genera en cada arranque; no hay credenciales en el código.
    password = os.environ.get("DEMO_PASSWORD") or f"Demo-{secrets.token_urlsafe(9)}"
    seed(app, password)

    # El motor en memoria comparte una sola conexión: se atiende una petición a la vez.
    async def one_at_a_time() -> None:
        anyio.to_thread.current_default_thread_limiter().total_tokens = 1

    app.router.on_startup.append(one_at_a_time)

    line = "=" * 68
    print(line)
    print(" MODO DEMOSTRACIÓN: datos en memoria, se borran al cerrar.")
    print(" No es SQL Server ni sustituye a la base de datos real.")
    print(line)
    print(" Abre http://localhost:3000 (con el frontend en marcha) y entra con:")
    print(f"   Administradora: {ADMIN_EMAIL}")
    print(f"   Reclutadores:   {ANA_EMAIL}   {BETO_EMAIL}")
    print(f"   Contraseña (la misma para los tres): {password}")
    print(" Para detenerlo: Ctrl+C")
    print(line, flush=True)
    # Al terminar el proceso, la carpeta temporal se elimina.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
