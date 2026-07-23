# Decisiones técnicas y consultas SQL

## Decisiones clave

1. **Consultas divididas, no monolítica.** La consulta grande multiplica filas
   (preguntas × fotos × firmas × adicionales × tickets). Se dividió en 12 consultas
   específicas y el `builder` agrupa en memoria. Ver [pending-fields.md](pending-fields.md).
2. **`SourceRepository` aislado** con dos implementaciones (`fixture`, `postgres`). El
   generador de PDF no conoce SQL ni nombres de tablas.
3. **Procesador desacoplado de Neon.** `app/jobs/processor.py::process_job` recibe
   repositorio/almacenamiento/correo y callbacks; se prueba de punta a punta con fixtures.
   `app/jobs/runner.py` lo envuelve con claim/heartbeat/persistencia.
4. **Fixtures compartidos** (`/fixtures/*.json`) entre web (conteo/catálogos) y worker
   (PDF), evitando divergencias en desarrollo.
5. **Store dual en la web** detrás de `getStore()`: memoria + simulador (sin DB) y
   Postgres (`pgStore`). Permite demo de la UI sin servicios.
6. **Fecha final siempre exclusiva.** La UI toma un `dateTo` inclusivo y lo convierte a
   `date_to_exclusive = dateTo + 1 día`. Nunca se usa `23:59:59`.
7. **Idempotencia de correo** vía `email_deliveries.idempotency_key` y `claim_email_send`
   (inserta fila `sending` con `ON CONFLICT DO NOTHING`). El claim de jobs excluye los que
   ya tienen correo `sent`.
8. **Minimización de datos:** RUT nunca se persiste ni se muestra; coordenadas ocultas por
   defecto; logs JSON filtran claves sensibles y URLs firmadas.

## Consultas SQL implementadas (`services/worker/app/source/queries/`)

| Archivo | Propósito | Notas |
|---------|-----------|-------|
| `list_companies.sql` | Empresas con respuestas | `DISTINCT` sobre `respuesta_formulario` |
| `list_forms.sql` | Formularios con respuestas de la empresa | parámetro `company_id` |
| `list_evaluation_points.sql` | Puntos con respuestas en rango | fecha final **exclusiva** |
| `count_responses.sql` | Conteo liviano | `include_all_points` + `ANY(evaluation_point_ids)` |
| `list_response_ids.sql` | IDs para crear `report_job_items` | orden por fecha, id |
| `response_headers.sql` | 1 fila por respuesta | sin preguntas/fotos/firmas |
| `response_questions.sql` | 1 fila por `id_respuesta_pregunta` | sin fotos; `ORDER BY` determinista |
| `response_images.sql` | Fotos por respuesta/pregunta | agrupadas por el builder |
| `response_signatures.sql` | Firmas (metadata) | sin imagen de firma |
| `additional_answers.sql` | Preguntas adicionales | separadas de las normales |
| `observation_options.sql` | Opciones de observación | formato tolerante |
| `tickets.sql` | Tickets por respuesta | regla `id_formulario_instancia` aislada |

Todas: parametrizadas, sin interpolación, aceptan lotes `ANY(%(response_ids)s)`,
solo lectura, `statement_timeout` configurable, sin columnas innecesarias.

## Estados de trabajo

`pending · processing · fetching_source_data · generating_pdfs · creating_bundle ·
uploading · sending_email · completed · completed_with_warnings · failed ·
cancel_requested · cancelled` — con etiquetas visibles en español (ver `apps/web/src/lib/status.ts`).

## Manejo de errores

Cada respuesta se procesa de forma independiente. Si una falla, se marca el ítem como
`failed`, se registra el evento y se continúa. Si algunas funcionan → `completed_with_warnings`;
si ninguna → `failed` (no se envía paquete vacío). Nunca se muestran stack traces en la UI.

Códigos: `SOURCE_DATABASE_ERROR, SOURCE_QUERY_TIMEOUT, SOURCE_DATA_INVALID,
IMAGE_DOWNLOAD_ERROR, IMAGE_FORMAT_ERROR, PDF_RENDER_ERROR, STORAGE_UPLOAD_ERROR,
ZIP_CREATION_ERROR, EMAIL_SEND_ERROR, JOB_CANCELLED, UNKNOWN_ERROR`.
