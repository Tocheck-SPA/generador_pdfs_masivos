-- IDs de respuesta para crear los report_job_items.
SELECT DISTINCT
    rf.id_respuesta,
    rf.id_empresa,
    rf.id_formulario,
    rf.id_punto_evaluacion,
    rf.id_entidad_auditable,
    rf.fecha_hora
FROM respuesta_formulario rf
WHERE rf.id_empresa = %(company_id)s
  AND rf.id_formulario = %(form_id)s
  AND rf.fecha_hora >= %(date_from)s
  AND rf.fecha_hora <  %(date_to_exclusive)s
  AND (
    %(include_all_points)s = TRUE
    OR rf.id_punto_evaluacion = ANY(%(evaluation_point_ids)s)
  )
ORDER BY rf.fecha_hora, rf.id_respuesta;
