from __future__ import annotations

import csv
import json
import os
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .models import DataBundle


CAMPAIGN_HEADERS = [
    "id",
    "data",
    "canal",
    "campanha",
    "investimento",
    "impressoes",
    "cliques",
    "leads",
    "vendas",
    "receita",
]
LEAD_HEADERS = ["id", "data", "empresa", "canal", "interesse", "status"]


def _atomic_text_write(path: Path, writer) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        writer(temp_path)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def build_indicators(bundle: DataBundle, source_hash: str) -> dict:
    channel_totals: dict[str, dict[str, Decimal | int]] = defaultdict(
        lambda: {
            "investimento": Decimal(0),
            "impressoes": 0,
            "cliques": 0,
            "leads": 0,
            "vendas": 0,
            "receita": Decimal(0),
        }
    )
    for row in bundle.campaigns:
        current = channel_totals[row.canal]
        current["investimento"] += row.investimento
        current["impressoes"] += row.impressoes
        current["cliques"] += row.cliques
        current["leads"] += row.leads
        current["vendas"] += row.vendas
        current["receita"] += row.receita

    def derived(values: dict) -> dict:
        investment = values["investimento"]
        impressions = values["impressoes"]
        clicks = values["cliques"]
        leads = values["leads"]
        sales = values["vendas"]
        revenue = values["receita"]
        return {
            **values,
            "ctr": Decimal(clicks) / Decimal(impressions) if impressions else None,
            "cpc": investment / Decimal(clicks) if clicks else None,
            "cpl": investment / Decimal(leads) if leads else None,
            "cpa": investment / Decimal(sales) if sales else None,
            "taxa_conversao": Decimal(sales) / Decimal(leads) if leads else None,
            "roas": revenue / investment if investment else None,
        }

    total_base = {
        key: sum(values[key] for values in channel_totals.values())
        for key in [
            "investimento",
            "impressoes",
            "cliques",
            "leads",
            "vendas",
            "receita",
        ]
    }

    def serializable(values: dict) -> dict:
        result = {}
        for key, value in values.items():
            if isinstance(value, Decimal):
                result[key] = round(float(value), 4)
            else:
                result[key] = value
        return result

    return {
        "metadata": {
            "gerado_em_utc": datetime.now(timezone.utc).isoformat(),
            "source_sha256": source_hash,
            "politica_divisao_por_zero": "null",
        },
        "total": serializable(derived(total_base)),
        "por_canal": {
            channel: serializable(derived(values))
            for channel, values in sorted(channel_totals.items())
        },
        "qualidade": bundle.quality_summary(),
        "quantidade_contatos_crm": len(bundle.leads),
        "observacao": (
            "Leads agregados por campanha não equivalem aos contatos exemplificativos no CRM."
        ),
    }


def export_bundle(bundle: DataBundle, output_dir: Path, source_hash: str) -> dict[str, Path]:
    campaign_path = output_dir / "campanhas.csv"
    lead_path = output_dir / "leads.csv"
    indicator_path = output_dir / "indicadores.json"

    def write_campaigns(path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(CAMPAIGN_HEADERS)
            writer.writerows(row.csv_row() for row in bundle.campaigns)

    def write_leads(path: Path) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(LEAD_HEADERS)
            writer.writerows(row.csv_row() for row in bundle.leads)

    indicators = build_indicators(bundle, source_hash)

    def write_indicators(path: Path) -> None:
        path.write_text(
            json.dumps(indicators, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    _atomic_text_write(campaign_path, write_campaigns)
    _atomic_text_write(lead_path, write_leads)
    _atomic_text_write(indicator_path, write_indicators)
    return {
        "campaigns": campaign_path,
        "leads": lead_path,
        "indicators": indicator_path,
    }

