"""Modo demostración: para ver las pantallas sin instalar SQL Server.

    python scripts/demo.py          # API en http://127.0.0.1:8000
    cd apps/web && npm run dev      # pantallas en http://localhost:3000

QUÉ ES Y QUÉ NO ES
- Arranca la API real, pero con los datos en memoria (el mismo motor que usan
  las pruebas automáticas). Todo se borra al cerrar.
- NO es SQL Server y no valida nada de SQL Server. No sustituye a la base de
  datos real en ningún entorno: solo sirve para mirar las pantallas.
- Los proveedores de IA están simulados: no se conecta a Anthropic ni a OpenAI.
  La "evaluación" de CV que muestra es inventada, solo para ver las pantallas.
- Los documentos se guardan en una carpeta temporal que se elimina al cerrar.
- Se niega a arrancar si el entorno está configurado como producción.
- Solo escucha en este equipo (127.0.0.1).
"""

# ruff: noqa: E402  (las importaciones de la API van después de ajustar la ruta)
from __future__ import annotations

import hashlib
import json
import os
import re
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
    Generation,
    Operation,
    ProviderCode,
    ProviderError,
)
from app.modules.file_management.domain.models import DocumentType
from app.modules.users.domain.models import Role
from app.modules.vacancies.application.service import VacancyData
from app.modules.vacancies.domain.models import AccessType, VacancyStatus, WorkMode
from app.tests.support.sample_files import docx_cv, pdf_cv, photo
from app.tests.support.sql_memory import build_test_backend

ADMIN_EMAIL = "admin@demo.test"
ANA_EMAIL = "ana@demo.test"
BETO_EMAIL = "beto@demo.test"
SAMPLE_PDF = (
    b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    b"% Documento ficticio del modo demostracion\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
)


# CV ficticios: tres con texto y uno "escaneado" (sin texto), que no se puede evaluar.
SAMPLE_CVS = [
    (
        f"CV Persona Ficticia {number}.pdf",
        pdf_cv(
            f"Persona Ficticia {number} - curriculum inventado para la demostracion",
            f"Analista de nomina, {number + 1} anios de experiencia en calculo de IMSS e ISR",
            "Excel intermedio y timbrado de recibos",
            f"Correo: persona{number}@ejemplo.test  Telefono: 55 0000 000{number}",
        ),
    )
    for number in (1, 2, 3)
] + [("CV Escaneado Ficticio.pdf", pdf_cv())]


# Lo que el proveedor simulado "lee" de cualquier perfil. No sale del documento.
SIMULATED_PROFILE = {
    "puesto": "Auxiliar Contable",
    "area": "Contabilidad",
    "proposito": "Registrar las operaciones contables del mes (respuesta simulada).",
    "niveles_de_formacion": ["Licenciatura", "TSU"],
    "especialidad": "Contaduría",
    "actividades": [{"actividad": "Registrar pólizas del día", "periodicidad": "Diaria"}],
    "experiencia": "Un año en un área contable.",
    "formacion": "Estudios en Contaduría.",
    "funciones": ["Registrar pólizas", "Conciliar cuentas bancarias"],
    "responsabilidades": ["Entregar el cierre mensual a tiempo"],
    "conocimientos": ["Normas de información financiera"],
    "habilidades": ["Orden y atención al detalle"],
    "certificaciones": [],
    "requisitos_indispensables": ["Experiencia en registro contable", "Manejo de Excel"],
    "requisitos_deseables": ["Conocimiento de CONTPAQi Contabilidad"],
    "ambiguedades": [
        "Respuesta simulada del modo demostración: el documento no se analizó de verdad",
        "«Manejo de Excel» no indica qué nivel",
    ],
}
PROFILE_DOCUMENT = docx_cv(
    "Perfil de puesto ficticio: Auxiliar Contable.",
    "Objetivo: registrar las operaciones contables del mes.",
    "Indispensable: experiencia en registro contable y manejo de Excel.",
    "Deseable: CONTPAQi Contabilidad.",
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

    def generate(self, api_key, model, *, system, user, max_output_tokens, images=()) -> Generation:
        # Consumo inventado, para ver la pantalla de costos.
        tokens = len(system + user) // 4 + 50
        simulated = None
        note = "Respuesta simulada del modo demostración: no la produjo ningún modelo real."
        if system.startswith(
            ("Recibes el texto de un reporte", "Recibes el material de una prueba")
        ):
            simulated = {
                "resumen": note,
                "resultados_documentados": ["Resultado simulado tomado del documento."],
                "datos_no_legibles": [],
                "advertencias": ["Resumen simulado: revisa el documento original."],
            }
        elif system.startswith("Recibes las notas de una entrevista"):
            simulated = {
                "resumen": note,
                "competencias_observadas": ["Competencia simulada"],
                "evidencias": ["Evidencia simulada tomada de las notas."],
                "informacion_faltante": [],
                "preguntas_de_seguimiento": ["Pregunta de seguimiento simulada."],
            }
        elif system.startswith("Recibes el texto de un formulario"):
            # "Lectura" inventada: un valor de ejemplo por campo, según su tipo.
            examples = {
                "FECHA": "2026-11-10",
                "TEXTO": "Dato simulado",
                "NUMERO": "2",
                "PARRAFO": "Texto simulado leído del formulario.",
                "CASILLA": True,
                "TABLA": [["Dato simulado"]],
            }
            fields = re.findall(r"^- (\S+): (.+?) \[(\w+)\]", user, re.MULTILINE)
            simulated = {
                "valores": {fid: examples[kind] for fid, _, kind in fields if kind in examples},
                "ilegibles": [label for _, label, kind in fields if kind == "OPCIONES"],
                "faltantes": [],
            }
        elif system.startswith("Recibes una fotografía"):
            simulated = {
                "descripcion": "Descripción simulada del modo demostración: la imagen no se "
                "analizó de verdad. Aquí aparecería lo que se observa en la fotografía.",
                "no_se_distingue": ["Detalle simulado que no se distingue"],
            }
        elif system.startswith("Recibes el expediente"):
            simulated = {
                "hechos_documentados": ["Hecho simulado tomado del CV (CV)."],
                "declaraciones": ["Declaración simulada de la llamada (llamada 1)."],
                "observaciones_humanas": ["Observación simulada de quien evaluó."],
                "resultados_tecnicos": [],
                "informacion_pendiente": ["Punto pendiente simulado."],
                "discrepancias_verificables": [],
            }
        elif user.startswith("CV a ordenar"):
            # "Extracción" inventada: solo el nombre sale de la primera línea del CV.
            first = user.split("<<<CV\n", 1)[-1].splitlines()[0]
            simulated = {
                "nombre": first.split(" - ")[0].strip()[:80],
                "experiencia": [
                    {
                        "puesto": "Analista de nómina",
                        "empresa": "Empresa Ficticia Uno",
                        "inicio": "2021-03",
                        "fin": "",
                        "actual": True,
                        "funciones": ["Cálculo de nómina"],
                    },
                    {
                        "puesto": "Auxiliar administrativo",
                        "empresa": "Empresa Ficticia Dos",
                        "inicio": "2018",
                        "fin": "2021-02",
                        "actual": False,
                        "funciones": [],
                    },
                ],
                "habilidades": ["Excel", "IMSS", "ISR"],
                "estudios": [
                    {
                        "titulo": "Contaduría",
                        "institucion": "Universidad Ficticia",
                        "periodo": "2014-2018",
                    }
                ],
                "certificaciones": [],
                "proyectos": [],
            }
        elif user.startswith("Propón"):
            simulated = {
                "preguntas": [
                    {
                        "texto": f"Pregunta simulada {number}: cuéntame de tu experiencia.",
                        "competencia": "Experiencia",
                        "guia": "Ejemplos concretos con fechas (simulado).",
                    }
                    for number in (1, 2, 3)
                ]
            }
        elif "<<<LLAMADA" in user:
            simulated = {
                "resumen": "Resumen simulado de la llamada: no lo produjo ningún modelo real.",
                "evidencias": ["Evidencia simulada tomada de las respuestas."],
                "competencias_exploradas": ["Experiencia"],
                "informacion_faltante": ["Dato simulado que no se preguntó."],
                "coincidencias_con_cv": [],
                "discrepancias_verificables": [],
                "preguntas_de_seguimiento": ["Pregunta de seguimiento simulada."],
            }
        if simulated is not None:
            text = json.dumps(simulated, ensure_ascii=False)
            return Generation(
                text, input_tokens=tokens, output_tokens=len(text) // 4, complete=True
            )
        if "<<<DOCUMENTO" in user:
            # "Lectura" inventada de un perfil: el documento no se analiza de verdad.
            text = json.dumps(SIMULATED_PROFILE, ensure_ascii=False)
            return Generation(
                text, input_tokens=tokens, output_tokens=len(text) // 4, complete=True
            )
        if "CRITERIOS DE LA RÚBRICA" in user:
            codes = re.findall(r"^(C\d+)\. ", user, re.MULTILINE)
            body = {
                "criterios": [
                    {
                        "id": code,
                        "descripcion": "Redacción simulada: busca en el CV evidencia con fechas.",
                        "niveles": [
                            "No hay evidencia en el CV (simulado).",
                            "Mención sin detalle ni fechas (simulado).",
                            "Evidencia directa pero parcial (simulado).",
                            "Evidencia directa y suficiente (simulado).",
                            "Evidencia que supera lo pedido (simulado).",
                        ],
                    }
                    for code in codes
                ],
                "observaciones": ["Propuesta simulada: no la produjo ningún modelo real."],
            }
            text = json.dumps(body, ensure_ascii=False)
            return Generation(
                text, input_tokens=tokens, output_tokens=len(text) // 4, complete=True
            )
        if "<<<CV" not in user:
            return Generation("OK", input_tokens=tokens, output_tokens=40, complete=True)
        # "Evaluación" inventada: los niveles salen del contenido del CV, sin
        # ningún análisis real. Sirve solo para ver la pantalla de resultados.
        codes = sorted(
            set(re.findall(r"^(C\d+)\. ", system, re.MULTILINE)), key=lambda c: int(c[1:])
        )
        seed = hashlib.sha256(user.encode()).digest()
        criteria = []
        for index, code in enumerate(codes):
            level = seed[index % len(seed)] % 5
            missing = seed[(index + 7) % len(seed)] % 9 == 0
            criteria.append(
                {
                    "id": code,
                    "nivel": None if missing else level,
                    "sin_evidencia": missing,
                    "evidencia": "" if missing else "Fragmento simulado del CV.",
                    "justificacion": "Respuesta simulada del modo demostración.",
                }
            )
        body = {
            "evaluable": True,
            "motivo_no_evaluable": None,
            "criterios": criteria,
            "calidad_documental": {
                "redaccion": 3,
                "ortografia": 3,
                "organizacion": 2,
                "claridad": 3,
                "coherencia": 3,
                "completitud": 2,
                "posible_error_de_digitalizacion": False,
            },
            "observaciones": "Evaluación simulada: no la produjo ningún modelo real.",
        }
        text = json.dumps(body, ensure_ascii=False)
        return Generation(text, input_tokens=tokens, output_tokens=len(text) // 4, complete=True)


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
        accounting = vacancies.create(
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
        ).vacancy
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
        # Perfil y prompt aprobado, para poder evaluar CV sin más preparación.
        setup = context.evaluation_setup(repos)
        setup.save_profile(
            ana,
            payroll.id,
            {
                "objective": "Calcular y pagar la nómina quincenal sin errores.",
                "experience": "Dos años en nómina.",
                "education": "Licenciatura en Contaduría o afín.",
                "functions": ["Calcular nómina", "Timbrar recibos"],
                "responsibilities": ["Cumplir las fechas de pago"],
                "knowledge": ["IMSS", "ISR"],
                "skills": ["Atención al detalle"],
                "certifications": [],
                "must_have": ["Experiencia en cálculo de nómina", "Manejo de Excel intermedio"],
                "nice_to_have": ["Conocimiento de CONTPAQi Nóminas"],
                "ambiguities": [],
            },
            change_note=None,
            expected_version=0,
        )
        draft = setup.generate(ana, payroll.id)
        review = setup.submit(ana, draft.id, expected_revision=draft.revision)
        setup.approve(ana, review.id, expected_revision=review.revision)

        # Proveedor simulado listo para evaluar (la clave no es real).
        ai = context.ai_settings(repos)
        ai.set_key(admin, ProviderCode.ANTHROPIC, "clave-simulada-demo-0000")
        ai.test_connection(admin, ProviderCode.ANTHROPIC)
        ai.update_provider(admin, ProviderCode.ANTHROPIC, enabled=True, monthly_limit_usd=None)
        model = next(m for m in ai.models(admin, ProviderCode.ANTHROPIC) if "grande" in m.model_id)
        for operation in (
            Operation.EVALUACION_DOCUMENTAL,
            Operation.ANALISIS_PERFILES,
            Operation.GENERACION_PROMPTS,
            Operation.EXTRACCION_CV,
            Operation.ANALISIS_LLAMADAS,
            Operation.RESUMEN_PRUEBAS,
            Operation.LECTURA_DOCUMENTOS,
            Operation.SINTESIS_EXPEDIENTES,
            Operation.DESCRIPCION_FOTOGRAFIAS,
        ):
            ai.assign(admin, operation, model.id)

        # Un banco de preguntas compartido, para probar las llamadas.
        context.phone_calls(repos).create_bank(
            ana,
            name="Filtro telefónico de nómina",
            description="Banco ficticio del modo demostración.",
            shared=True,
            questions=[
                {"text": "¿Qué nóminas has calculado y de qué tamaño?", "competency": "Nómina"},
                {"text": "¿Cómo validas el cálculo de IMSS e ISR?", "competency": "Cumplimiento"},
                {"text": "¿Qué disponibilidad tienes para iniciar?"},
            ],
        )

    pipeline = context.upload_pipeline()
    uploads = [(payroll.id, DocumentType.CV, name, content) for name, content in SAMPLE_CVS]
    # Un perfil en Word para probar «Llenar con IA desde un documento».
    uploads.append(
        (
            accounting.id,
            DocumentType.PERFIL_PUESTO,
            "Perfil Auxiliar Contable.docx",
            PROFILE_DOCUMENT,
        )
    )
    # Documentos ficticios para probar la psicometría y la digitalización del estudio.
    uploads.append(
        (
            payroll.id,
            DocumentType.PSICOMETRIA,
            "Reporte psicométrico ficticio.docx",
            docx_cv("Reporte ficticio de una prueba inventada.", "Escala A: percentil 70."),
        )
    )
    uploads.append(
        (
            payroll.id,
            DocumentType.ESTUDIO_SOCIOECONOMICO,
            "Estudio escaneado ficticio.docx",
            docx_cv(
                "Estudio socioeconómico ficticio.", "Fecha de aplicación: 10 de noviembre de 2026."
            ),
        )
    )
    # Una fotografía inventada (un rectángulo de color) para probar «Describir con IA».
    uploads.append(
        (payroll.id, DocumentType.ESTUDIO_SOCIOECONOMICO, "Fachada ficticia.jpg", photo())
    )
    for vacancy_id, document_type, name, content in uploads:
        with context.require_backend().transaction() as repos:
            asset = context.file_service(repos).begin_upload(
                ana,
                vacancy_id=vacancy_id,
                document_type=document_type,
                original_name=name,
                declared_size=len(content),
            )
        receiver = pipeline.receiver(asset)
        receiver.write(content)
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
            # Los proveedores son simulados: ningún documento sale de este equipo.
            ai_allow_real_documents=True,
        ),
        health_checks={"demostracion": lambda: True},
        backend=build_test_backend(),
        storage=storage,
        master_key=MasterKey.from_text(generate_key_text()),
        ai_clients={
            ProviderCode.ANTHROPIC: SimulatedProvider("anthropic"),
            ProviderCode.OPENAI: SimulatedProvider("openai"),
            ProviderCode.GEMINI: SimulatedProvider("gemini"),
        },
        # El motor en memoria tiene una sola conexión: los lotes se procesan al momento.
        job_mode="inline",
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
