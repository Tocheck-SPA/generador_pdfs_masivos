-- Empresas y formularios que tienen respuestas dentro de la ventana de ingesta.
SELECT DISTINCT
    e.id       AS id_empresa,
    e.empresa  AS nombre_empresa,
    e.logo     AS logo_empresa,
    f.id       AS id_formulario,
    f.nombre   AS nombre_formulario,
    f.codigo   AS codigo_formulario,
    f.escala   AS escala_formulario,
    f.logo     AS logo_formulario
FROM respuesta_formulario rf
INNER JOIN empresa e ON e.id = rf.id_empresa
INNER JOIN formulario f ON f.id = rf.id_formulario
WHERE rf.fecha_hora >= %(date_from)s
  AND rf.fecha_hora < %(date_to_exclusive)s
  AND rf.id_empresa = %(company_id)s
ORDER BY e.empresa, f.nombre;
