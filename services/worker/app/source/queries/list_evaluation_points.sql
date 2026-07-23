-- Puntos de evaluación con respuestas en el rango (fecha final EXCLUSIVA).
SELECT DISTINCT
    pe.id             AS id_punto_evaluacion,
    pe.nombre_punto,
    pe.direccion_punto,
    pe.pais_punto,
    z.zona            AS nombre_zona
FROM respuesta_formulario rf
LEFT JOIN punto_evaluacion pe ON pe.id = rf.id_punto_evaluacion
LEFT JOIN zona z ON z.id = pe.id_zona
WHERE rf.id_empresa = %(company_id)s
  AND rf.id_formulario = %(form_id)s
  AND rf.fecha_hora >= %(date_from)s
  AND rf.fecha_hora <  %(date_to_exclusive)s
  AND pe.id IS NOT NULL
ORDER BY pe.nombre_punto;
