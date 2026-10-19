from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Protocol

from .config import MySQLConfig
from .models import DataBundle


@dataclass(frozen=True)
class SyncResult:
    campaign_inserted: int
    campaign_updated: int
    lead_inserted: int
    lead_updated: int
    campaign_rows_after: int
    lead_rows_after: int
    stale_campaign_ids: tuple[str, ...]
    stale_lead_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "campaign_inserted": self.campaign_inserted,
            "campaign_updated": self.campaign_updated,
            "lead_inserted": self.lead_inserted,
            "lead_updated": self.lead_updated,
            "campaign_rows_after": self.campaign_rows_after,
            "lead_rows_after": self.lead_rows_after,
            "stale_campaign_ids": list(self.stale_campaign_ids),
            "stale_lead_ids": list(self.stale_lead_ids),
            "deleted_rows": 0,
        }


class Repository(Protocol):
    def sync(self, bundle: DataBundle, run_id: str, source_hash: str) -> SyncResult: ...


def _partition(existing: set[str], source: set[str]) -> tuple[int, int, tuple[str, ...]]:
    inserted = len(source - existing)
    updated = len(source & existing)
    stale = tuple(sorted(existing - source))
    return inserted, updated, stale


class SQLiteRepository:
    """Backend de teste local. O ambiente produtivo continua sendo MySQL."""

    def __init__(self, path: Path):
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _initialize(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS campanhas (
              id TEXT PRIMARY KEY, data TEXT NOT NULL, canal TEXT NOT NULL,
              campanha TEXT NOT NULL, investimento NUMERIC NOT NULL,
              impressoes INTEGER NOT NULL, cliques INTEGER NOT NULL,
              leads INTEGER NOT NULL, vendas INTEGER NOT NULL, receita NUMERIC NOT NULL
            );
            CREATE TABLE IF NOT EXISTS leads (
              id TEXT PRIMARY KEY, data TEXT NOT NULL, empresa TEXT NOT NULL,
              canal TEXT NOT NULL, interesse TEXT NOT NULL, status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS etl_execucoes (
              run_id TEXT PRIMARY KEY, iniciado_em TEXT NOT NULL, finalizado_em TEXT,
              status TEXT NOT NULL, source_hash TEXT NOT NULL,
              campanhas_processadas INTEGER, leads_processados INTEGER, mensagem TEXT
            );
            """
        )

    def sync(self, bundle: DataBundle, run_id: str, source_hash: str) -> SyncResult:
        with closing(self._connect()) as connection, connection:
            self._initialize(connection)
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO etl_execucoes(run_id,iniciado_em,status,source_hash) VALUES(?,?,?,?)",
                (run_id, datetime.now(timezone.utc).isoformat(), "EM_EXECUCAO", source_hash),
            )
            campaign_existing = {
                row[0] for row in connection.execute("SELECT id FROM campanhas").fetchall()
            }
            lead_existing = {row[0] for row in connection.execute("SELECT id FROM leads").fetchall()}
            campaign_source = {row.id for row in bundle.campaigns}
            lead_source = {row.id for row in bundle.leads}
            campaign_inserted, campaign_updated, stale_campaigns = _partition(
                campaign_existing, campaign_source
            )
            lead_inserted, lead_updated, stale_leads = _partition(lead_existing, lead_source)

            connection.executemany(
                """
                INSERT INTO campanhas VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  data=excluded.data, canal=excluded.canal, campanha=excluded.campanha,
                  investimento=excluded.investimento, impressoes=excluded.impressoes,
                  cliques=excluded.cliques, leads=excluded.leads, vendas=excluded.vendas,
                  receita=excluded.receita
                """,
                [
                    (
                        row.id,
                        row.data.isoformat(),
                        row.canal,
                        row.campanha,
                        str(row.investimento),
                        row.impressoes,
                        row.cliques,
                        row.leads,
                        row.vendas,
                        str(row.receita),
                    )
                    for row in bundle.campaigns
                ],
            )
            connection.executemany(
                """
                INSERT INTO leads VALUES (?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                  data=excluded.data, empresa=excluded.empresa, canal=excluded.canal,
                  interesse=excluded.interesse, status=excluded.status
                """,
                [
                    (
                        row.id,
                        row.data.isoformat(),
                        row.empresa,
                        row.canal,
                        row.interesse,
                        row.status,
                    )
                    for row in bundle.leads
                ],
            )
            campaign_count = connection.execute("SELECT COUNT(*) FROM campanhas").fetchone()[0]
            lead_count = connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            duplicate_campaigns = connection.execute(
                "SELECT COUNT(*) FROM (SELECT id FROM campanhas GROUP BY id HAVING COUNT(*) > 1)"
            ).fetchone()[0]
            duplicate_leads = connection.execute(
                "SELECT COUNT(*) FROM (SELECT id FROM leads GROUP BY id HAVING COUNT(*) > 1)"
            ).fetchone()[0]
            if duplicate_campaigns or duplicate_leads:
                raise RuntimeError("Duplicidades detectadas após sincronização; rollback aplicado.")
            connection.execute(
                """
                UPDATE etl_execucoes SET finalizado_em=?, status='SUCESSO',
                  campanhas_processadas=?, leads_processados=?, mensagem=? WHERE run_id=?
                """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    len(bundle.campaigns),
                    len(bundle.leads),
                    "Sincronização concluída sem exclusões.",
                    run_id,
                ),
            )
            return SyncResult(
                campaign_inserted,
                campaign_updated,
                lead_inserted,
                lead_updated,
                campaign_count,
                lead_count,
                stale_campaigns,
                stale_leads,
            )


class MySQLRepository:
    def __init__(self, config: MySQLConfig):
        self.config = config

    def _connect(self):
        try:
            import mysql.connector
        except ImportError as exc:
            raise RuntimeError(
                "Dependência ausente: instale mysql-connector-python conforme requirements.txt."
            ) from exc
        return mysql.connector.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            connection_timeout=self.config.connection_timeout,
            charset="utf8mb4",
            use_unicode=True,
            autocommit=False,
        )

    @staticmethod
    def _require_schema(cursor) -> None:
        cursor.execute("SHOW TABLES")
        tables = {row[0] for row in cursor.fetchall()}
        missing = {"campanhas", "leads", "etl_execucoes"} - tables
        if missing:
            raise RuntimeError(
                "Esquema incompleto. Execute sql/schema.sql. Ausentes: "
                + ", ".join(sorted(missing))
            )

    def sync(self, bundle: DataBundle, run_id: str, source_hash: str) -> SyncResult:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            self._require_schema(cursor)
            cursor.execute(
                """
                INSERT INTO etl_execucoes
                  (run_id,iniciado_em,status,source_hash)
                VALUES (%s,UTC_TIMESTAMP(6),'EM_EXECUCAO',%s)
                """,
                (run_id, source_hash),
            )
            cursor.execute("SELECT id FROM campanhas")
            campaign_existing = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT id FROM leads")
            lead_existing = {row[0] for row in cursor.fetchall()}
            campaign_source = {row.id for row in bundle.campaigns}
            lead_source = {row.id for row in bundle.leads}
            campaign_inserted, campaign_updated, stale_campaigns = _partition(
                campaign_existing, campaign_source
            )
            lead_inserted, lead_updated, stale_leads = _partition(lead_existing, lead_source)

            campaign_sql = """
                INSERT INTO campanhas
                  (id,data,canal,campanha,investimento,impressoes,cliques,leads,vendas,receita)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                AS new
                ON DUPLICATE KEY UPDATE
                  data=new.data, canal=new.canal, campanha=new.campanha,
                  investimento=new.investimento, impressoes=new.impressoes,
                  cliques=new.cliques, leads=new.leads, vendas=new.vendas,
                  receita=new.receita
            """
            campaign_rows = [row.database_tuple() for row in bundle.campaigns]
            cursor.executemany(campaign_sql, campaign_rows)

            lead_sql = """
                INSERT INTO leads (id,data,empresa,canal,interesse,status)
                VALUES (%s,%s,%s,%s,%s,%s)
                AS new
                ON DUPLICATE KEY UPDATE
                  data=new.data, empresa=new.empresa, canal=new.canal,
                  interesse=new.interesse, status=new.status
            """
            lead_rows = [row.database_tuple() for row in bundle.leads]
            cursor.executemany(lead_sql, lead_rows)

            cursor.execute("SELECT COUNT(*) FROM campanhas")
            campaign_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM leads")
            lead_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM (SELECT id FROM campanhas GROUP BY id HAVING COUNT(*) > 1) x"
            )
            duplicate_campaigns = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM (SELECT id FROM leads GROUP BY id HAVING COUNT(*) > 1) x"
            )
            duplicate_leads = cursor.fetchone()[0]
            if duplicate_campaigns or duplicate_leads:
                raise RuntimeError("Duplicidades detectadas após sincronização; rollback aplicado.")

            cursor.execute(
                """
                UPDATE etl_execucoes SET finalizado_em=UTC_TIMESTAMP(6), status='SUCESSO',
                  campanhas_processadas=%s, leads_processados=%s,
                  campanhas_inseridas=%s, campanhas_atualizadas=%s,
                  leads_inseridos=%s, leads_atualizados=%s,
                  mensagem='Sincronização concluída sem exclusões.'
                WHERE run_id=%s
                """,
                (
                    len(bundle.campaigns),
                    len(bundle.leads),
                    campaign_inserted,
                    campaign_updated,
                    lead_inserted,
                    lead_updated,
                    run_id,
                ),
            )
            connection.commit()
            return SyncResult(
                campaign_inserted,
                campaign_updated,
                lead_inserted,
                lead_updated,
                campaign_count,
                lead_count,
                stale_campaigns,
                stale_leads,
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

