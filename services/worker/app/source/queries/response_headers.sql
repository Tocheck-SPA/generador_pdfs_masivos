-- Una fila por respuesta. Sin preguntas/fotos/firmas/tickets (evita multiplicación).
SELECT
    rf.id_respuesta,
    rf.id_empresa,
    rf.id_formulario,
    rf.id_punto_evaluacion,
    rf.id_entidad_auditable,
    rf.id_usuario,
    rf.fecha_hora,
    rf.fecha_hora_inicio,
    rf.ponderacion            AS ponderacion_total,
    rf.observacion            AS observacion_general,
    rf.coordenada,
    rf.timing,
    f.nombre                  AS nombre_formulario,
    f.codigo                  AS codigo_formulario,
    f.escala                  AS escala_formulario,
    f.logo                    AS logo_formulario,
    e.empresa                 AS nombre_empresa,
    e.logo                    AS logo_empresa,
    pe.nombre_punto,
    pe.direccion_punto,
    pe.pais_punto,
    z.zona                    AS nombre_zona,
    ea.nombre                 AS nombre_entidad_auditable,
    ea.codigo_identificador   AS codigo_entidad_auditable,
    ea.correo                 AS correo_entidad_auditable,
    ea.tipo                   AS tipo_entidad_auditable,
    u.nombres                 AS nombre_usuario,
    u.apellidos               AS apellido_usuario,
    u.cargo                   AS cargo_usuario
FROM respuesta_formulario rf
INNER JOIN formulario f ON f.id = rf.id_formulario
INNER JOIN empresa e    ON e.id = rf.id_empresa
LEFT JOIN punto_evaluacion pe ON pe.id = rf.id_punto_evaluacion
LEFT JOIN zona z              ON z.id = pe.id_zona
LEFT JOIN entidad_auditable ea ON ea.id = rf.id_entidad_auditable
LEFT JOIN usuario u           ON u.id = rf.id_usuario
WHERE rf.id_respuesta = ANY(%(response_ids)s);
