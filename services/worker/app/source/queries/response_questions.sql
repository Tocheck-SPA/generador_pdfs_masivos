-- Una fila por id_respuesta_pregunta. Sin fotografías (van en consulta aparte).
SELECT
    rp.id_respuesta,
    rp.id                     AS id_respuesta_pregunta,
    rp.id_pregunta,
    rp.id_item,
    rp.respuesta              AS valor_respuesta,
    rp.observacion            AS observacion_respuesta,
    rp.tipo_resp,
    rp.ponderacion            AS ponderacion_respuesta,
    rp.ticket                 AS genera_ticket_respuesta,
    p.enunciado               AS enunciado_pregunta,
    p.tipo_pregunta,
    p.observacion             AS requiere_observacion_pregunta,
    p.foto                    AS requiere_foto_pregunta,
    p.genera_ticket,
    i.nombre                  AS nombre_item,
    i.ponderacion             AS ponderacion_item,
    ip.orden                  AS orden_pregunta,
    tp.descripcion            AS tooltip_pregunta
FROM respuesta_pregunta rp
LEFT JOIN pregunta p ON p.id = rp.id_pregunta
LEFT JOIN item i     ON i.id = rp.id_item
LEFT JOIN item_pregunta ip ON ip.id_pregunta = p.id AND ip.id_item = i.id
LEFT JOIN tooltips_pregunta tp ON tp.id_pregunta = p.id
WHERE rp.id_respuesta = ANY(%(response_ids)s)
ORDER BY rp.id_respuesta, i.ponderacion, ip.orden, rp.id;
