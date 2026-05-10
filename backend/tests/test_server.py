"""Integration tests for the ScribeAI FastAPI backend.

Run with:  pytest backend/tests/ -v
Requires MongoDB to be running at the MONGO_URL in .env (or set TEST_MONGO_URL).
"""
import io
import os
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

from fastapi.testclient import TestClient

# Point at a throwaway test database so we don't touch production data
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "scribeai_test")

import server  # noqa: E402  (must come after env vars are set)

client = TestClient(server.app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_png_bytes(width: int = 100, height: int = 40, text: str = "hello") -> bytes:
    """Create a minimal in-memory PNG with some text drawn on it."""
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((5, 5), text, fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "status" in body
    assert "mongodb" in body
    assert "ocr_engines" in body


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

def test_root():
    resp = client.get("/api/")
    assert resp.status_code == 200
    assert resp.json()["version"] == "1.0.0"


# ---------------------------------------------------------------------------
# OCR upload
# ---------------------------------------------------------------------------

def test_upload_valid_image():
    png_bytes = _make_png_bytes()
    resp = client.post(
        "/api/ocr/upload",
        data={"preprocess": "false", "engine": "tesseract", "language": "eng"},
        files={"file": ("test.png", png_bytes, "image/png")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "image_id" in body
    assert body["is_pdf"] is False


def test_upload_invalid_file_type():
    resp = client.post(
        "/api/ocr/upload",
        data={"preprocess": "false"},
        files={"file": ("evil.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_oversized_image(monkeypatch):
    # Patch the size limit to 1 byte so any real file triggers it
    monkeypatch.setattr(server, "MAX_IMAGE_SIZE", 1)
    png_bytes = _make_png_bytes()
    resp = client.post(
        "/api/ocr/upload",
        data={"preprocess": "false"},
        files={"file": ("big.png", png_bytes, "image/png")},
    )
    assert resp.status_code == 413


# ---------------------------------------------------------------------------
# Notes CRUD
# ---------------------------------------------------------------------------

NOTE_PAYLOAD = {
    "title": "Test Note",
    "transcribed_text": "Hello world from the test suite",
    "original_image_path": "uploads/fake-id.png",
    "confidence": 0.85,
    "engine": "tesseract",
    "language": "eng",
}


@pytest.fixture
def created_note():
    resp = client.post("/api/notes", json=NOTE_PAYLOAD)
    assert resp.status_code == 200
    note = resp.json()
    yield note
    # Cleanup
    client.delete(f"/api/notes/{note['id']}")


def test_create_note(created_note):
    assert created_note["title"] == "Test Note"
    assert created_note["engine"] == "tesseract"


def test_get_notes(created_note):
    resp = client.get("/api/notes")
    assert resp.status_code == 200
    ids = [n["id"] for n in resp.json()]
    assert created_note["id"] in ids


def test_get_note_by_id(created_note):
    resp = client.get(f"/api/notes/{created_note['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created_note["id"]


def test_get_missing_note():
    resp = client.get("/api/notes/nonexistent-id")
    assert resp.status_code == 404


def test_update_note(created_note):
    resp = client.patch(
        f"/api/notes/{created_note['id']}",
        json={"title": "Updated Title"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Title"


def test_delete_note(created_note):
    note_id = created_note["id"]
    resp = client.delete(f"/api/notes/{note_id}")
    assert resp.status_code == 200
    # Confirm it's gone
    assert client.get(f"/api/notes/{note_id}").status_code == 404


# ---------------------------------------------------------------------------
# Folders
# ---------------------------------------------------------------------------

@pytest.fixture
def created_folder():
    resp = client.post("/api/folders", json={"name": "Test Folder", "color": "#ff0000"})
    assert resp.status_code == 200
    folder = resp.json()
    yield folder
    client.delete(f"/api/folders/{folder['id']}")


def test_create_folder(created_folder):
    assert created_folder["name"] == "Test Folder"


def test_get_folders(created_folder):
    resp = client.get("/api/folders")
    assert resp.status_code == 200
    ids = [f["id"] for f in resp.json()]
    assert created_folder["id"] in ids


def test_delete_folder(created_folder):
    folder_id = created_folder["id"]
    resp = client.delete(f"/api/folders/{folder_id}")
    assert resp.status_code == 200
    # Confirm it's gone
    folders = client.get("/api/folders").json()
    assert folder_id not in [f["id"] for f in folders]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def test_search_notes(created_note):
    resp = client.post("/api/search", json={"query": "hello world"})
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert "count" in body


def test_search_no_results():
    resp = client.post("/api/search", json={"query": "zzzzz_no_match_zzzzz"})
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# Path traversal guard
# ---------------------------------------------------------------------------

def test_ocr_process_path_traversal():
    resp = client.post(
        "/api/ocr/process",
        data={"image_path": "../../etc/passwd", "engine": "tesseract"},
    )
    assert resp.status_code == 400


def test_pdf_generate_path_traversal():
    resp = client.post(
        "/api/pdf/generate",
        data={"image_path": "../../etc/passwd", "text": "hi", "searchable": "true"},
    )
    assert resp.status_code == 400
