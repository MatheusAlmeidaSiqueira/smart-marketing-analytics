from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MySQLConfig:
    host: str
    port: int
    user: str
    password: str
    database: str
    connection_timeout: int = 10

    @classmethod
    def from_environment(cls) -> "MySQLConfig":
        def first(*names: str, default: str | None = None) -> str | None:
            for name in names:
                value = os.getenv(name)
                if value:
                    return value
            return default

        user = first("SMART_MARKETING_MYSQL_USER", "MYSQL_USER")
        password = first("SMART_MARKETING_MYSQL_PASSWORD", "MYSQL_PASSWORD")
        if not user:
            raise ValueError(
                "Defina SMART_MARKETING_MYSQL_USER. Não há usuário root padrão."
            )
        if not password:
            raise ValueError(
                "Defina SMART_MARKETING_MYSQL_PASSWORD no processo de execução."
            )
        try:
            port = int(first("SMART_MARKETING_MYSQL_PORT", "MYSQL_PORT", default="3306"))
        except ValueError as exc:
            raise ValueError("SMART_MARKETING_MYSQL_PORT deve ser inteiro.") from exc

        return cls(
            host=first("SMART_MARKETING_MYSQL_HOST", "MYSQL_HOST", default="127.0.0.1"),
            port=port,
            user=user,
            password=password,
            database=first(
                "SMART_MARKETING_MYSQL_DATABASE", "MYSQL_DATABASE", default="smart_marketing"
            ),
            connection_timeout=int(
                first("SMART_MARKETING_MYSQL_TIMEOUT", default="10")
            ),
        )

    @property
    def safe_description(self) -> str:
        return f"mysql://{self.user}@{self.host}:{self.port}/{self.database}"


@dataclass(frozen=True)
class PipelinePaths:
    project_root: Path
    workbook: Path
    output_dir: Path
    log_dir: Path

    @classmethod
    def defaults(cls, project_root: Path) -> "PipelinePaths":
        return cls(
            project_root=project_root,
            workbook=project_root / "data" / "Smart_Marketing_Analytics_DEMO.xlsx",
            output_dir=project_root / "runtime" / "exports",
            log_dir=project_root / "runtime" / "logs",
        )

