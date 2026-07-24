SELECT
    rff.id_respuesta,
    rff.id_usuario_firmador,
    rff.estado           AS estado_firma,
    rff.fecha_envio      AS fecha_envio_firma,
    rff.fecha_firma,
    rff.observacion      AS observacion_firma,
    uf.nombres           AS nombre_firmador,
    uf.apellidos         AS apellido_firmador,
    uf.email             AS email_firmador,
    uf.cargo             AS cargo_firmador
FROM respuesta_formulario_firmas rff
LEFT JOIN usuario uf ON uf.id = rff.id_usuario_firmador
WHERE rff.id_respuesta = ANY(%(response_ids)s)
ORDER BY rff.id_respuesta;
