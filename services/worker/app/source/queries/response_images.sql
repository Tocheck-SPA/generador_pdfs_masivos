SELECT
    ri.id_respuesta,
    ri.id_pregunta,
    ri.path
FROM respuesta_imagenes ri
WHERE ri.id_respuesta = ANY(%(response_ids)s)
ORDER BY ri.id_respuesta, ri.id_pregunta, ri.path;
