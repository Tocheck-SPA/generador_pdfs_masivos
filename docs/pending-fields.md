# Campos de la fuente por confirmar y puntos de extensión

Estos elementos NO están confirmados en el esquema de la fuente. El código los **aísla**,
maneja su ausencia con valores nulos y **no bloquea el MVP**. Aquí se documenta dónde
ajustarlos cuando se validen con datos reales.

| Tema | Estado | Dónde se aísla / se extiende |
|------|--------|------------------------------|
| **Orden de ítems** | RESUELTO con datos reales: se ordena por `i.id`, que coincide con el orden del informe oficial de ToCheck. | `queries/response_questions.sql` (`ORDER BY ... i.id`). |
| **Mapeo respuesta → Cumple/No Cumple y cumplimiento por ítem** | RESUELTO: fórmula oficial de ToCheck (por `tipo_resp`) + cumplimiento = Σ `rp.ponderacion` / Σ `p.ponderacion`, nota obtenida = peso del ítem × cumplimiento. Coincide exactamente con el informe real (p. ej. INSTALACIONES 12,6 / 84 %). | `app/reports/compliance.py`; `app/reports/builder.py` (agregados por ítem). |
| **Base de imágenes de la fuente** | RESUELTO para la fuente MySQL: las rutas relativas de `respuesta_imagenes.path` se descargan desde `https://tocheck.s3.amazonaws.com` y se convierten a `data URI` antes de renderizar el PDF. Los logos de empresa usan su base pública separada. | `app/source/asset_resolver.py`; `SOURCE_ASSET_BASE_URL` / `SOURCE_LOGO_BASE_URL` (configurables) / `SOURCE_ASSET_LOCAL_DIR` (fallback local). |
| **Numeración exacta de preguntas (ítem.posición)** | Aproximada: `ip.orden` viene NULL, se numera por posición dentro del ítem (coincide en la mayoría; puede diferir en ±1 respecto de ToCheck). | `app/reports/builder.py` (asignación de `number`). |
| **Mapa "Ubicación"** | No implementado (requiere proveedor de mapas + token). El informe oficial muestra un mapa Mapbox. | Punto de extensión en `templates/report.html.j2`. |
| **Imagen de firma dibujada** | La consulta disponible no expone la ruta de la firma. Se muestran nombre, estado, fecha y observación. | `app/reports/model.py` → `SignatureData` (punto de extensión `signature_image_data_uri`); plantilla `templates/report.html.j2` (nota al pie de "Firmas"). |
| **Autenticación / base de imágenes** | Las rutas pueden ser URL, key S3, ruta relativa o nombre. Las rutas relativas se resuelven contra la base pública S3 configurable; no se requieren credenciales para los objetos públicos validados. | `app/source/asset_resolver.py` (`resolve_remote_asset`, parámetro `asset_base_url`); `MySQLSourceRepository`. |
| **`id_formulario_instancia` de tickets** | La consulta original lo relacionaba con `rf.id_formulario`. Se deja aislado para ajustarlo. | `queries/tickets.sql` + `PostgresSourceRepository.get_tickets`. La regla NO está incrustada en la plantilla. |
| **Estado final / incompleto de la respuesta** | No confirmado. No se filtra por estado en el MVP. | `queries/list_response_ids.sql` (agregar filtro cuando se conozca el campo). |
| **Campos `updated_at` en la fuente** | No confirmados. La caché de PDF **no** depende de `source_updated_at`. | `app/reports/hashing.py` (hash del contenido visible). |
| **Formato de `lista_opciones_observacion_respuesta.opciones`** | Puede ser texto, JSON o separado por comas. | `app/reports/observation_options.py` (`parse_observation_options`, tolerante). |
| **Tipos de respuesta** | `tipo_pregunta` / `tipo_resp` con formato variable. El modelo acepta `str | bool | int | float | list`. | `app/reports/model.py` → `ReportQuestion.answer`; badge en la plantilla. |

## Estrategia de caché sin `updated_at`

La clave lógica de reutilización de PDF es:

```
response_id + source_payload_hash + PDF_TEMPLATE_VERSION + PDF_GENERATOR_VERSION
```

`source_payload_hash` es un SHA-256 del `ReportData` serializado de forma determinista,
**excluyendo** binarios de imágenes (se representan por su ruta de origen) y URLs
prefirmadas. Si cambia cualquier dato visible, cambia el hash y se regenera el PDF.
La consulta de reutilización está en `app/database/jobs.py::cache_lookup`.
