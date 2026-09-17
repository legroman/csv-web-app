from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from flask import Flask, flash, redirect, render_template, send_file, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from processor import CsvProcessingError, clean_rows, read_csv, write_xlsx


BASE_DIR = Path(__file__).resolve().parent
ALLOWED_EXTENSIONS = {"csv"}


def create_app(test_config: dict | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
        UPLOAD_FOLDER=BASE_DIR / "uploads",
        EXPORT_FOLDER=BASE_DIR / "exports",
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # 10 MB
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["EXPORT_FOLDER"]).mkdir(parents=True, exist_ok=True)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/upload")
    def upload():
        uploaded: FileStorage | None = request_file()
        if uploaded is None or not uploaded.filename:
            flash("Choose a CSV file before uploading.", "error")
            return redirect(url_for("index"))

        source_name = secure_filename(uploaded.filename)
        if not source_name or Path(source_name).suffix.lower().lstrip(".") not in ALLOWED_EXTENSIONS:
            flash("Unsupported file. Please upload a CSV file (.csv).", "error")
            return redirect(url_for("index"))

        # A UUID makes the stored source distinct, so it is never overwritten.
        stored_name = f"{uuid4().hex}_{source_name}"
        source_path = Path(app.config["UPLOAD_FOLDER"]) / stored_name
        uploaded.save(source_path)

        try:
            headers, rows, delimiter = read_csv(source_path)
            cleaned_rows, removed_empty, removed_duplicates = clean_rows(rows)
            export_name = f"cleaned_{uuid4().hex}.xlsx"
            export_path = Path(app.config["EXPORT_FOLDER"]) / export_name
            write_xlsx(export_path, headers, cleaned_rows)
        except CsvProcessingError as error:
            source_path.unlink(missing_ok=True)
            flash(str(error), "error")
            return redirect(url_for("index"))

        return render_template(
            "preview.html",
            headers=headers,
            rows=cleaned_rows[:100],
            total_rows=len(cleaned_rows),
            removed_empty=removed_empty,
            removed_duplicates=removed_duplicates,
            delimiter_name={",": "comma", ";": "semicolon", "\t": "tab"}[delimiter],
            download_url=url_for("download", filename=export_name),
        )

    @app.get("/download/<filename>")
    def download(filename: str):
        safe_name = secure_filename(filename)
        if safe_name != filename or not safe_name.endswith(".xlsx"):
            flash("The requested export could not be found.", "error")
            return redirect(url_for("index"))
        export_path = Path(app.config["EXPORT_FOLDER"]) / safe_name
        if not export_path.is_file():
            flash("The requested export could not be found.", "error")
            return redirect(url_for("index"))
        return send_file(export_path, as_attachment=True, download_name="cleaned_data.xlsx")

    @app.errorhandler(413)
    def file_too_large(_error):
        flash("That file is too large. Please upload a CSV smaller than 10 MB.", "error")
        return redirect(url_for("index"))

    return app


def request_file() -> FileStorage | None:
    """Keep request import local to make the app factory easy to test."""
    from flask import request

    return request.files.get("file")


if __name__ == "__main__":
    create_app().run(debug=True)
