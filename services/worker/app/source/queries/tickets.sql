-- Regla id_formulario_instancia AISLADA aquí para poder ajustarla con datos reales.
SELECT
    t.id_respuesta,
    t.id_ticket,
    t.id_formulario_instancia,
    t.titulo_ticket,
    t.ticket_estado,
    t.prioridad,
    t.created_at
FROM ticket t
WHERE t.id_respuesta = ANY(%(response_ids)s)
ORDER BY t.id_respuesta, t.created_at, t.id_ticket;
