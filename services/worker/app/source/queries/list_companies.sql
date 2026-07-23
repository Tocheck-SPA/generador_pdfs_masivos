-- Empresas con al menos una respuesta.
SELECT DISTINCT
    e.id       AS id_empresa,
    e.empresa  AS nombre_empresa,
    e.logo     AS logo_empresa
FROM respuesta_formulario rf
INNER JOIN empresa e ON e.id = rf.id_empresa
ORDER BY e.empresa;
