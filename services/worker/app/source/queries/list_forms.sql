-- Formularios con respuestas para la empresa.
SELECT DISTINCT
    f.id      AS id_formulario,
    f.nombre  AS nombre_formulario,
    f.codigo  AS codigo_formulario,
    f.escala  AS escala_formulario,
    f.logo    AS logo_formulario
FROM respuesta_formulario rf
INNER JOIN formulario f ON f.id = rf.id_formulario
WHERE rf.id_empresa = %(company_id)s
ORDER BY f.nombre;
