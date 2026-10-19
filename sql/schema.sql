-- Smart Marketing Analytics | esquema MySQL 8.0+
-- Idempotente para instalação nova. Não exclui dados existentes.
CREATE DATABASE IF NOT EXISTS smart_marketing
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_marketing;

CREATE TABLE IF NOT EXISTS campanhas (
  id VARCHAR(20) NOT NULL,
  data DATE NOT NULL,
  canal VARCHAR(80) NOT NULL,
  campanha VARCHAR(150) NOT NULL,
  investimento DECIMAL(12,2) NOT NULL,
  impressoes INT NOT NULL,
  cliques INT NOT NULL,
  leads INT NOT NULL,
  vendas INT NOT NULL,
  receita DECIMAL(12,2) NOT NULL,
  PRIMARY KEY (id),
  INDEX ix_campanhas_canal_data (canal, data),
  CONSTRAINT ck_campanhas_metricas_nao_negativas CHECK (
    investimento >= 0 AND impressoes >= 0 AND cliques >= 0 AND
    leads >= 0 AND vendas >= 0 AND receita >= 0
  ),
  CONSTRAINT ck_campanhas_funil CHECK (
    cliques <= impressoes AND leads <= cliques AND vendas <= leads
  )
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS leads (
  id VARCHAR(20) NOT NULL,
  data DATE NOT NULL,
  empresa VARCHAR(150) NOT NULL,
  canal VARCHAR(80) NOT NULL,
  interesse VARCHAR(150) NOT NULL,
  status VARCHAR(80) NOT NULL,
  PRIMARY KEY (id),
  INDEX ix_leads_canal_data (canal, data),
  INDEX ix_leads_status (status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS etl_execucoes (
  run_id CHAR(36) NOT NULL,
  iniciado_em DATETIME(6) NOT NULL,
  finalizado_em DATETIME(6) NULL,
  status VARCHAR(20) NOT NULL,
  source_hash CHAR(64) NOT NULL,
  campanhas_processadas INT NULL,
  leads_processados INT NULL,
  campanhas_inseridas INT NULL,
  campanhas_atualizadas INT NULL,
  leads_inseridos INT NULL,
  leads_atualizados INT NULL,
  mensagem VARCHAR(500) NULL,
  PRIMARY KEY (run_id),
  INDEX ix_etl_execucoes_status_data (status, iniciado_em)
) ENGINE=InnoDB;

CREATE OR REPLACE VIEW vw_resultados_canal AS
SELECT
  canal,
  SUM(investimento) AS investimento,
  SUM(impressoes) AS impressoes,
  SUM(cliques) AS cliques,
  SUM(leads) AS leads,
  SUM(vendas) AS vendas,
  SUM(receita) AS receita,
  SUM(cliques) / NULLIF(SUM(impressoes), 0) AS ctr,
  SUM(investimento) / NULLIF(SUM(cliques), 0) AS cpc,
  SUM(investimento) / NULLIF(SUM(leads), 0) AS cpl,
  SUM(investimento) / NULLIF(SUM(vendas), 0) AS cpa,
  SUM(vendas) / NULLIF(SUM(leads), 0) AS taxa_conversao,
  SUM(receita) / NULLIF(SUM(investimento), 0) AS roas
FROM campanhas
GROUP BY canal;

CREATE OR REPLACE VIEW vw_ultima_atualizacao AS
SELECT
  run_id,
  iniciado_em,
  finalizado_em,
  status,
  source_hash,
  campanhas_processadas,
  leads_processados,
  mensagem
FROM etl_execucoes
WHERE status = 'SUCESSO'
ORDER BY finalizado_em DESC
LIMIT 1;

CREATE OR REPLACE VIEW vw_qualidade_dados AS
SELECT 'campanhas_ids_duplicados' AS teste, COUNT(*) AS ocorrencias
FROM (SELECT id FROM campanhas GROUP BY id HAVING COUNT(*) > 1) x
UNION ALL
SELECT 'leads_ids_duplicados', COUNT(*)
FROM (SELECT id FROM leads GROUP BY id HAVING COUNT(*) > 1) y
UNION ALL
SELECT 'campanhas_funil_invalido', COUNT(*)
FROM campanhas
WHERE cliques > impressoes OR leads > cliques OR vendas > leads
UNION ALL
SELECT 'campanhas_metricas_negativas', COUNT(*)
FROM campanhas
WHERE investimento < 0 OR impressoes < 0 OR cliques < 0
   OR leads < 0 OR vendas < 0 OR receita < 0;

SELECT * FROM vw_resultados_canal ORDER BY receita DESC;
SELECT * FROM vw_qualidade_dados;

