from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from .models import Campaign, DataBundle, Lead


class DataValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


CAMPAIGN_COLUMNS = {
    "ID": "id",
    "Data": "data",
    "Canal": "canal",
    "Campanha": "campanha",
    "Investimento (R$)": "investimento",
    "Impressões": "impressoes",
    "Cliques": "cliques",
    "Leads": "leads",
    "Vendas": "vendas",
    "Receita (R$)": "receita",
}

LEAD_COLUMNS = {
    "Lead ID": "id",
    "Data": "data",
    "Empresa fictícia": "empresa",
    "Canal": "canal",
    "Interesse": "interesse",
    "Status": "status",
}


def _required_headers(records: list[dict], mapping: dict[str, str], sheet: str) -> list[str]:
    if not records:
        return [f"{sheet}: nenhuma linha de dados."]
    missing = [header for header in mapping if header not in records[0]]
    return [f"{sheet}: cabeçalho obrigatório ausente: {header}" for header in missing]


def _text(value, label: str, row: int, errors: list[str]) -> str:
    result = "" if value is None else str(value).strip()
    if not result:
        errors.append(f"Linha {row}: {label} é obrigatório.")
    return result


def _date(value, label: str, row: int, errors: list[str]) -> date:
    try:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, (int, float)):
            return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
        return date.fromisoformat(str(value).strip())
    except (TypeError, ValueError, OverflowError):
        errors.append(f"Linha {row}: {label} inválida: {value!r}.")
        return date.min


def _decimal(value, label: str, row: int, errors: list[str]) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        if result < 0:
            errors.append(f"Linha {row}: {label} não pode ser negativo.")
        return result.quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError):
        errors.append(f"Linha {row}: {label} inválido: {value!r}.")
        return Decimal(0)


def _integer(value, label: str, row: int, errors: list[str]) -> int:
    try:
        number = Decimal(str(value))
        if number != number.to_integral_value():
            raise InvalidOperation
        result = int(number)
        if result < 0:
            errors.append(f"Linha {row}: {label} não pode ser negativo.")
        return result
    except (InvalidOperation, TypeError, ValueError):
        errors.append(f"Linha {row}: {label} deve ser inteiro: {value!r}.")
        return 0


def build_bundle(campaign_records: list[dict], lead_records: list[dict]) -> DataBundle:
    errors = _required_headers(campaign_records, CAMPAIGN_COLUMNS, "Campanhas")
    errors += _required_headers(lead_records, LEAD_COLUMNS, "Leads")
    if errors:
        raise DataValidationError(errors)

    campaigns: list[Campaign] = []
    campaign_ids: set[str] = set()
    for raw in campaign_records:
        row = int(raw["__row__"])
        campaign = Campaign(
            id=_text(raw.get("ID"), "ID", row, errors),
            data=_date(raw.get("Data"), "Data", row, errors),
            canal=_text(raw.get("Canal"), "Canal", row, errors),
            campanha=_text(raw.get("Campanha"), "Campanha", row, errors),
            investimento=_decimal(raw.get("Investimento (R$)"), "Investimento", row, errors),
            impressoes=_integer(raw.get("Impressões"), "Impressões", row, errors),
            cliques=_integer(raw.get("Cliques"), "Cliques", row, errors),
            leads=_integer(raw.get("Leads"), "Leads", row, errors),
            vendas=_integer(raw.get("Vendas"), "Vendas", row, errors),
            receita=_decimal(raw.get("Receita (R$)"), "Receita", row, errors),
        )
        if campaign.id in campaign_ids:
            errors.append(f"Linha {row}: ID de campanha duplicado: {campaign.id}.")
        campaign_ids.add(campaign.id)
        if campaign.cliques > campaign.impressoes:
            errors.append(f"Linha {row}: cliques excedem impressões.")
        if campaign.leads > campaign.cliques:
            errors.append(f"Linha {row}: leads excedem cliques.")
        if campaign.vendas > campaign.leads:
            errors.append(f"Linha {row}: vendas excedem leads.")
        campaigns.append(campaign)

    leads: list[Lead] = []
    lead_ids: set[str] = set()
    for raw in lead_records:
        row = int(raw["__row__"])
        lead = Lead(
            id=_text(raw.get("Lead ID"), "Lead ID", row, errors),
            data=_date(raw.get("Data"), "Data", row, errors),
            empresa=_text(raw.get("Empresa fictícia"), "Empresa", row, errors),
            canal=_text(raw.get("Canal"), "Canal", row, errors),
            interesse=_text(raw.get("Interesse"), "Interesse", row, errors),
            status=_text(raw.get("Status"), "Status", row, errors),
        )
        if lead.id in lead_ids:
            errors.append(f"Linha {row}: Lead ID duplicado: {lead.id}.")
        lead_ids.add(lead.id)
        leads.append(lead)

    if errors:
        raise DataValidationError(errors)

    campaign_channels = {row.canal for row in campaigns}
    crm_channels = {row.canal for row in leads}
    warnings = []
    unknown_channels = sorted(crm_channels - campaign_channels)
    if unknown_channels:
        warnings.append(
            "Canais presentes no CRM e ausentes em Campanhas: " + ", ".join(unknown_channels)
        )
    warnings.append(
        "Leads agregados das campanhas e contatos do CRM têm granularidades diferentes; "
        "não devem ser relacionados diretamente."
    )
    return DataBundle(tuple(campaigns), tuple(leads), tuple(warnings))

