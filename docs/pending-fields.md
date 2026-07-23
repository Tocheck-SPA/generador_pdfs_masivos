# Campos de la fuente por confirmar y puntos de extensión

Estos elementos NO están confirmados en el esquema de la fuente. El código los **aísla**,
maneja su ausencia con valores nulos y **no bloquea el MVP**. Aquí se documenta dónde
ajustarlos cuando se validen con datos reales.

| Tema | Estado | Dónde se aísla / se extiende |
|------|--------|------------------------------|
| **Orden explícito de ítems** | No confirmado. Se usa el **orden de aparición** en el resultado (la consulta ordena por `i.ponderacion, ip.orden`). No se asume que la ponderación sea el orden. | `app/reports/builder.py` (comentario en `section_order`); `queries/response_questions.sql` (cláusula `ORDER BY`). |
| **Imagen de firma dibujada** | La consulta disponible no expone la ruta de la firma. Se muestran nombre, estado, fecha y observación. | `app/reports/model.py` → `SignatureData` (punto de extensión `signature_image_data_uri`); plantilla `templates/report.html.j2` (nota al pie de "Firmas"). |
| **Autenticación / base de imágenes** | Las rutas pueden ser URL, key S3, ruta relativa o nombre. Se resuelven URLs http(s); S3/relativas requieren base y credenciales. | `app/source/asset_resolver.py` (`resolve_remote_asset`, parámetro `asset_base_url`); en `PostgresSourceRepository._asset_base_url`. |
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
