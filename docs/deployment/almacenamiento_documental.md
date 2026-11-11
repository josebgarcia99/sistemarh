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
