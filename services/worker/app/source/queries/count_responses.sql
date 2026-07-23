-- Conteo liviano. include_all_points controla el filtro de puntos.
SELECT
    COUNT(DISTINCT rf.id_respuesta)          AS total_responses,
    COUNT(DISTINCT rf.id_punto_evaluacion)   AS total_evaluation_points
FROM respuesta_formulario rf
WHERE rf.id_empresa = %(company_id)s
  AND rf.id_formulario = %(form_id)s
  AND rf.fecha_hora >= %(date_from)s
  AND rf.fecha_hora <  %(date_to_exclusive)s
  AND (
    %(include_all_points)s = TRUE
    OR rf.id_punto_evaluacion = ANY(%(evaluation_point_ids)s)
  );
