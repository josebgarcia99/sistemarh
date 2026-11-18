"""Sustituto de la IA para cargar los datos de prueba.

No se conecta a ningún proveedor, no necesita claves ni modelos asignados y no
registra consumo. Devuelve textos de ejemplo fijos, con la misma forma que
espera el sistema, para que las pantallas tengan algo que mostrar."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.modules.ai_settings.application.service import GenerationResult
from app.sample_data.content import EXAMPLE, PEOPLE


def _person(text: str):  # noqa: ANN202
    return next((person for person in PEOPLE if person.name in text), None)


class SampleAi:
    """Ocupa el lugar del servicio de IA solo durante la carga."""

    def ensure_ready(self, operation: object, *, carries_document: bool = False) -> None:
        return None

    def execute(self, operation: object, *, system: str, user: str, **_: Any) -> GenerationResult:
        body = self._answer(system, user)
        if body is None:
            return GenerationResult(
                ok=False,
                text="",
                complete=False,
                error="Los datos de prueba no incluyen un ejemplo para esta operación.",
                input_tokens=None,
                output_tokens=None,
                estimated_cost_usd=None,
                attempts=1,
                execution_id=uuid.uuid4(),
            )
        return GenerationResult(
            ok=True,
            text=json.dumps(body, ensure_ascii=False),
            complete=True,
            error=None,
            input_tokens=None,
            output_tokens=None,
            estimated_cost_usd=None,
            attempts=1,
            execution_id=uuid.uuid4(),
        )

    def _answer(self, system: str, user: str) -> dict[str, Any] | None:  # noqa: PLR0911
        if system.startswith("Recibes el reporte de una prueba psicométrica"):
            return {
                "resumen": EXAMPLE + "el reporte de la Prueba Inventada de Habilidades documenta "
                "tres escalas y concluye que el perfil es compatible con tareas de detalle.",
                "escalas": [
                    {
                        "nombre": "Atención al detalle",
                        "nivel": 4,
                        "maximo": 5,
                        "frase": "Nivel alto",
                        "lectura": "FAVORABLE",
                    },
                    {
                        "nombre": "Razonamiento numérico",
                        "nivel": 4,
                        "maximo": 5,
                        "frase": "Nivel alto",
                        "lectura": "FAVORABLE",
                    },
                    {
                        "nombre": "Trabajo bajo presión",
                        "nivel": 3,
                        "maximo": 5,
                        "frase": "Nivel medio",
                        "lectura": "INTERMEDIO",
                    },
                ],
                "resultados_documentados": [
                    "Atención al detalle: percentil 80.",
                    "Razonamiento numérico: percentil 65.",
                    "Trabajo bajo presión: percentil 40.",
                ],
                "interpretacion": [
                    "Atención al detalle, percentil 80: el reporte lo describe como alto frente "
                    "a su grupo de comparación.",
                    "Razonamiento numérico, percentil 65: el reporte lo ubica por encima del "
                    "promedio.",
                    "Trabajo bajo presión, percentil 40: el reporte lo ubica en el rango medio "
                    "y sugiere explorarlo en entrevista.",
                ],
                "datos_no_legibles": [],
                "advertencias": ["El reporte no indica la fecha de aplicación."],
                "preguntas_para_la_siguiente_etapa": [
                    "Cuéntame de un cierre de nómina con poco tiempo: ¿qué hiciste primero?",
                    "¿Cómo revisas tu propio trabajo antes de entregarlo?",
                ],
            }
        if system.startswith("Recibes el material de una prueba"):
            return {
                "resumen": EXAMPLE + "calculó bien 9 de 10 recibos; falló uno con incapacidad.",
                "resultados_documentados": [
                    "88 de 100 puntos en la rúbrica; el mínimo aprobatorio es 70."
                ],
                "datos_no_legibles": [],
                "advertencias": ["La prueba no cubrió finiquitos."],
                "preguntas_para_la_siguiente_etapa": [
                    "¿Cómo calculas un recibo cuando hay una incapacidad a media quincena?"
                ],
            }
        if system.startswith("Recibes las notas de una entrevista"):
            return {
                "resumen": EXAMPLE + "describió con fechas un cierre de nómina complicado y "
                "su calendario de la semana de pago.",
                "competencias_observadas": ["Organización", "Manejo de presión"],
                "evidencias": [
                    "Resolvió un fallo de timbrado en diciembre y pagó a tiempo.",
                    "Cierra incidencias el martes, calcula el miércoles y revisa el jueves.",
                ],
                "informacion_faltante": ["No se habló de experiencia con finiquitos."],
                "preguntas_de_seguimiento": ["¿Cómo calculas un finiquito con vacaciones?"],
            }
        if system.startswith("Recibes las referencias"):
            return {
                "resumen": EXAMPLE + "dos referencias contactadas y una sin localizar.",
                "referencias_laborales": [
                    "La referencia 1 indicó que es analista de nómina desde 2020 y que sigue ahí."
                ],
                "referencias_personales": [
                    "La referencia 3 indicó que la conoce desde hace ocho años."
                ],
                "coincidencias_con_cv": [
                    "Empresa, puesto y año de inicio coinciden con el empleo actual del CV."
                ],
                "discrepancias_verificables": [],
                "sin_confirmar": [
                    "La referencia 2 no se localizó: nadie confirma el empleo de 2018 a 2020."
                ],
                "preguntas_para_la_siguiente_etapa": [
                    "¿Quién más puede confirmar tu empleo de 2018 a 2020?"
                ],
            }
        if system.startswith("Recibes el expediente de una postulación que una persona"):
            return {
                "analisis_de_cierre": EXAMPLE + "la persona llegó hasta la etapa en la que se "
                "cerró su postulación. El CV documenta su experiencia y la llamada la confirmó.\n\n"
                "El motivo escrito por Recursos Humanos coincide con lo que consta en el "
                "expediente.",
                "avance_por_etapa": [
                    "CV: documenta la experiencia declarada.",
                    "Llamada: confirma el puesto y los años del CV.",
                ],
                "puntos_de_atencion": [
                    "Prueba técnica: falló un recibo con incapacidad (prueba técnica)."
                ],
                "informacion_pendiente": ["El estudio socioeconómico no se concluyó."],
            }
        if system.startswith("Recibes el expediente"):
            return {
                "puntos_de_atencion": [
                    "Prueba técnica: falló un recibo con incapacidad (prueba técnica).",
                    "Prueba psicométrica: el reporte ubica «Trabajo bajo presión» en 3 de 5, "
                    "lectura intermedia (prueba psicométrica).",
                    "Referencias: el empleo de 2018 a 2020 quedó sin confirmar (referencias).",
                ],
                "contrastes": [
                    "Cierre de nómina con poco tiempo: dijo resolverlo sin problema "
                    "(llamada 1); el reporte ubica «Trabajo bajo presión» en 3 de 5 (prueba "
                    "psicométrica). Conclusión: lo declarado se sostiene solo en parte; "
                    "conviene pedir un ejemplo concreto.",
                ],
                "veredicto": "RECOMENDABLE_CON_RESERVAS",
                "razones": [
                    "Seis años como analista de nómina en la misma empresa (CV).",
                    "88 de 100 en la prueba técnica (prueba técnica).",
                    "Un empleo anterior sin confirmar por referencias (referencias).",
                ],
                "conclusion": EXAMPLE + "cumple la experiencia que pide el puesto y su prueba "
                "técnica es alta. Quedan por aclarar un empleo sin confirmar y el manejo de "
                "recibos con incapacidad.",
                "hechos_documentados": [
                    "Seis años como analista de nómina en la misma empresa (CV).",
                    "88 de 100 en la prueba técnica (prueba técnica).",
                ],
                "declaraciones": [
                    "Dijo calcular una nómina quincenal de 350 personas (llamada).",
                    "Una referencia laboral indicó que sigue trabajando ahí (referencia 1).",
                ],
                "observaciones_humanas": [
                    "Quien entrevistó anotó respuestas concretas, con fechas y cifras."
                ],
                "resultados_tecnicos": ["Falló un recibo con incapacidad en la prueba técnica."],
                "informacion_pendiente": [
                    "El estudio socioeconómico sigue en proceso.",
                    "No se localizó a la referencia del empleo de 2018 a 2020.",
                ],
                "discrepancias_verificables": [],
                "coincidencias_entre_fuentes": [
                    "El CV indica seis años como analista de nómina (CV) y la referencia 1 "
                    "indicó que ocupa ese puesto desde 2020 (referencia 1).",
                    "En la llamada dijo conciliar contra el SUA cada mes (llamada 1) y quien "
                    "entrevistó anotó que describió su calendario de cierre (entrevista).",
                ],
                "avance_por_etapa": [
                    "CV: documenta seis años en nómina en una sola empresa.",
                    "Llamada: confirma el puesto y los años del CV; añade el tamaño de la "
                    "nómina (350 personas). No se habló de finiquitos.",
                    "Entrevista: respalda lo dicho en la llamada sobre el cierre de nómina; "
                    "sigue sin tratarse el tema de finiquitos.",
                    "Prueba técnica: 88 de 100; el único error fue un recibo con incapacidad, "
                    "tema que no se había tocado antes.",
                    "Referencias: una confirma el empleo actual del CV; el empleo de 2018 a "
                    "2020 queda sin confirmar.",
                ],
                "preguntas_sugeridas": [
                    "¿Cómo calculas un recibo con incapacidad?",
                    "¿Quién más puede confirmar tu empleo de 2018 a 2020?",
                ],
            }
        if user.startswith("CV a ordenar"):
            person = _person(user)
            if person is None:
                return None
            return {
                "nombre": person.name,
                "experiencia": person.jobs,
                "habilidades": ["Excel", "IMSS", "ISR"],
                "estudios": [
                    {
                        "titulo": "Contaduría",
                        "institucion": "Universidad Ficticia",
                        "periodo": "2012-2016",
                    }
                ],
                "certificaciones": [],
                "proyectos": [],
            }
        if "<<<LLAMADA" in user:
            rated = re.findall(
                r"^Pregunta (\d+): .*\n(?:  Competencia: .*\n)?  Qué se espera", user, re.MULTILINE
            )
            return {
                "resumen": EXAMPLE + "dijo calcular una nómina quincenal de 350 personas y "
                "describió cómo valida IMSS e ISR.",
                "evidencias": ["«Concilio contra el SUA cada mes»."],
                "competencias_exploradas": ["Nómina", "Cumplimiento"],
                "informacion_faltante": ["No se preguntó por finiquitos."],
                "coincidencias_con_cv": ["El puesto y los años coinciden con el CV."],
                "discrepancias_verificables": [],
                "preguntas_de_seguimiento": ["¿Qué sistema usarías si no hay CONTPAQi?"],
                "cobertura": [
                    {
                        "pregunta": int(number),
                        "nivel": ("CUMPLE", "CUMPLE", "PARCIAL")[index % 3],
                        "evidencia": "Respuesta de ejemplo.",
                    }
                    for index, number in enumerate(rated)
                ],
            }
        if "<<<CV" in user:
            person = _person(user)
            if person is None:
                return None
            codes = sorted(
                set(re.findall(r"^(C\d+)\. ", system, re.MULTILINE)), key=lambda c: int(c[1:])
            )
            return {
                "evaluable": True,
                "motivo_no_evaluable": None,
                "criterios": [
                    {
                        "id": code,
                        "nivel": person.level,
                        "sin_evidencia": False,
                        "evidencia": f"{person.years} años calculando nómina quincenal.",
                        "justificacion": "Nivel de ejemplo de los datos de prueba.",
                    }
                    for code in codes
                ],
                "calidad_documental": {
                    "redaccion": 3,
                    "ortografia": 4,
                    "organizacion": 3,
                    "claridad": 3,
                    "coherencia": 3,
                    "completitud": 3,
                    "posible_error_de_digitalizacion": False,
                },
                "observaciones": EXAMPLE + "calificación fija para mostrar la pantalla.",
            }
        return None
