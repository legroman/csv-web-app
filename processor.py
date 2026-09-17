"""CSV parsing, cleaning, and Excel export functions."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path

from openpyxl import Workbook


class CsvProcessingError(ValueError):
    """Raised when an uploaded CSV cannot be safely processed."""


def read_csv(path: str | Path) -> tuple[list[str], list[list[str]], str]:
    """Read a UTF-8 CSV and detect comma, semicolon, or tab delimiters."""
    try:
        content = Path(path).read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvProcessingError("This file is not a UTF-8 CSV. Please save it as UTF-8 and try again.") from error
    except OSError as error:
        raise CsvProcessingError("The uploaded file could not be read.") from error

    if not content.strip():
        raise CsvProcessingError("The CSV file is empty.")

    try:
        dialect = csv.Sniffer().sniff(content[:8192], delimiters=",;\t")
    except csv.Error:
        # Sniffer needs a consistent sample.  If a malformed data row prevents
        # detection, infer the delimiter from the header so the caller still
        # receives the more useful column-count validation below.
        first_line = next((line for line in content.splitlines() if line.strip()), "")
        delimiter = next((item for item in ",;\t" if item in first_line), ",")
        dialect = csv.excel()
        dialect.delimiter = delimiter

    try:
        delimiter = dialect.delimiter
        parsed_rows = list(csv.reader(StringIO(content, newline=""), dialect))
    except csv.Error as error:
        raise CsvProcessingError("The CSV file could not be parsed. Check its delimiter and quoting.") from error

    if not parsed_rows:
        raise CsvProcessingError("The CSV file contains no rows.")

    headers = [cell.strip() for cell in parsed_rows[0]]
    if not headers or not any(headers):
        raise CsvProcessingError("The CSV needs a non-empty header row.")

    expected_columns = len(headers)
    data_rows: list[list[str]] = []
    for row_number, row in enumerate(parsed_rows[1:], start=2):
        if not row:
            # A physical blank line represents an all-empty row and belongs in
            # the normal cleanup accounting rather than failing validation.
            data_rows.append([""] * expected_columns)
            continue
        if len(row) != expected_columns:
            raise CsvProcessingError(
                f"Row {row_number} has {len(row)} columns; the header has {expected_columns}."
            )
        data_rows.append(row)
    return headers, data_rows, delimiter


def clean_rows(rows: list[list[str]]) -> tuple[list[list[str]], int, int]:
    """Trim cells, drop all-empty rows, and deduplicate while retaining order."""
    cleaned: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    empty_count = 0
    duplicate_count = 0

    for row in rows:
        trimmed = [cell.strip() for cell in row]
        if not any(trimmed):
            empty_count += 1
            continue
        row_key = tuple(trimmed)
        if row_key in seen:
            duplicate_count += 1
            continue
        seen.add(row_key)
        cleaned.append(trimmed)
    return cleaned, empty_count, duplicate_count


def write_xlsx(path: str | Path, headers: list[str], rows: list[list[str]]) -> None:
    """Write headers and cleaned rows into a simple Excel workbook."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Cleaned Data"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column_cells in sheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 40)
        sheet.column_dimensions[column_cells[0].column_letter].width = width
    workbook.save(path)
