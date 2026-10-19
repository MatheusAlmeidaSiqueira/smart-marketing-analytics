from __future__ import annotations

import hashlib
import logging
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from smart_marketing.config import PipelinePaths
from smart_marketing.excel_reader import read_sheet
from smart_marketing.exporter import build_indicators
from smart_marketing.pipeline import run_pipeline
from smart_marketing.validation import DataValidationError, build_bundle


ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "data" / "Smart_Marketing_Analytics_DEMO.xlsx"


class PipelineTests(unittest.TestCase):
    def test_demo_workbook_is_valid_and_unique(self) -> None:
        bundle = build_bundle(
            read_sheet(WORKBOOK, "Campanhas"), read_sheet(WORKBOOK, "Leads")
        )
        self.assertEqual(24, len(bundle.campaigns))
        self.assertEqual(80, len(bundle.leads))
        self.assertEqual(24, len({item.id for item in bundle.campaigns}))
        self.assertEqual(80, len({item.id for item in bundle.leads}))
        totals = build_indicators(bundle, "test")["total"]
        self.assertEqual(15510.0, totals["investimento"])
        self.assertEqual(1299, totals["leads"])
        self.assertEqual(104, totals["vendas"])
        self.assertEqual(832000.0, totals["receita"])

    def test_duplicate_campaign_is_rejected(self) -> None:
        campaigns = read_sheet(WORKBOOK, "Campanhas")
        leads = read_sheet(WORKBOOK, "Leads")
        campaigns.append(dict(campaigns[0], __row__=999))
        with self.assertRaises(DataValidationError):
            build_bundle(campaigns, leads)

    def test_sqlite_upsert_is_idempotent_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            paths = PipelinePaths(ROOT, WORKBOOK, base / "exports", base / "logs")
            database = base / "demo.sqlite3"
            first = run_pipeline(paths, "sqlite", database, False, True, False)
            second = run_pipeline(paths, "sqlite", database, False, True, False)

            self.assertEqual(24, first["database"]["campaign_inserted"])
            self.assertEqual(80, first["database"]["lead_inserted"])
            self.assertEqual(0, second["database"]["campaign_inserted"])
            self.assertEqual(24, second["database"]["campaign_updated"])
            self.assertEqual(0, second["database"]["deleted_rows"])

            with closing(sqlite3.connect(database)) as connection:
                campaign_count = connection.execute("SELECT COUNT(*) FROM campanhas").fetchone()[0]
                lead_count = connection.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
                audit_count = connection.execute("SELECT COUNT(*) FROM etl_execucoes").fetchone()[0]
                duplicate_count = connection.execute(
                    "SELECT COUNT(*) FROM (SELECT id FROM campanhas GROUP BY id HAVING COUNT(*) > 1)"
                ).fetchone()[0]
            self.assertEqual((24, 80, 2, 0), (campaign_count, lead_count, audit_count, duplicate_count))
            logging.shutdown()

    def test_source_hash_is_reproducible(self) -> None:
        digest = hashlib.sha256(WORKBOOK.read_bytes()).hexdigest()
        self.assertEqual(64, len(digest))


if __name__ == "__main__":
    unittest.main()
