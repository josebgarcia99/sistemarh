# Almacenamiento documental

> Origen: propuesta de arquitectura aprobada el 10 de noviembre de 2026.
> Este archivo es la copia de trabajo del repositorio y se actualiza en cada fase.

## 8. Almacenamiento físico persistente

Cada archivo se guarda una sola vez en el disco privado de tu servidor, con nombre UUID, y SQL Server registra qué es y dónde está. Ningún archivo tiene URL pública.

```
<STORAGE_ROOT>/                      configurable; ejemplo /srv/reclutamiento/storage/
  private/<tipo>/<aa>/<bb>/<uuid>    cv, job_profiles, psychometrics, technical_tests,
                                     socioeconomic_studies, attachments
  generated/<tipo>/<aa>/<bb>/<uuid>  excel, zip, reports
  processing/temporary/<uuid>.part   recepción en curso
  quarantine/                        archivos rechazados o huérfanos en revisión
```

Los niveles `<aa>/<bb>` son los primeros caracteres del UUID y evitan carpetas con miles de archivos. Ningún nombre de candidato aparece en el disco.

**Referencia de almacenamiento.** SQL Server guarda una clave lógica relativa, por ejemplo `private/cv/3f/a9/<uuid>`, y el nombre del backend (`local`). La ruta absoluta solo existe en la configuración. Cambiar a un almacén compatible con S3 significaría añadir otro adaptador de `FileStorageService`, sin tocar reglas de negocio. MinIO no se despliega.

**Protocolo de escritura recuperable.** El disco y SQL Server no comparten transacción, así que cada archivo pasa por estados explícitos:

1. Se crea el registro en `file_assets` con estado `RECIBIENDO` y su UUID.
2. El archivo se escribe en la zona temporal mientras se calculan tamaño y SHA-256.
3. Se valida: extensión permitida, tipo real por contenido, apertura estructural y análisis antivirus local.
4. Se sincroniza a disco y se mueve de forma atómica a su ubicación definitiva.
5. El registro pasa a `CONFIRMADO` con hash, tamaño y clave. Solo entonces la API responde que se guardó.
6. Si algo falla, el registro queda en `RECHAZADO` o `FALLIDO` y el temporal se limpia.

Un proceso nocturno de conciliación detecta tres casos: registros atascados en `RECIBIENDO`, archivos sin registro (huérfanos, que van a cuarentena y a un reporte, nunca se borran solos) y registros `CONFIRMADO` sin archivo (incidente crítico). También recalcula hashes por muestreo.

**Persistencia.** El disco se monta en los contenedores de la API y del worker como ruta del servidor. Nada definitivo vive dentro de un contenedor, así que reinicios, actualizaciones y despliegues no afectan los documentos.

**Duplicados.** Se detectan por SHA-256 dentro de la misma convocatoria y se reportan. No se comparte un mismo archivo físico entre postulaciones, para que retención y eliminación sean independientes.

**Conservación.** Ningún documento se borra al terminar su análisis. Cada uno lleva su fecha de retención según la política aprobada. El borrado seguro elimina archivo, extracciones derivadas y referencias, y queda registrado en `privacy_requests`.

## Lo construido en la Fase 3

Estado al 11 de noviembre de 2026. Probado con archivos sintéticos sobre un disco local y el motor de pruebas; **falta probarlo con SQL Server, Docker y ClamAV reales**.

### Qué necesita Sistemas

| Elemento | Detalle |
| --- | --- |
| Carpeta de documentos | Una carpeta del servidor, fuera del código y de cualquier directorio público, montada en los contenedores de la API y del worker. Se indica en `RECLU_STORAGE_ROOT` |
| La carpeta debe existir | Si no existe al arrancar, la API se detiene con un error. Es intencional: evita guardar documentos dentro de un contenedor que se pierde al recrearlo |
| Permisos | Solo el usuario del sistema que ejecuta la API y el worker debe poder leer y escribir en ella |
| Espacio | Las cargas se rechazan cuando el espacio libre baja de `RECLU_STORAGE_MIN_FREE_BYTES` (1 GB por omisión) |
| Antivirus | `RECLU_ANTIVIRUS_MODE=clamd` con un ClamAV en el propio servidor (`RECLU_CLAMD_HOST`, `RECLU_CLAMD_PORT`), o `disabled`. En producción hay que elegir de forma expresa. Si está en `clamd` y el antivirus no responde, la carga se rechaza: no se guarda nada sin analizar |
| Proxy inverso | Debe permitir cuerpos de petición de al menos 20 MB hacia `/api/` (en Nginx, `client_max_body_size 25m`) |
| Cifrado | Cifrado del volumen a cargo de Sistemas (decisión 8) |

### Qué acepta

PDF, DOCX, DOC, JPG y PNG, hasta 20 MB (`RECLU_MAX_UPLOAD_BYTES`). Se comprueba el contenido real, no solo la extensión: un ejecutable renombrado a `.pdf` se rechaza. Los documentos de Word con macros se rechazan. El nombre original se sanea y solo se usa para mostrarlo; en el disco el archivo se llama como su identificador.

### Rutas de la API

| Ruta | Quién |
| --- | --- |
| `GET /api/v1/vacancies/{id}/files` | Acceso de lectura a la vacante |
| `POST /api/v1/vacancies/{id}/files?document_type=…&filename=…` (el cuerpo es el archivo) | Acceso de colaboración |
| `GET /api/v1/files/{id}` y `GET /api/v1/files/{id}/download` | Acceso de lectura; permiso adicional si es sensible |
| `POST /api/v1/files/{id}/deletion` | Administrador, con motivo |
| `GET /api/v1/storage/status` y `POST /api/v1/storage/reconciliation` | Administrador |

### Conciliación

```bash
python -m app.cli storage-check --verify-hashes sample   # none | sample | all
```

Devuelve código 0 si el disco y la base coinciden y 2 si no. Hace lo descrito arriba: cierra cargas interrumpidas, manda a cuarentena los archivos sin registro (nunca los borra), reporta los registros sin archivo, termina los borrados pendientes y recalcula hashes (`sample` revisa los 200 documentos más antiguos; `all`, todos). **Todavía no se ejecuta sola cada noche:** hay que programarla (por ejemplo con `cron` sobre el contenedor de la API) o lanzarla desde la API.

### Pendiente en esta área

- **Documentos sensibles.** Psicometría y estudios socioeconómicos no se aceptan todavía: la decisión 8 exige cifrarlos archivo por archivo y ese cifrado se construye en la Fase 4, junto con la custodia de la clave maestra. El permiso adicional ya funciona y está probado con datos sintéticos.
- **Versiones de un documento** (`file_versions`): se crean cuando exista el primer documento versionado (perfiles de puesto, Fase 4).
- **Fecha de retención:** la columna existe, pero no se aplica ninguna política hasta que el área legal la defina.
- **Vista previa de PDF:** hoy solo hay descarga.
- **Pantalla de administración** del almacenamiento: hoy se consulta por la API o por comando.
- **Duplicados:** se detectan por vacante; pasarán a ser por convocatoria cuando existan (Fase 5).
