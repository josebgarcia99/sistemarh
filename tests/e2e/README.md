# Recorridos completos en navegador

Cinco recorridos con Playwright que usan la aplicación como lo haría una persona: inician sesión, pulsan botones, descargan archivos y comprueban lo que aparece en pantalla.

| Recorrido | Qué cubre |
| --- | --- |
| `recorrido_evaluacion_cv.py` | Lote de CV, resultados, Excel y ZIP, acceso de lectura, consumo de IA, móvil |
| `recorrido_ayudas_ia.py` | Perfil llenado con IA y propuestas de mejora a los criterios |
| `recorrido_reclutamiento.py` | Candidatos, etapas, expediente, llamadas, bancos de preguntas, versiones del proceso |
| `recorrido_evaluaciones.py` | Prueba técnica, entrevista, psicometría, estudio, síntesis y datos sensibles |
| `recorrido_indicadores.py` | Resultado final, reapertura, tablero, histórico, Excel de reportes y permisos |

```bash
cd apps/web && npm ci && npm run build && cd ../..
python tests/e2e/run.py
```

Cada recorrido se ejecuta sobre el **modo demostración** recién arrancado: datos en memoria, IA simulada y documentos ficticios. No prueban SQL Server ni proveedores reales.

Al final de cada uno se imprime la lista de respuestas de error que vio el navegador. Algunas son esperadas: el recorrido provoca validaciones a propósito (por ejemplo, registrar un resultado sin motivo). Un recorrido falla cuando alguna comprobación no se cumple, no por esa lista.

Los guiones son compactos, con varias acciones por línea; no siguen el estilo del resto del código.
