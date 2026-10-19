from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


class WorkbookReadError(ValueError):
    pass


def _column_index(cell_reference: str) -> int:
    match = re.match(r"([A-Z]+)", cell_reference.upper())
    if not match:
        raise WorkbookReadError(f"Referência de célula inválida: {cell_reference}")
    result = 0
    for char in match.group(1):
        result = result * 26 + ord(char) - ord("A") + 1
    return result - 1


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(path))
    strings = []
    for item in root.findall(f"{{{MAIN_NS}}}si"):
        strings.append("".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")))
    return strings


def _sheet_paths(archive: zipfile.ZipFile) -> dict[str, str]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relationships = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rel_root.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
    }
    result: dict[str, str] = {}
    for sheet in workbook_root.findall(f".//{{{MAIN_NS}}}sheet"):
        rel_id = sheet.attrib[f"{{{REL_NS}}}id"]
        target = PurePosixPath(relationships[rel_id])
        if target.is_absolute():
            normalized = str(target).lstrip("/")
        else:
            normalized = str(PurePosixPath("xl") / target)
        result[sheet.attrib["name"]] = normalized
    return result


def _cell_value(cell: ET.Element, shared_strings: list[str]):
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{{{MAIN_NS}}}is")
        return "" if inline is None else "".join(
            node.text or "" for node in inline.iter(f"{{{MAIN_NS}}}t")
        )
    value_node = cell.find(f"{{{MAIN_NS}}}v")
    if value_node is None:
        return None
    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError) as exc:
            raise WorkbookReadError("Índice inválido em sharedStrings.xml") from exc
    if cell_type in {"str", "e"}:
        return raw
    if cell_type == "b":
        return raw == "1"
    try:
        number = float(raw)
        return int(number) if number.is_integer() else number
    except ValueError:
        return raw


def read_sheet(workbook_path: Path, sheet_name: str) -> list[dict[str, object]]:
    if not workbook_path.exists():
        raise WorkbookReadError(f"Arquivo Excel não encontrado: {workbook_path}")
    try:
        with zipfile.ZipFile(workbook_path) as archive:
            paths = _sheet_paths(archive)
            if sheet_name not in paths:
                raise WorkbookReadError(
                    f"Aba '{sheet_name}' ausente. Abas disponíveis: {', '.join(paths)}"
                )
            shared_strings = _read_shared_strings(archive)
            root = ET.fromstring(archive.read(paths[sheet_name]))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise WorkbookReadError(f"XLSX inválido ou corrompido: {workbook_path}") from exc

    rows: list[list[object | None]] = []
    for row in root.findall(f".//{{{MAIN_NS}}}sheetData/{{{MAIN_NS}}}row"):
        indexed: dict[int, object | None] = {}
        for cell in row.findall(f"{{{MAIN_NS}}}c"):
            reference = cell.attrib.get("r")
            if not reference:
                continue
            indexed[_column_index(reference)] = _cell_value(cell, shared_strings)
        if indexed:
            width = max(indexed) + 1
            rows.append([indexed.get(index) for index in range(width)])

    if not rows:
        raise WorkbookReadError(f"Aba '{sheet_name}' está vazia.")
    headers = [str(value).strip() if value is not None else "" for value in rows[0]]
    if not any(headers):
        raise WorkbookReadError(f"Aba '{sheet_name}' não possui cabeçalho.")

    records: list[dict[str, object]] = []
    for row_number, values in enumerate(rows[1:], start=2):
        if not any(value not in (None, "") for value in values):
            continue
        record = {"__row__": row_number}
        for index, header in enumerate(headers):
            if header:
                record[header] = values[index] if index < len(values) else None
        records.append(record)
    return records

