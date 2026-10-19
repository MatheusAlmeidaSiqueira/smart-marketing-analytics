from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import uuid
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import MySQLConfig, PipelinePaths
from .excel_reader import read_sheet
from .exporter import build_indicators, export_bundle
from .repository import MySQLRepository, SQLiteRepository
from .validation import DataValidationError, build_bundle


def _logger(log_dir: Path, verbose: bool = False) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("smart_marketing")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    file_handler = RotatingFileHandler(
        log_dir / "pipeline.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console)
    return logger


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_pipeline(
    paths: PipelinePaths,
    backend: str,
    sqlite_path: Path | None,
    validate_only: bool,
    no_export: bool,
    verbose: bool,
) -> dict:
    logger = _logger(paths.log_dir, verbose)
    run_id = str(uuid.uuid4())
    logger.info("Início da execução %s", run_id)
    logger.info("Fonte: %s", paths.workbook)
    source_hash = _sha256(paths.workbook)

    campaign_records = read_sheet(paths.workbook, "Campanhas")
    lead_records = read_sheet(paths.workbook, "Leads")
    bundle = build_bundle(campaign_records, lead_records)
    logger.info(
        "Validação aprovada: %d campanhas e %d contatos CRM.",
        len(bundle.campaigns),
        len(bundle.leads),
    )
    for warning in bundle.warnings:
        logger.warning(warning)

    exported = {}
    if not no_export:
        exported = {
            key: str(value)
            for key, value in export_bundle(bundle, paths.output_dir, source_hash).items()
        }
        logger.info("Arquivos derivados publicados atomicamente em %s", paths.output_dir)

    sync_result = None
    if not validate_only:
        if backend == "mysql":
            config = MySQLConfig.from_environment()
            logger.info("Destino: %s", config.safe_description)
            repository = MySQLRepository(config)
        elif backend == "sqlite":
            if sqlite_path is None:
                raise ValueError("Informe --sqlite-path para o backend sqlite.")
            logger.info("Destino de teste SQLite: %s", sqlite_path)
            repository = SQLiteRepository(sqlite_path)
        else:
            raise ValueError(f"Backend desconhecido: {backend}")
        sync_result = repository.sync(bundle, run_id, source_hash)
        logger.info("Sincronização concluída: %s", json.dumps(sync_result.as_dict()))
        if sync_result.stale_campaign_ids or sync_result.stale_lead_ids:
            logger.warning(
                "Há IDs no banco ausentes no Excel. Nenhuma exclusão foi feita: campanhas=%d, leads=%d.",
                len(sync_result.stale_campaign_ids),
                len(sync_result.stale_lead_ids),
            )

    result = {
        "run_id": run_id,
        "status": "SUCESSO",
        "source_sha256": source_hash,
        "validated": bundle.quality_summary(),
        "indicators": build_indicators(bundle, source_hash)["total"],
        "exported": exported,
        "database": sync_result.as_dict() if sync_result else None,
    }
    logger.info("Fim da execução %s: SUCESSO", run_id)
    return result


def parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parents[2]
    defaults = PipelinePaths.defaults(project_root)
    result = argparse.ArgumentParser(
        description="Valida o Excel, publica derivados e sincroniza com MySQL sem exclusões."
    )
    result.add_argument("--workbook", type=Path, default=defaults.workbook)
    result.add_argument("--output-dir", type=Path, default=defaults.output_dir)
    result.add_argument("--log-dir", type=Path, default=defaults.log_dir)
    result.add_argument("--backend", choices=("mysql", "sqlite"), default="mysql")
    result.add_argument("--sqlite-path", type=Path)
    result.add_argument("--validate-only", action="store_true")
    result.add_argument("--no-export", action="store_true")
    result.add_argument("--verbose", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    paths = PipelinePaths(
        project_root=Path(__file__).resolve().parents[2],
        workbook=args.workbook.resolve(),
        output_dir=args.output_dir.resolve(),
        log_dir=args.log_dir.resolve(),
    )
    try:
        result = run_pipeline(
            paths=paths,
            backend=args.backend,
            sqlite_path=args.sqlite_path.resolve() if args.sqlite_path else None,
            validate_only=args.validate_only,
            no_export=args.no_export,
            verbose=args.verbose,
        )
    except DataValidationError as exc:
        print("FALHA DE VALIDAÇÃO:", file=sys.stderr)
        for error in exc.errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    except Exception as exc:
        logging.getLogger("smart_marketing").exception("Falha na execução: %s", exc)
        print(f"FALHA: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

