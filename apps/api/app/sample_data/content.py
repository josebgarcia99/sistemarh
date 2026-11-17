"""Contenido inventado de los datos de prueba. Ninguna persona, empresa,
correo ni teléfono es real: los correos usan el dominio reservado
``ejemplo.test`` y los teléfonos, números imposibles."""

from __future__ import annotations

from dataclasses import dataclass, field

VACANCY_NAME = "Analista de Nómina · DATOS DE PRUEBA"
EXAMPLE = "Ejemplo de los datos de prueba (no lo escribió ninguna IA): "

PROFILE = {
    "objective": "Calcular y pagar la nómina quincenal de 400 personas, sin errores y a tiempo.",
    "experience": "Dos años calculando nómina en empresas de más de 100 personas.",
    "education": "Licenciatura en Contaduría, Administración o afín.",
    "functions": [
        "Calcular la nómina quincenal",
        "Timbrar recibos",
        "Determinar cuotas de IMSS e INFONAVIT",
    ],
    "responsibilities": ["Cumplir las fechas de pago", "Atender aclaraciones del personal"],
    "knowledge": ["IMSS", "ISR", "SUA"],
    "skills": ["Atención al detalle", "Trato amable con el personal"],
    "certifications": [],
    "must_have": ["Experiencia en cálculo de nómina", "Manejo de Excel intermedio"],
    "nice_to_have": ["Conocimiento de CONTPAQi Nóminas"],
    "ambiguities": [],
}

BANK_NAME = "Filtro telefónico de nómina · datos de prueba"
# (pregunta, competencia, qué se espera de la respuesta, respuesta de ejemplo)
BANK = [
    (
        "¿Qué nóminas has calculado y de qué tamaño?",
        "Nómina",
        "Número de personas, periodicidad y sistema que usó.",
        "Nómina quincenal de 350 personas durante tres años, en CONTPAQi Nóminas.",
    ),
    (
        "¿Cómo validas el cálculo de IMSS e ISR antes de pagar?",
        "Cumplimiento",
        "Un método de revisión concreto, no solo «lo reviso».",
        "Concilio contra el SUA cada mes y reviso una muestra de recibos contra la tabla de ISR.",
    ),
    (
        "¿Qué harías si detectas un error después de timbrar?",
        "Solución de problemas",
        "Cancelación o complemento del recibo y aviso a la persona afectada.",
        "Cancelo el recibo, lo vuelvo a timbrar corregido y le aviso a la persona el mismo día.",
    ),
    (
        "¿Cuándo podrías empezar y cuál es tu expectativa de sueldo?",
        "",
        "",
        "En dos semanas. Entre 16 y 18 mil pesos mensuales.",
    ),
]


@dataclass(frozen=True)
class Person:
    name: str
    # Nivel que el ejemplo de evaluación da a todos los criterios (0 a 4).
    level: int
    # Hasta dónde llega: REVISION_RH, LLAMADA, PSICOMETRIA, ENTREVISTA,
    # PRUEBA_TECNICA, ESTUDIO_SOCIOECONOMICO o RESULTADO.
    stage: str
    years: int
    employer: str
    outcome: tuple[str, str] | None = None  # (resultado, motivo)
    extras: frozenset[str] = field(default_factory=frozenset)

    @property
    def slug(self) -> str:
        return self.name.split()[0].lower()

    @property
    def email(self) -> str:
        return f"{self.slug}@ejemplo.test"

    def phone(self, number: int) -> str:
        return f"55 0000 00{number:02d}"

    @property
    def jobs(self) -> list[dict[str, object]]:
        start = 2026 - self.years
        return [
            {
                "puesto": "Analista de nómina",
                "empresa": self.employer,
                "inicio": f"{start}-03",
                "fin": "",
                "actual": True,
                "funciones": ["Cálculo de nómina quincenal", "Timbrado de recibos"],
            },
            {
                "puesto": "Auxiliar administrativo",
                "empresa": "Servicios Ficticios del Norte",
                "inicio": f"{start - 2}-01",
                "fin": f"{start}-02",
                "actual": False,
                "funciones": ["Captura de incidencias"],
            },
        ]

    def cv_lines(self, number: int) -> list[str]:
        return [
            f"{self.name} - currículum inventado para los datos de prueba",
            f"Correo: {self.email}   Teléfono: {self.phone(number)}",
            f"Analista de nómina en {self.employer}, de {2026 - self.years} a la fecha.",
            f"{self.years} años calculando nómina quincenal, IMSS e ISR. Excel intermedio.",
            f"Auxiliar administrativo en Servicios Ficticios del Norte, {2024 - self.years} a "
            f"{2026 - self.years}.",
            "Licenciatura en Contaduría, Universidad Ficticia, 2012 a 2016.",
        ]


# La etapa de cada quien muestra un momento distinto del proceso.
PEOPLE = [
    Person("Mariana Ficticia Ortega", 4, "ESTUDIO_SOCIOECONOMICO", 6, "Comercial Ficticia SA"),
    Person("Luis Ficticio Herrera", 3, "PRUEBA_TECNICA", 4, "Grupo Inventado del Bajío"),
    Person("Sofía Ficticia Rangel", 3, "ENTREVISTA", 3, "Manufacturas Imaginarias"),
    Person("Diego Ficticio Morales", 3, "PSICOMETRIA", 3, "Transportes de Ejemplo"),
    Person("Valeria Ficticia Núñez", 4, "LLAMADA", 5, "Alimentos Supuestos SA"),
    # La IA lo rechazó y Recursos Humanos decidió avanzarlo de todos modos.
    Person("Jorge Ficticio Salas", 2, "LLAMADA", 1, "Tienda Hipotética"),
    Person("Paola Ficticia Rivas", 3, "REVISION_RH", 2, "Farmacias de Muestra"),
    Person("Andrés Ficticio Cano", 1, "REVISION_RH", 1, "Papelería Simulada"),
    Person(
        "Fernanda Ficticia Lugo",
        3,
        "LLAMADA",
        4,
        "Hoteles de Prueba",
        outcome=("DESISTIO", "Aceptó otra oferta antes de la entrevista."),
    ),
    Person(
        "Elena Ficticia Duarte",
        4,
        "RESULTADO",
        7,
        "Constructora Aparente",
        outcome=("CONTRATADO", ""),
    ),
]
# Un CV escaneado, sin texto: queda como «no evaluable».
SCANNED_CV = "CV escaneado ficticio.pdf"

INTERVIEW = {
    "interviewer": "Gerente Ficticio de Nómina",
    "questions": [
        {
            "question": "Cuéntame de un cierre de nómina que se complicó.",
            "answer": "En diciembre falló el timbrado; se quedó a resolverlo y pagó a tiempo.",
        },
        {
            "question": "¿Cómo te organizas en la semana de pago?",
            "answer": "Cierra incidencias el martes, calcula el miércoles y revisa el jueves.",
        },
    ],
    "competencies": ["Organización", "Manejo de presión"],
    "feedback": "Respuestas concretas, con fechas y cifras.",
    "evidence": "Describió el calendario de cierre sin que se le pidiera.",
    "notes": "Pidió conocer el sistema de nómina que se usa.",
    "conclusion": "Cumple con lo que busca el área. Sugiero continuar el proceso.",
}
TECHNICAL = {
    "test_type": "Caso práctico de cálculo de nómina en Excel",
    "competency": "Cálculo de nómina",
    "responsible": "Jefatura Ficticia de Nómina",
    "result": "Calculó correctamente 9 de 10 recibos.",
    "evidence": "Archivo de Excel entregado en 50 minutos.",
    "comments": "El error fue en un recibo con incapacidad.",
    "pass_mark": "70",
}
TECHNICAL_RUBRIC = [
    ("Cálculo de percepciones", 40, 38),
    ("Cálculo de ISR e IMSS", 40, 32),
    ("Orden y presentación", 20, 18),
]
PSYCHOMETRIC = {
    "instrument": "Prueba Inventada de Habilidades",
    "instrument_version": "2",
    "provider": "Proveedor Ficticio de Evaluaciones",
    "result": "Resultado de ejemplo: dentro del rango esperado para el puesto.",
    "notes": "Aplicada en línea.",
    "professional_name": "Psic. Ficticia Responsable",
    "professional_license": "0000000",
    "validation_note": "Interpretación de ejemplo, sin valor real.",
}
# Reporte inventado que se adjunta a la psicometría validada, para ver el resumen.
PSYCHOMETRIC_REPORT = [
    "Reporte ficticio de la Prueba Inventada de Habilidades (datos de prueba).",
    "Atención al detalle: percentil 80. Rango alto frente al grupo de comparación.",
    "Razonamiento numérico: percentil 65. Por encima del promedio.",
    "Trabajo bajo presión: percentil 40. Rango medio; se sugiere explorarlo en entrevista.",
    "Conclusión del profesional: perfil compatible con tareas de detalle.",
    "Interpretó: Psic. Ficticia Responsable.",
]
# Fotografía adicional del estudio: una imagen de un solo color, con su descripción.
EXTRA_PHOTO = {
    "title": "Calle de acceso (imagen de ejemplo)",
    "description": "Ejemplo de los datos de prueba: la imagen es un rectángulo de color, no una "
    "fotografía real. Aquí iría la descripción de lo que se observa.",
}

REFERENCES = [
    {
        "type": "LABORAL",
        "name": "Jefa Ficticia Anterior",
        "relation": "Comercial Ficticia SA",
        "position": "Gerente de nómina",
        "phone": "55 0000 0091",
        "period": "2020 a 2026",
        "contacted_by": "Analista de estudios (datos de prueba)",
        "contacted_on": "2026-11-14",
        "result": "CONTACTADA",
        "comments": "Confirma el puesto de analista de nómina desde 2020. La describe como "
        "ordenada. Dice que sigue trabajando ahí.",
    },
    {
        "type": "LABORAL",
        "name": "Supervisor Ficticio",
        "relation": "Servicios Ficticios del Norte",
        "position": "Supervisor administrativo",
        "phone": "55 0000 0092",
        "period": "2018 a 2020",
        "contacted_by": "Analista de estudios (datos de prueba)",
        "contacted_on": "2026-11-14",
        "result": "NO_LOCALIZADA",
        "comments": "",
    },
    {
        "type": "PERSONAL",
        "name": "Vecina Ficticia",
        "relation": "Vecina desde hace ocho años",
        "position": "",
        "phone": "55 0000 0093",
        "period": "",
        "contacted_by": "Analista de estudios (datos de prueba)",
        "contacted_on": "2026-11-15",
        "result": "CONTACTADA",
        "comments": "La conoce desde hace ocho años. Dice que es puntual y de trato amable.",
    },
]
# Respuestas del estudio, por etiqueta del formato de la empresa.
STUDY_ANSWERS = {
    "Fecha de aplicación": "2026-11-15",
    "Nombre completo": "Mariana Ficticia Ortega",
    "Ocupación": "Analista de nómina",
    "Domicilio": "Calle Inventada 123, Colonia de Ejemplo, Monterrey, N. L.",
    "Tiempo de habitar": "8 años",
    "Nacionalidad": "Mexicana",
    "Escolaridad": "Licenciatura",
}
