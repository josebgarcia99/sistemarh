import { z } from "zod";
import { apiFetch } from "./client";

const auditEventSchema = z.object({
  id: z.string(),
  occurred_at: z.string(),
  action: z.string(),
  result: z.enum(["PERMITIDO", "DENEGADO", "FALLIDO"]),
  actor_user_id: z.string().nullable(),
  actor_name: z.string().nullable(),
  resource_type: z.string().nullable(),
  resource_id: z.string().nullable(),
  ip: z.string().nullable(),
  correlation_id: z.string().nullable(),
  details: z.record(z.string(), z.unknown()),
});
export type AuditEvent = z.infer<typeof auditEventSchema>;

const auditPageSchema = z.object({
  items: z.array(auditEventSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
});
export type AuditPage = z.infer<typeof auditPageSchema>;

/** Acciones que la API registra hoy, con su nombre para mostrar. */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  "sesion.inicio": "Inicio de sesión",
  "sesion.inicio_fallido": "Inicio de sesión fallido",
  "sesion.cierre": "Cierre de sesión",
  "acceso.denegado": "Acceso denegado",
  "usuario.creado": "Usuario creado",
  "usuario.actualizado": "Usuario actualizado",
  "usuario.contrasena_restablecida": "Contraseña restablecida",
  "usuario.desactivado": "Usuario dado de baja",
  "usuario.activado": "Usuario reactivado",
  "vacante.creada": "Vacante creada",
  "vacante.actualizada": "Vacante actualizada",
  "vacante.estado_cambiado": "Cambio de estado de vacante",
  "vacante.compartida": "Vacante compartida",
  "vacante.acceso_modificado": "Tipo de acceso modificado",
  "vacante.acceso_revocado": "Acceso revocado",
  "vacante.permiso_sensible_cambiado": "Permiso de documentos sensibles",
  "vacante.transferida": "Vacante transferida",
  "transferencia_masiva.completada": "Baja con transferencia",
  "documento.cargado": "Documento cargado",
  "documento.rechazado": "Documento rechazado",
  "documento.descargado": "Documento descargado",
  "documento.no_disponible": "Documento no disponible",
  "documento.eliminado": "Documento eliminado",
  "almacenamiento.conciliado": "Conciliación del almacenamiento",
  "ia.clave_registrada": "API key registrada",
  "ia.clave_revocada": "API key revocada",
  "ia.conexion_probada": "Prueba de conexión con proveedor de IA",
  "ia.proveedor_actualizado": "Proveedor de IA actualizado",
  "ia.modelo_asignado": "Modelo de IA asignado",
  "perfil.version_creada": "Versión de perfil de puesto",
  "prompt.generado": "Prompt generado",
  "prompt.editado": "Prompt editado",
  "prompt.enviado_a_revision": "Prompt enviado a revisión",
  "prompt.devuelto_a_borrador": "Prompt devuelto a borrador",
  "prompt.aprobado": "Prompt aprobado",
  "prompt.archivado": "Prompt archivado",
  "prompt.duplicado": "Prompt duplicado",
};

export function listAuditEvents(
  params: { action?: string; page: number; pageSize: number },
  signal?: AbortSignal,
): Promise<AuditPage> {
  return apiFetch("/audit/events", {
    schema: auditPageSchema,
    query: { action: params.action, page: params.page, page_size: params.pageSize },
    signal,
  });
}
