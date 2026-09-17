from io import BytesIO

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({
        "TESTING": True,
        "SECRET_KEY": "test",
        "UPLOAD_FOLDER": tmp_path / "uploads",
        "EXPORT_FOLDER": tmp_path / "exports",
    })


def test_home_page_loads(app):
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b"Clean messy data" in response.data


def test_csv_upload_shows_cleaned_preview_and_download(app):
    client = app.test_client()
    response = client.post(
        "/upload",
        data={"file": (BytesIO(b"Name,City\n Ada , Kyiv \nAda,Kyiv\n,\n"), "people.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert b"Your data is tidy" in response.data
    assert b">1</strong><span>clean rows" in response.data
    assert b">1</strong><span>duplicates removed" in response.data

    exports = list(app.config["EXPORT_FOLDER"].glob("*.xlsx"))
    assert len(exports) == 1
    download = client.get(f"/download/{exports[0].name}")
    assert download.status_code == 200
    assert download.headers["Content-Type"].startswith("application/vnd.openxmlformats")


def test_rejects_non_csv_upload(app):
    response = app.test_client().post(
        "/upload",
        data={"file": (BytesIO(b"not a csv"), "report.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Unsupported file" in response.data
