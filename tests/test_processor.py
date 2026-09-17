import pytest

from processor import CsvProcessingError, clean_rows, read_csv, write_xlsx


def test_read_csv_detects_semicolon_and_preserves_headers(tmp_path):
    source = tmp_path / "people.csv"
    source.write_text("First Name;EMAIL\n Ada ; ada@example.com \n", encoding="utf-8")

    headers, rows, delimiter = read_csv(source)

    assert headers == ["First Name", "EMAIL"]
    assert rows == [[" Ada ", " ada@example.com "]]
    assert delimiter == ";"


def test_clean_rows_trims_removes_empty_and_deduplicates():
    rows = [[" Ada ", " a@example.com "], [" ", ""], ["Ada", "a@example.com"], ["Ben", " b@example.com "]]

    cleaned, empty_count, duplicate_count = clean_rows(rows)

    assert cleaned == [["Ada", "a@example.com"], ["Ben", "b@example.com"]]
    assert empty_count == 1
    assert duplicate_count == 1


def test_read_csv_rejects_inconsistent_rows(tmp_path):
    source = tmp_path / "broken.csv"
    source.write_text("name,email\nAda\n", encoding="utf-8")

    with pytest.raises(CsvProcessingError, match="Row 2 has 1 columns"):
        read_csv(source)


def test_read_csv_keeps_blank_lines_for_cleanup(tmp_path):
    source = tmp_path / "people.csv"
    source.write_text("name,city\nAda,Kyiv\n\nBen,Lviv\n", encoding="utf-8")

    headers, rows, delimiter = read_csv(source)

    assert headers == ["name", "city"]
    assert rows == [["Ada", "Kyiv"], ["", ""], ["Ben", "Lviv"]]
    assert delimiter == ","


def test_write_xlsx_creates_workbook(tmp_path):
    target = tmp_path / "cleaned.xlsx"
    write_xlsx(target, ["Name"], [["Ada"]])
    assert target.exists()
    assert target.read_bytes()[:2] == b"PK"
