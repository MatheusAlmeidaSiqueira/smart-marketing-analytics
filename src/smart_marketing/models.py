from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Campaign:
    id: str
    data: date
    canal: str
    campanha: str
    investimento: Decimal
    impressoes: int
    cliques: int
    leads: int
    vendas: int
    receita: Decimal

    def database_tuple(self) -> tuple:
        return (
            self.id,
            self.data,
            self.canal,
            self.campanha,
            self.investimento,
            self.impressoes,
            self.cliques,
            self.leads,
            self.vendas,
            self.receita,
        )

    def csv_row(self) -> list[str | int]:
        return [
            self.id,
            self.data.isoformat(),
            self.canal,
            self.campanha,
            format(self.investimento, "f"),
            self.impressoes,
            self.cliques,
            self.leads,
            self.vendas,
            format(self.receita, "f"),
        ]


@dataclass(frozen=True)
class Lead:
    id: str
    data: date
    empresa: str
    canal: str
    interesse: str
    status: str

    def database_tuple(self) -> tuple:
        return (self.id, self.data, self.empresa, self.canal, self.interesse, self.status)

    def csv_row(self) -> list[str]:
        return [
            self.id,
            self.data.isoformat(),
            self.empresa,
            self.canal,
            self.interesse,
            self.status,
        ]


@dataclass(frozen=True)
class DataBundle:
    campaigns: tuple[Campaign, ...]
    leads: tuple[Lead, ...]
    warnings: tuple[str, ...]

    def quality_summary(self) -> dict:
        return {
            "campaign_rows": len(self.campaigns),
            "campaign_unique_ids": len({row.id for row in self.campaigns}),
            "crm_contact_rows": len(self.leads),
            "crm_contact_unique_ids": len({row.id for row in self.leads}),
            "warnings": list(self.warnings),
        }

