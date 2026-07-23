SELECT
    ra.id_respuesta,
    pa.id            AS id_pregunta_adicional,
    pa.pregunta,
    pa.pregunta_texto,
    ra.respuesta_adicional_boolean
FROM pregunta_adicional pa
INNER JOIN respuesta_adicional ra ON ra.id_pregunta_adicional = pa.id
WHERE ra.id_respuesta = ANY(%(response_ids)s)
ORDER BY ra.id_respuesta, pa.id;
