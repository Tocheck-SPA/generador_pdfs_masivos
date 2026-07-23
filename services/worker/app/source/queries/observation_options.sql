SELECT
    lor.id_respuesta,
    lor.id_pregunta,
    lor.titulo_lista,
    lor.opciones
FROM lista_opciones_observacion_respuesta lor
WHERE lor.id_respuesta = ANY(%(response_ids)s)
ORDER BY lor.id_respuesta, lor.id_pregunta;
