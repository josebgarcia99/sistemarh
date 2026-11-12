"""Evento de auditoría. Solo se inserta; nunca se modifica ni se borra."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol


class AuditResult(StrEnum):
    PERMITIDO = "PERMITIDO"
    DENEGADO = "DENEGADO"
    FALLIDO = "FALLIDO"


class AuditAction(StrEnum):
    SESION_INICIO = "sesion.inicio"
    SESION_INICIO_FALLIDO = "sesion.inicio_fallido"
    SESION_CIERRE = "sesion.cierre"
    ACCESO_DENEGADO = "acceso.denegado"
    USUARIO_CREADO = "usuario.creado"
    USUARIO_ACTUALIZADO = "usuario.actualizado"
    USUARIO_CONTRASENA_RESTABLECIDA = "usuario.contrasena_restablecida"
    USUARIO_DESACTIVADO = "usuario.desactivado"
    USUARIO_ACTIVADO = "usuario.activado"
    VACANTE_CREADA = "vacante.creada"
    VACANTE_ACTUALIZADA = "vacante.actualizada"
    VACANTE_ESTADO_CAMBIADO = "vacante.estado_cambiado"
    VACANTE_COMPARTIDA = "vacante.compartida"
    VACANTE_ACCESO_MODIFICADO = "vacante.acceso_modificado"
    VACANTE_ACCESO_REVOCADO = "vacante.acceso_revocado"
    VACANTE_PERMISO_SENSIBLE = "vacante.permiso_sensible_cambiado"
    VACANTE_TRANSFERIDA = "vacante.transferida"
    TRANSFERENCIA_MASIVA = "transferencia_masiva.completada"
    DOCUMENTO_CARGADO = "documento.cargado"
    DOCUMENTO_RECHAZADO = "documento.rechazado"
    DOCUMENTO_DESCARGADO = "documento.descargado"
    DOCUMENTO_NO_DISPONIBLE = "documento.no_disponible"
    DOCUMENTO_ELIMINADO = "documento.eliminado"
    ALMACENAMIENTO_CONCILIADO = "almacenamiento.conciliado"
    IA_CLAVE_REGISTRADA = "ia.clave_registrada"
    IA_CLAVE_REVOCADA = "ia.clave_revocada"
    IA_CONEXION_PROBADA = "ia.conexion_probada"
    IA_PROVEEDOR_ACTUALIZADO = "ia.proveedor_actualizado"
    IA_MODELO_ASIGNADO = "ia.modelo_asignado"
    IA_PRECIO_ACTUALIZADO = "ia.precio_actualizado"
    PERFIL_VERSION_CREADA = "perfil.version_creada"
    PERFIL_EXTRAIDO_CON_IA = "perfil.extraido_con_ia"
    PERFIL_LEIDO_DEL_FORMATO = "perfil.leido_del_formato"
    PROMPT_CRITERIOS_PROPUESTOS = "prompt.criterios_propuestos"
    PROMPT_GENERADO = "prompt.generado"
    PROMPT_EDITADO = "prompt.editado"
    PROMPT_ENVIADO_A_REVISION = "prompt.enviado_a_revision"
    PROMPT_DEVUELTO = "prompt.devuelto_a_borrador"
    PROMPT_APROBADO = "prompt.aprobado"
    PROMPT_ARCHIVADO = "prompt.archivado"
    PROMPT_DUPLICADO = "prompt.duplicado"
    EXPORTACION_GENERADA = "exportacion.generada"
    LOTE_CV_CREADO = "lote_cv.creado"
    LOTE_CV_TERMINADO = "lote_cv.terminado"
    LOTE_CV_REANUDADO = "lote_cv.reanudado"
    LOTE_CV_CANCELADO = "lote_cv.cancelado"
    ETAPAS_VERSION_CREADA = "etapas.version_creada"
    CONVOCATORIA_ABIERTA = "convocatoria.abierta"
    CONVOCATORIA_CERRADA = "convocatoria.cerrada"
    POSTULACIONES_CREADAS = "postulacion.creada"
    POSTULACION_MOVIDA = "postulacion.movida"
    POSTULACION_ESTADO_CAMBIADO = "postulacion.estado_cambiado"
    POSTULACION_ANOTADA = "postulacion.anotada"
    RESULTADO_FINAL_REGISTRADO = "postulacion.resultado_registrado"
    RESULTADO_FINAL_ANULADO = "postulacion.resultado_anulado"
    REPORTE_GENERADO = "reporte.generado"
    REPORTE_DESCARGADO = "reporte.descargado"
    CANDIDATO_ACTUALIZADO = "candidato.actualizado"
    BANCO_CREADO = "banco_preguntas.creado"
    BANCO_ACTUALIZADO = "banco_preguntas.actualizado"
    BANCO_PREGUNTAS_PROPUESTAS = "banco_preguntas.preguntas_propuestas"
    LLAMADA_ABIERTA = "llamada.abierta"
    LLAMADA_GUARDADA = "llamada.guardada"
    LLAMADA_CERRADA = "llamada.cerrada"
    LLAMADA_ANALIZADA = "llamada.analizada"
    FORMULARIO_VERSION_CREADA = "formulario.version_creada"
    EVALUACION_CREADA = "evaluacion.creada"
    EVALUACION_ACTUALIZADA = "evaluacion.actualizada"
    EVALUACION_RESUMIDA = "evaluacion.resumida"
    ESTUDIO_DIGITALIZADO = "estudio.digitalizado"
    EXPEDIENTE_SINTETIZADO = "expediente.sintetizado"


@dataclass(frozen=True)
class AuditEvent:
    id: uuid.UUID
    occurred_at: datetime
    action: str
    result: AuditResult
    actor_user_id: uuid.UUID | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    ip: str | None = None
    correlation_id: str | None = None
    # Nunca contraseñas, claves ni contenido de documentos.
    details: dict[str, Any] = field(default_factory=dict)


class AuditRepository(Protocol):
    def add(self, event: AuditEvent) -> None: ...

    def list(
        self, *, action: str | None, offset: int, limit: int
    ) -> tuple[list[AuditEvent], int]: ...
