USE smart_marketing;

SELECT 'campanhas' AS tabela, COUNT(*) AS registros FROM campanhas
UNION ALL
SELECT 'leads', COUNT(*) FROM leads;

SELECT id, COUNT(*) AS ocorrencias
FROM campanhas GROUP BY id HAVING COUNT(*) > 1;

SELECT id, COUNT(*) AS ocorrencias
FROM leads GROUP BY id HAVING COUNT(*) > 1;

SELECT * FROM vw_resultados_canal ORDER BY receita DESC;
SELECT * FROM vw_qualidade_dados;
SELECT * FROM vw_ultima_atualizacao;

