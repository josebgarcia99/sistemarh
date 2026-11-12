"""Medición de rendimiento con volumen sintético.

    python scripts/medir_rendimiento.py              # 2 000, 20 000 y 50 000 postulaciones
    python scripts/medir_rendimiento.py 5000         # un solo volumen

QUÉ MIDE
- El tiempo de respuesta de la API real (todas sus capas: sesión, permisos,
  consultas, cálculo y respuesta) con miles de postulaciones inventadas.
- Las rutas que más datos leen: tableros, histórico, Excel, lista de vacantes,
  candidatos de una vacante y expediente.

QUÉ NO MIDE
- SQL Server: los datos están en memoria, en el mismo motor que usan las
  pruebas automáticas. Sirve para detectar un cálculo mal planteado (que el
  tiempo crezca más rápido que los datos), no para dimensionar el servidor.
- Usuarios simultáneos: las solicitudes van de una en una.
- Lotes de CV y documentos: no se generan archivos.

Todos los datos son inventados y se borran al terminar.
"""

# ruff: noqa: E402  (las importaciones de la API van después de ajustar la ruta)
from __future__ import annotations

import os
import random
import statistics
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

for _name in [name for name in os.environ if name.startswith("RECLU_")]:
    del os.environ[_name]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app import cli
from app.core.config.settings import Environment, Settings
from app.infrastructure.storage.local import LocalFileStorage
from app.main import create_app
from app.modules.ai_settings.infrastructure.orm import AiExecutionRow
from app.modules.authentication.api.dependencies import CSRF_HEADER
from app.modules.recruitment.infrastructure.orm import (
    ApplicationMovementRow,
    ApplicationOutcomeRow,
    ApplicationRow,
    CampaignRow,
    CandidateRow,
)
from app.modules.vacancies.infrastructure.orm import VacancyRow
from app.tests.support.sql_memory import build_test_backend

API = "/api/v1"
# Contraseña de usuarios inventados que solo existen en memoria durante la medición.
PASSWORD = "Clave-Medicion-2026"  # noqa: S105
RECRUITERS = 10
APPLICATIONS_PER_VACANCY = 100
REPEATS = 5
OUTCOMES = ("CONTRATADO", "NO_CONTRATADO", "DESISTIO", "NO_LOCALIZADO")
STATUS = {
    "CONTRATADO": "CONTRATADA",
    "NO_CONTRATADO": "DESCARTADA",
    "DESISTIO": "DESISTIO",
    "NO_LOCALIZADO": "NO_LOCALIZADA",
}
MOVEMENT = {
    "CONTRATADO": "CONTRATACION",
    "NO_CONTRATADO": "DESCARTE",
    "DESISTIO": "DESISTIMIENTO",
    "NO_LOCALIZADO": "NO_LOCALIZADO",
}


def login(app, email: str) -> TestClient:
    # HTTPS: la cookie de sesión es «Secure» y no viajaría por HTTP.
    client = TestClient(app, base_url="https://testserver")
    response = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    client.headers[CSRF_HEADER] = response.json()["csrf_token"]
    return client


def seed(backend, stages: list[str], owners: list[str], applications: int, rng: random.Random):
    """Inserta directamente las filas: por la API tardaría horas."""
    start = datetime(2025, 1, 1, tzinfo=UTC)
    pipeline = stages[0][1]
    stage_ids = [stage_id for stage_id, _ in stages]
    vacancies, campaigns, candidates, rows, movements, outcomes = [], [], [], [], [], []
    for number in range(max(1, applications // APPLICATIONS_PER_VACANCY)):
        owner = uuid.UUID(owners[number % len(owners)])
        vacancy_id, campaign_id = uuid.uuid4(), uuid.uuid4()
        opened = start + timedelta(days=rng.randrange(600))
        vacancies.append(
            {
                "id": vacancy_id,
                "name": f"Puesto ficticio {number + 1}",
                "department": f"Área {number % 12 + 1}",
                "location": "CDMX",
                "work_mode": "HIBRIDA",
                "contract_type": "Tiempo indeterminado",
                "description": "Vacante inventada para medir el rendimiento.",
                "positions": 5,
                "status": "ABIERTA" if number % 3 else "CERRADA",
                "owner_user_id": owner,
                "opened_at": opened,
                "created_at": opened,
                "created_by": owner,
                "updated_at": opened,
                "updated_by": owner,
                "version": 1,
            }
        )
        campaigns.append(
            {
                "id": campaign_id,
                "vacancy_id": vacancy_id,
                "number": 1,
                "name": "Convocatoria 1",
                "status": "ABIERTA",
                "pipeline_version_id": uuid.UUID(pipeline),
                "opened_at": opened,
                "opened_by": owner,
            }
        )
        hires = 0
        for index in range(APPLICATIONS_PER_VACANCY):
            application_id, candidate_id = uuid.uuid4(), uuid.uuid4()
            created = opened + timedelta(days=rng.randrange(30), minutes=index)
            reached = rng.randrange(1, len(stage_ids))
            outcome = rng.choice(OUTCOMES) if rng.random() < 0.6 else None
            if outcome == "CONTRATADO":
                hires += 1
                if hires > 5:
                    outcome = "NO_CONTRATADO"
            candidates.append(
                {
                    "id": candidate_id,
                    "full_name": f"Persona Ficticia {number + 1}-{index + 1}",
                    "email": f"persona{number}-{index}@ejemplo.test",
                    "created_at": created,
                    "updated_at": created,
                }
            )
            rows.append(
                {
                    "id": application_id,
                    "candidate_id": candidate_id,
                    "campaign_id": campaign_id,
                    "vacancy_id": vacancy_id,
                    "stage_id": uuid.UUID(stage_ids[reached]),
                    "status": STATUS[outcome] if outcome else "ACTIVA",
                    "ai_classification": rng.choice(("ACEPTADO_IA", "RECHAZADO_IA")),
                    "ai_score": rng.randrange(0, 101),
                    "created_at": created,
                    "updated_at": created,
                }
            )
            moment, sequence = created, 1
            movements.append(
                {
                    "id": uuid.uuid4(),
                    "application_id": application_id,
                    "sequence": sequence,
                    "kind": "ALTA",
                    "to_stage_id": uuid.UUID(stage_ids[0]),
                    "occurred_at": moment,
                }
            )
            for step in range(1, reached + 1):
                moment += timedelta(days=rng.randrange(1, 6))
                sequence += 1
                movements.append(
                    {
                        "id": uuid.uuid4(),
                        "application_id": application_id,
                        "sequence": sequence,
                        "kind": "AVANCE",
                        "from_stage_id": uuid.UUID(stage_ids[step - 1]),
                        "to_stage_id": uuid.UUID(stage_ids[step]),
                        "occurred_at": moment,
                        "actor_user_id": owner,
                    }
                )
            if outcome:
                moment += timedelta(days=rng.randrange(1, 6))
                movements.append(
                    {
                        "id": uuid.uuid4(),
                        "application_id": application_id,
                        "sequence": sequence + 1,
                        "kind": MOVEMENT[outcome],
                        "from_stage_id": uuid.UUID(stage_ids[reached]),
                        "occurred_at": moment,
                        "actor_user_id": owner,
                        "note": "Motivo inventado",
                    }
                )
                outcomes.append(
                    {
                        "id": uuid.uuid4(),
                        "application_id": application_id,
                        "vacancy_id": vacancy_id,
                        "outcome": outcome,
                        "reason": "Motivo inventado",
                        "recorded_at": moment,
                        "recorded_by": owner,
                    }
                )
    executions = [
        {
            "id": uuid.uuid4(),
            "occurred_at": start + timedelta(minutes=rng.randrange(600 * 24 * 60)),
            "operation": "EVALUACION_DOCUMENTAL",
            "provider_code": "ANTHROPIC",
            "model_id": "modelo-ficticio",
            "status": "CORRECTA" if rng.random() > 0.02 else "FALLIDA",
            "attempts": 1,
            "duration_ms": 900,
            "input_tokens": 1500,
            "output_tokens": 400,
            "estimated_cost_usd": "0.0105",
            "vacancy_id": rng.choice(vacancies)["id"],
        }
        for _ in range(len(rows))
    ]
    with backend._session_factory() as session:
        for table, data in (
            (VacancyRow, vacancies),
            (CampaignRow, campaigns),
            (CandidateRow, candidates),
            (ApplicationRow, rows),
            (ApplicationMovementRow, movements),
            (ApplicationOutcomeRow, outcomes),
            (AiExecutionRow, executions),
        ):
            for offset in range(0, len(data), 5000):
                session.execute(sa.insert(table), data[offset : offset + 5000])
        session.commit()
    return vacancies[0]["id"], rows[0]["id"], len(vacancies), len(movements)


def timed(call) -> tuple[float, float]:
    samples = []
    for _ in range(REPEATS):
        started = time.perf_counter()
        response = call()
        samples.append((time.perf_counter() - started) * 1000)
        assert response.status_code in (200, 201), response.text[:300]
    return statistics.median(samples), max(samples)


def measure(applications: int) -> list[tuple[str, float, float]]:
    # Semilla fija: los mismos datos inventados en cada medición.
    rng = random.Random(2026)  # noqa: S311
    backend = build_test_backend()
    with tempfile.TemporaryDirectory(prefix="reclu-medicion-") as folder:
        storage = LocalFileStorage(Path(folder))
        storage.prepare()
        app = create_app(
            settings=Settings(
                environment=Environment.TEST, storage_min_free_bytes=0, log_level="ERROR"
            ),
            health_checks={"x": lambda: True},
            backend=backend,
            storage=storage,
            job_mode="inline",
        )
        cli.create_admin(
            app.state.context,
            email="admin@ejemplo.test",
            full_name="Administradora de Medición",
            password=PASSWORD,
        )
        admin = login(app, "admin@ejemplo.test")
        owners = []
        for number in range(RECRUITERS):
            created = admin.post(
                f"{API}/users",
                json={
                    "email": f"reclutador{number}@ejemplo.test",
                    "full_name": f"Reclutador Ficticio {number + 1}",
                    "password": PASSWORD,
                    "role": "RECLUTADOR",
                },
            )
            owners.append(created.json()["id"])
        pipeline = admin.get(f"{API}/pipeline").json()
        stages = [(stage["id"], pipeline["id"]) for stage in pipeline["stages"]]
        vacancy_id, application_id, vacancies, movements = seed(
            backend, stages, owners, applications, rng
        )
        recruiter = login(app, "reclutador0@ejemplo.test")
        print(
            f"\n{applications:,} postulaciones · {vacancies:,} vacantes · "
            f"{movements:,} movimientos · {RECRUITERS} reclutadores".replace(",", " ")
        )
        year = {"date_from": "2026-01-01", "date_to": "2026-12-31"}
        cases = [
            (
                "Tablero del administrador, todo el histórico",
                lambda: admin.get(f"{API}/reports/overview"),
            ),
            (
                "Tablero del administrador, un año",
                lambda: admin.get(f"{API}/reports/overview", params=year),
            ),
            (
                "Tablero de un reclutador (sus vacantes)",
                lambda: recruiter.get(f"{API}/reports/overview"),
            ),
            (
                "Histórico de candidatos, primera página",
                lambda: admin.get(f"{API}/reports/applications"),
            ),
            (
                "Histórico filtrado por resultado y nombre",
                lambda: admin.get(
                    f"{API}/reports/applications",
                    params={"outcome": "CONTRATADO", "candidate": "ficticia 1"},
                ),
            ),
            (
                "Excel de postulaciones de un reclutador",
                lambda: recruiter.post(f"{API}/reports/exports", json={"kind": "POSTULACIONES"}),
            ),
            ("Lista de vacantes", lambda: admin.get(f"{API}/vacancies")),
            (
                "Candidatos de una vacante (100 personas)",
                lambda: admin.get(f"{API}/vacancies/{vacancy_id}/applications"),
            ),
            (
                "Expediente de una persona",
                lambda: admin.get(f"{API}/applications/{application_id}"),
            ),
        ]
        results = []
        for label, call in cases:
            median, worst = timed(call)
            results.append((label, median, worst))
            print(f"  {label:<48} {median:>8.0f} ms   (máx. {worst:.0f} ms)")
        return results


def main() -> int:
    sizes = [int(value) for value in sys.argv[1:]] or [2_000, 20_000, 50_000]
    print(__doc__.split("QUÉ MIDE")[0].strip())
    print("Motor en memoria (no es SQL Server). Mediana de", REPEATS, "repeticiones.")
    for size in sizes:
        measure(size)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
