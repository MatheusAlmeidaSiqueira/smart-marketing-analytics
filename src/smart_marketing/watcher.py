"""Monitor leve para sincronizar um XLSX salvo com o banco configurado.

O monitor usa apenas caminhos relativos e variáveis de ambiente. Ele aguarda o
arquivo ficar estável e legível antes de disparar o mesmo pipeline transacional
usado na execução manual.
"""

from __future__ import annotations

import argparse
import logging
import os
import time
import zipfile
from contextlib import contextmanager
from pathlib import Path

from .config import PipelinePaths
from .pipeline import run_pipeline


LOGGER = logging.getLogger("smart_marketing.watcher")


def _signature(path: Path) -> tuple[int, int]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size


def _xlsx_ready(path: Path, quiet_seconds: float) -> bool:
    """Confirma que o arquivo parou de mudar e já pode ser aberto como XLSX."""
    try:
        first = _signature(path)
        time.sleep(quiet_seconds)
        if first != _signature(path):
            return False
        with path.open("rb"):
            pass
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None
    except (FileNotFoundError, PermissionError, OSError, zipfile.BadZipFile):
        return False


def _process_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True


@contextmanager
def _single_instance(lock_path: Path):
    """Evita duas instâncias; recupera lock órfão de processo já encerrado."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(descriptor, str(os.getpid()).encode("ascii"))
            os.close(descriptor)
            break
        except FileExistsError:
            try:
                previous_pid = int(lock_path.read_text(encoding="ascii").strip())
            except (OSError, ValueError):
                previous_pid = -1
            if _process_is_alive(previous_pid):
                raise RuntimeError(f"Monitor já está ativo (PID {previous_pid}).")
            lock_path.unlink(missing_ok=True)
    else:
        raise RuntimeError("Não foi possível adquirir o lock do monitor.")
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    defaults = PipelinePaths.defaults(root)
    result = argparse.ArgumentParser(description="Monitora o Excel e sincroniza alterações.")
    result.add_argument("--workbook", type=Path, default=defaults.workbook)
    result.add_argument("--poll-seconds", type=float, default=3.0)
    result.add_argument("--quiet-seconds", type=float, default=2.0)
    result.add_argument("--run-on-start", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    workbook = args.workbook.resolve()
    paths = PipelinePaths(
        project_root=root,
        workbook=workbook,
        output_dir=root / "runtime" / "exports",
        log_dir=root / "runtime" / "logs",
    )
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    lock_path = root / "runtime" / "watcher.lock"
    with _single_instance(lock_path):
        LOGGER.info("Monitorando %s", workbook)
        previous = None if args.run_on_start else (_signature(workbook) if workbook.exists() else None)
        while True:
            try:
                current = _signature(workbook)
                if current != previous and _xlsx_ready(workbook, args.quiet_seconds):
                    run_pipeline(paths, "mysql", None, False, False, False)
                    previous = _signature(workbook)
                    LOGGER.info("Sincronização concluída; aguardando nova alteração.")
            except FileNotFoundError:
                LOGGER.warning("Arquivo ainda não encontrado: %s", workbook)
            except Exception:
                LOGGER.exception("A sincronização falhou; o monitor continuará ativo.")
            time.sleep(max(args.poll_seconds, 1.0))


if __name__ == "__main__":
    raise SystemExit(main())
