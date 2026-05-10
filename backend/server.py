from contextlib import asynccontextmanager
import asyncio
import time as _time
_t0 = _time.perf_counter()
def _elapsed() -> str:
    return f"{_time.perf_counter() - _t0:.1f}s"

print(f"[startup] Python started ({_elapsed()})")

from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import logging.handlers
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone
from PIL import Image
import io
import base64
import shutil

print(f"[startup] stdlib/fastapi/pydantic done ({_elapsed()})")

from knowledge_graph import knowledge_graph_generator
print(f"[startup] knowledge_graph ({_elapsed()})")

from ocr_engine import ocr_engine
print(f"[startup] ocr_engine ({_elapsed()})")

from image_preprocessing import image_preprocessor
print(f"[startup] image_preprocessing ({_elapsed()})")

from pdf_generator import pdf_generator
print(f"[startup] pdf_generator ({_elapsed()})")

from rag_engine import rag_engine, EMBED_MODEL_NAME, EMBED_DIM, FAISS_INDEX_PATH
print(f"[startup] rag_engine ({_elapsed()})")

from pdf_processor import pdf_processor
print(f"[startup] pdf_processor ({_elapsed()})")

from voice_agent import voice_engine, AUDIO_DIR
print(f"[startup] voice_agent ({_elapsed()})")

from tabular_extractor import tabular_extractor
print(f"[startup] tabular_extractor ({_elapsed()})")

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
# serverSelectionTimeoutMS: fail fast instead of the 30s default, which
# multiplied across 5 sequential create_index calls = 2.5 min hang if DB is down.
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client[os.environ['DB_NAME']]

# Configure logging
LOG_DIR = ROOT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "app.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logging.getLogger().addHandler(file_handler)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[startup] lifespan: connecting to MongoDB ({_elapsed()})")
    await db.notes.create_index("id", unique=True)
    await db.notes.create_index("folder_id")
    await db.notes.create_index("created_at")
    await db.folders.create_index("id", unique=True)
    await db.recordings.create_index("id", unique=True)
    await db.recordings.create_index("created_at")
    await db.recordings.create_index("folder_id")
    logger.info("MongoDB indexes created")
    print(f"[startup] ready — total startup time {_elapsed()}")

    # Pre-warm embedding model + FAISS in the background so the first RAG
    # query doesn't pay the 30-60s cold-load cost.
    async def _warmup():
        try:
            await rag_engine.embed_text("warmup")
            _ = rag_engine.store  # initialise FAISS store
            logger.info("RAG warmup complete (embedding model + FAISS ready)")
        except Exception as e:
            logger.warning(f"RAG warmup failed (non-fatal): {e}")

    asyncio.create_task(_warmup())
    yield
    client.close()

# Create the main app without a prefix
app = FastAPI(title="ScribeAI API", version="1.0.0", lifespan=lifespan)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Create upload directories
UPLOAD_DIR = ROOT_DIR / "uploads"
PROCESSED_DIR = ROOT_DIR / "processed"
PDF_DIR = ROOT_DIR / "pdfs"

for directory in [UPLOAD_DIR, PROCESSED_DIR, PDF_DIR, AUDIO_DIR]:
    directory.mkdir(exist_ok=True)

MAX_IMAGE_SIZE = 20 * 1024 * 1024   # 20 MB
MAX_PDF_SIZE   = 50 * 1024 * 1024   # 50 MB
MAX_AUDIO_SIZE = 500 * 1024 * 1024  # 500 MB

# Magic-byte signatures for supported file types
_IMAGE_SIGNATURES = [
    b'\xff\xd8\xff',           # JPEG
    b'\x89PNG\r\n\x1a\n',     # PNG
    b'GIF87a', b'GIF89a',     # GIF
    b'RIFF',                   # WebP (starts with RIFF....WEBP)
    b'BM',                     # BMP
    b'\x49\x49\x2a\x00',      # TIFF LE
    b'\x4d\x4d\x00\x2a',      # TIFF BE
]
_PDF_SIGNATURE = b'%PDF'

# ============ Pydantic Models ============

class NoteCreate(BaseModel):
    title: str
    transcribed_text: str
    original_image_path: str
    processed_image_path: Optional[str] = None
    pdf_path: Optional[str] = None
    confidence: float
    engine: str
    language: str = "eng"
    folder_id: Optional[str] = None
    tags: List[str] = []

class Note(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    transcribed_text: str
    original_image_path: str
    processed_image_path: Optional[str] = None
    pdf_path: Optional[str] = None
    confidence: float
    engine: str
    language: str = "eng"
    folder_id: Optional[str] = None
    tags: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RAGQueryRequest(BaseModel):
    question: str
    folder_id: Optional[str] = None
    history: List[Dict[str, Any]] = []

class NoteUpdate(BaseModel):
    title: Optional[str] = None
    transcribed_text: Optional[str] = None
    folder_id: Optional[str] = None
    tags: Optional[List[str]] = None

class Folder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    color: str = "#2563EB"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FolderCreate(BaseModel):
    name: str
    color: str = "#2563EB"

class OCRRequest(BaseModel):
    image_id: str
    engine: str = "trocr"
    language: str = "eng"
    preprocess: bool = True

class SearchRequest(BaseModel):
    query: str
    folder_id: Optional[str] = None

class TabularExtractRequest(BaseModel):
    query: str
    folder_id: Optional[str] = None
    columns: Optional[List[str]] = None
    note_ids: Optional[List[str]] = None

# ============ Helper Functions ============

def _fix_datetime_fields(doc: dict) -> dict:
    """Convert ISO string datetime fields back to datetime objects."""
    for field in ("created_at", "updated_at"):
        if isinstance(doc.get(field), str):
            doc[field] = datetime.fromisoformat(doc[field])
    return doc

async def _validate_upload(file: UploadFile) -> tuple[bytes, bool]:
    """Read file header, validate magic bytes, enforce size limits.
    Returns (header_bytes, is_pdf). Raises HTTPException on failure."""
    header = await file.read(12)
    await file.seek(0)

    is_pdf = header[:4] == _PDF_SIGNATURE
    is_image = any(header[:len(sig)] == sig for sig in _IMAGE_SIGNATURES)
    # WebP extra check: bytes 8-12 must be 'WEBP'
    if header[:4] == b'RIFF' and header[8:12] != b'WEBP':
        is_image = False

    if not is_pdf and not is_image:
        raise HTTPException(status_code=400, detail="File must be a valid image (JPEG, PNG, GIF, WebP, BMP, TIFF) or PDF")

    size_limit = MAX_PDF_SIZE if is_pdf else MAX_IMAGE_SIZE
    content_length = file.size if hasattr(file, "size") and file.size else None
    if content_length and content_length > size_limit:
        limit_mb = size_limit // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {limit_mb} MB.")

    return header, is_pdf

def save_image_from_upload(upload_file: UploadFile, directory: Path) -> str:
    """Save uploaded image to disk"""
    file_id = str(uuid.uuid4())

    original_filename = upload_file.filename or "upload.png"
    file_extension = Path(original_filename).suffix or ".png"

    file_path = directory / f"{file_id}{file_extension}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return str(file_path)

def image_to_base64(image_path: str) -> str:
    """Convert image to base64 string"""
    try:
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
            return f"data:image/png;base64,{encoded}"
    except Exception as e:
        logger.error(f"Failed to encode image: {str(e)}")
        return ""

def resolve_storage_path(image_path: str) -> Path:
    """Resolve a stored image path to a safe local path inside backend storage directories."""
    candidate = Path(image_path)
    if not candidate.is_absolute():
        candidate = ROOT_DIR / candidate

    candidate = candidate.resolve()
    allowed_roots = [UPLOAD_DIR.resolve(), PROCESSED_DIR.resolve(), PDF_DIR.resolve()]

    if not any(str(candidate).startswith(str(root)) for root in allowed_roots):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not candidate.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return candidate


def normalize_ocr_languages(languages: Optional[str]) -> str:
    """Normalize OCR language input and default to English when omitted."""
    tokens = [token.strip() for token in (languages or "").split("+") if token.strip()]
    if not tokens:
        return "eng"

    normalized_tokens = []
    seen = set()
    for token in tokens:
        if token not in seen:
            normalized_tokens.append(token)
            seen.add(token)

    return "+".join(normalized_tokens)

# ============ API Routes ============

@api_router.get("/")
async def root():
    return {
        "message": "ScribeAI API",
        "version": "1.0.0",
        "endpoints": {
            "notes": "/api/notes",
            "ocr": "/api/ocr",
            "folders": "/api/folders",
            "search": "/api/search",
            "rag": "/api/rag",
            "voice": "/api/voice",
            "extract": "/api/extract",
        }
    }

# ============ OCR Routes ============

@api_router.post("/ocr/upload")
async def upload_image(
    file: UploadFile = File(...),
    preprocess: bool = Form(True),
    engine: str = Form("gemini"),
    language: str = Form("eng"),
):
    """Upload and optionally preprocess an image or PDF"""
    try:
        _, is_pdf = await _validate_upload(file)

        original_path = save_image_from_upload(file, UPLOAD_DIR)
        logger.info(f"File uploaded: {original_path}")

        MAX_PDF_PAGES = 15

        if is_pdf:
            # Rename to .pdf so pypdfium2 handles it correctly
            pdf_path = str(Path(original_path).with_suffix(".pdf"))
            Path(original_path).rename(pdf_path)
            original_path = pdf_path

            total_pages = pdf_processor.page_count(original_path)
            normalized_language = normalize_ocr_languages(language)

            # Try extracting the embedded text layer first — instant and perfect for
            # PDFs that already have selectable text (e.g. digitally-created or pre-OCR'd)
            try:
                layer_text, has_layer = pdf_processor.extract_text_layer(
                    original_path, max_pages=MAX_PDF_PAGES
                )
            except Exception as e:
                logger.warning(f"Text layer extraction failed, falling back to OCR: {e}")
                layer_text, has_layer = "", False

            if has_layer:
                # Render only the first page for the preview image
                first_page_images = pdf_processor.pdf_to_images(
                    original_path, max_pages=1
                )
                if first_page_images:
                    preview_id = str(uuid.uuid4())
                    preview_path = PROCESSED_DIR / f"{preview_id}.png"
                    first_page_images[0].save(preview_path, format="PNG")
                else:
                    preview_path = None

                return {
                    "success": True,
                    "text": layer_text.strip(),
                    "image_id": Path(original_path).stem,
                    "original_path": original_path,
                    "processed_path": str(preview_path) if preview_path else None,
                    "confidence": 1.0,
                    "engine": "pdf_text_layer",
                    "language": normalized_language,
                    "total_pages": total_pages,
                    "pages_processed": min(MAX_PDF_PAGES, total_pages),
                    "has_text_layer": True,
                }

            # No text layer, run OCR on each page
            logger.info(f"PDF has no text layer, running OCR on {min(total_pages, MAX_PDF_PAGES)} pages")

            # Render pages to images at 2.5x (approximately 180 DPI for letter-size pages)
            page_images = pdf_processor.pdf_to_images(
                original_path, max_pages=MAX_PDF_PAGES
            )

            if not page_images:
                raise HTTPException(status_code=422, detail="Failed to render PDF pages")

            # Use batch API for engines that support it (faster, fewer round trips)
            if engine == "mistral":
                combined_text, _ = ocr_engine.extract_with_mistral_batch(page_images)
            elif engine == "gemini":
                combined_text, _ = ocr_engine.extract_with_gemini_batch(page_images)
            else:
                all_texts = []
                for idx, page_img in enumerate(page_images):
                    if preprocess:
                        page_img = image_preprocessor.preprocess_for_engine(page_img, engine=engine)
                    ocr_result = ocr_engine.extract_text(page_img, engine=engine, languages=normalized_language)
                    if ocr_result["success"]:
                        all_texts.append(ocr_result["text"])
                    else:
                        logger.warning(f"OCR failed for page {idx + 1}: {ocr_result.get('error')}")
                combined_text = "\n\n---\n\n".join(all_texts)

            # Save the first page as processed preview
            preview_id = str(uuid.uuid4())
            preview_path = PROCESSED_DIR / f"{preview_id}.png"
            page_images[0].save(preview_path, format="PNG")

            return {
                "success": True,
                "text": combined_text.strip(),
                "image_id": Path(original_path).stem,
                "original_path": original_path,
                "processed_path": str(preview_path),
                "confidence": 0.9,
                "engine": engine,
                "language": normalized_language,
                "total_pages": total_pages,
                "pages_processed": len(page_images),
                "has_text_layer": False,
            }

        # Single image upload
        image = Image.open(original_path)
        processed_image = image

        if preprocess:
            processed_image = image_preprocessor.preprocess_for_engine(image, engine=engine)

            processed_id = str(uuid.uuid4())
            processed_path = PROCESSED_DIR / f"{processed_id}.png"
            processed_image.save(processed_path)
        else:
            processed_path = None

        # OCR
        normalized_language = normalize_ocr_languages(language)
        result = ocr_engine.extract_text(processed_image, engine=engine, languages=normalized_language)

        if not result["success"]:
            raise HTTPException(status_code=422, detail=result.get("error", "OCR failed"))

        return {
            "success": True,
            "text": result["text"],
            "image_id": Path(original_path).stem,
            "original_path": original_path,
            "processed_path": str(processed_path) if processed_path else original_path,
            "confidence": result.get("confidence", 0.0),
            "engine": engine,
            "language": normalized_language,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ocr/process")
async def process_image(req: OCRRequest):
    """Process an already uploaded image with specific OCR engine"""
    try:
        # Search UPLOAD_DIR (all extensions) then PROCESSED_DIR
        candidates = [
            UPLOAD_DIR / f"{req.image_id}.png",
            UPLOAD_DIR / f"{req.image_id}.jpg",
            UPLOAD_DIR / f"{req.image_id}.pdf",
            PROCESSED_DIR / f"{req.image_id}.png",
            PROCESSED_DIR / f"{req.image_id}.jpg",
        ]
        image_path = next((p for p in candidates if p.exists()), None)
        if image_path is None:
            raise HTTPException(status_code=404, detail="Image not found")

        safe_path = resolve_storage_path(str(image_path))
        normalized_language = normalize_ocr_languages(req.language)

        # Remap non-reprocessable engine names to best available
        engine = req.engine
        if engine in ("pdf_text_layer", "auto", ""):
            engine = "mistral" if os.environ.get("MISTRAL_API_KEY") else (
                "gemini" if (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")) else "tesseract"
            )

        # PDF re-process: run full multi-page OCR (capped at 15 pages)
        if str(safe_path).lower().endswith(".pdf"):
            page_images = pdf_processor.pdf_to_images(str(safe_path), max_pages=15)
            if not page_images:
                raise HTTPException(status_code=422, detail="Failed to render PDF pages")
            if engine == "mistral":
                text, confidence = ocr_engine.extract_with_mistral_batch(page_images)
            elif engine == "gemini":
                text, confidence = ocr_engine.extract_with_gemini_batch(page_images)
            else:
                parts = []
                for img in page_images:
                    r = ocr_engine.extract_text(img, engine=engine, languages=normalized_language)
                    parts.append(r.get("text", ""))
                text = "\n\n".join(parts)
                confidence = 0.9
            preview_id = str(uuid.uuid4())
            preview_path = PROCESSED_DIR / f"{preview_id}.png"
            page_images[0].save(preview_path, format="PNG")
            return {
                "success": True,
                "text": text,
                "image_id": req.image_id,
                "processed_path": str(preview_path),
                "confidence": confidence,
                "engine": req.engine,
                "language": normalized_language,
            }

        image = Image.open(safe_path)
        processed_image = image
        if req.preprocess:
            processed_image = image_preprocessor.preprocess_for_engine(image, engine=req.engine)
            processed_id = str(uuid.uuid4())
            processed_path = PROCESSED_DIR / f"{processed_id}.png"
            processed_image.save(processed_path)
        else:
            processed_path = image_path

        result = ocr_engine.extract_text(processed_image, engine=req.engine, languages=normalized_language)

        if not result["success"]:
            raise HTTPException(status_code=422, detail=result.get("error", "OCR failed"))

        return {
            "success": True,
            "text": result["text"],
            "image_id": req.image_id,
            "processed_path": str(processed_path),
            "confidence": result.get("confidence", 0.0),
            "engine": req.engine,
            "language": normalized_language,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ocr/batch")
async def batch_ocr(
    files: List[UploadFile] = File(...),
    engine: str = Form("gemini"),
    language: str = Form("eng")
):
    """Process multiple images in batch"""
    results = []

    for file in files:
        try:
            _, is_pdf = await _validate_upload(file)
            if is_pdf:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": "PDF not supported in batch mode"
                })
                continue

            original_path = save_image_from_upload(file, UPLOAD_DIR)
            image = Image.open(original_path)

            normalized_language = normalize_ocr_languages(language)
            result = ocr_engine.extract_text(image, engine=engine, languages=normalized_language)

            results.append({
                "filename": file.filename,
                "success": result["success"],
                "text": result.get("text", ""),
                "original_path": original_path,
                "confidence": result.get("confidence", 0.0),
                "error": result.get("error")
            })

        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })

    return {"results": results, "total": len(results)}

@api_router.get("/images")
async def get_image(path: str):
    """Serve an uploaded or processed image"""
    try:
        safe_path = resolve_storage_path(path)
        return FileResponse(safe_path)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/pdf/pages")
async def get_pdf_pages(path: str, max_pages: int = 0):
    """Render every page of a PDF as PNGs and return their preview URLs.

    Pages are cached on disk as `{pdf_stem}_p{N}.png` so repeat views are instant.
    Pass max_pages > 0 to cap; default 0 means render all pages.
    For non-PDF inputs, falls back to returning the single image path.
    """
    try:
        safe_path = resolve_storage_path(path)
        path_str = str(safe_path)

        if not path_str.lower().endswith(".pdf"):
            return {"pages": [path_str], "total_pages": 1, "is_pdf": False}

        total_pages = pdf_processor.page_count(path_str)
        page_count = min(total_pages, max_pages) if max_pages > 0 else total_pages
        stem = safe_path.stem

        cached_paths: List[str] = []
        missing_indices: List[int] = []
        for i in range(page_count):
            cache_path = PROCESSED_DIR / f"{stem}_p{i + 1}.png"
            cached_paths.append(str(cache_path))
            if not cache_path.exists():
                missing_indices.append(i)

        if missing_indices:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(path_str)
            try:
                for i in missing_indices:
                    page = doc[i]
                    bitmap = page.render(scale=2.0, rotation=0)
                    pil_image = bitmap.to_pil().convert("RGB")
                    pil_image.save(cached_paths[i], format="PNG", optimize=True)
                    bitmap.close()
                    page.close()
            finally:
                doc.close()

        return {
            "pages": cached_paths,
            "total_pages": total_pages,
            "rendered_pages": page_count,
            "is_pdf": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF pages render failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Notes Routes ============

@api_router.post("/notes", response_model=Note)
async def create_note(note_data: NoteCreate):
    """Create a new note"""
    try:
        note = Note(**note_data.model_dump())

        doc = note.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()

        await db.notes.insert_one(doc)

        # Index in FAISS
        try:
            await rag_engine.index_note(note.id, note.title, note.transcribed_text)
        except Exception as e:
            logger.warning(f"FAISS indexing failed: {e}")

        return note

    except Exception as e:
        logger.error(f"Failed to create note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/notes", response_model=List[Note])
async def get_notes(folder_id: Optional[str] = None, limit: int = 100):
    """Get all notes, optionally filtered by folder"""
    try:
        query = {}
        if folder_id:
            query["folder_id"] = folder_id

        notes = await db.notes.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)

        return [_fix_datetime_fields(n) for n in notes]

    except Exception as e:
        logger.error(f"Failed to get notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/notes/{note_id}", response_model=Note)
async def get_note(note_id: str):
    """Get a specific note by ID"""
    try:
        note = await db.notes.find_one({"id": note_id}, {"_id": 0})

        if not note:
            raise HTTPException(status_code=404, detail="Note not found")

        return _fix_datetime_fields(note)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.patch("/notes/{note_id}", response_model=Note)
async def update_note(note_id: str, note_update: NoteUpdate):
    """Update a note"""
    try:
        update_data = {k: v for k, v in note_update.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        result = await db.notes.update_one(
            {"id": note_id},
            {"$set": update_data}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")

        # Re-index in FAISS if text or title changed
        if "title" in update_data or "transcribed_text" in update_data:
            note = await db.notes.find_one({"id": note_id}, {"_id": 0})
            if note:
                try:
                    await rag_engine.remove_note(note_id)
                    await rag_engine.index_note(
                        note_id,
                        note.get("title", ""),
                        note.get("transcribed_text", "")
                    )
                except Exception as e:
                    logger.warning(f"FAISS re-indexing failed: {e}")

        note = await db.notes.find_one({"id": note_id}, {"_id": 0})
        return _fix_datetime_fields(note)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/notes/{note_id}")
async def delete_note(note_id: str):
    """Delete a note"""
    try:
        result = await db.notes.delete_one({"id": note_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Note not found")

        # Remove from FAISS
        try:
            await rag_engine.remove_note(note_id)
        except Exception as e:
            logger.warning(f"FAISS removal skipped: {e}")

        return {"success": True, "message": "Note deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Folder Routes ============

@api_router.post("/folders", response_model=Folder)
async def create_folder(folder_data: FolderCreate):
    """Create a new folder (rejects duplicate names case-insensitively)"""
    try:
        existing = await db.folders.find_one(
            {"name": {"$regex": f"^{folder_data.name.strip()}$", "$options": "i"}},
            {"_id": 0},
        )
        if existing:
            raise HTTPException(status_code=409, detail=f"A folder named \"{folder_data.name}\" already exists")

        folder = Folder(**folder_data.model_dump())
        doc = folder.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.folders.insert_one(doc)
        return folder

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/folders", response_model=List[Folder])
async def get_folders():
    """Get all folders"""
    try:
        folders = await db.folders.find({}, {"_id": 0}).sort("name", 1).to_list(100)

        return [_fix_datetime_fields(f) for f in folders]

    except Exception as e:
        logger.error(f"Failed to get folders: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str):
    """Delete a folder"""
    try:
        result = await db.folders.delete_one({"id": folder_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Folder not found")

        # Optional: Remove folder_id from all notes
        await db.notes.update_many(
            {"folder_id": folder_id},
            {"$set": {"folder_id": None}}
        )

        return {"success": True, "message": "Folder deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Search Route ============

@api_router.post("/search")
async def search_notes(search_data: SearchRequest):
    """Search notes by text content"""
    try:
        query: Dict[str, Any] = {
            "$or": [
                {"title": {"$regex": search_data.query, "$options": "i"}},
                {"transcribed_text": {"$regex": search_data.query, "$options": "i"}},
                {"tags": {"$regex": search_data.query, "$options": "i"}}
            ]
        }

        if search_data.folder_id:
            query["folder_id"] = search_data.folder_id

        notes = await db.notes.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
        return {"results": [_fix_datetime_fields(n) for n in notes], "count": len(notes)}

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ RAG Routes ============

@api_router.post("/rag/query")
async def rag_query(req: RAGQueryRequest):
    """Ask a natural language question about your notes"""
    try:
        result = await rag_engine.query(
            question=req.question,
            db=db,
            folder_id=req.folder_id,
            history=req.history,
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"RAG query failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/rag/reindex")
async def rag_reindex():
    """Rebuild the entire FAISS index from all notes in MongoDB"""
    try:
        result = await rag_engine.reindex_all(db)
        return {
            "success": True,
            "indexed": result["indexed"],
            "skipped": result["skipped"],
            "total": result["total"],
        }
    except Exception as e:
        logger.error(f"Reindex failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/rag/stats")
async def rag_stats():
    """FAISS index statistics"""
    return {
        "total_vectors": rag_engine.store.count,
        "embedding_model": EMBED_MODEL_NAME,
        "embedding_dim": EMBED_DIM,
        "index_file": str(FAISS_INDEX_PATH) if FAISS_INDEX_PATH.exists() else None,
    }

@api_router.get("/rag/debug/chunks")
async def rag_debug_chunks():
    """Show how many chunks each note would produce — does NOT modify the index."""
    from rag_engine import _split_note_chunks, NOTE_CHUNK_SEP
    notes = await db.notes.find({}, {"_id": 0, "id": 1, "title": 1, "transcribed_text": 1}).to_list(1000)
    result = []
    for note in notes:
        text = note.get("transcribed_text", "")
        chunks = _split_note_chunks(text)
        result.append({
            "id": note["id"],
            "title": note.get("title", "Untitled"),
            "text_chars": len(text),
            "text_words": len(text.split()),
            "chunk_count": len(chunks),
            "text_preview": text[:120].replace("\r", "\\r").replace("\n", "\\n"),
        })
    meta_ids = [m["id"] for m in rag_engine.store.metadata]
    note_chunks_in_faiss = [mid for mid in meta_ids if NOTE_CHUNK_SEP in mid]
    return {
        "notes": result,
        "faiss_total": rag_engine.store.count,
        "note_chunks_in_faiss": len(note_chunks_in_faiss),
        "note_chunk_sep": NOTE_CHUNK_SEP,
    }

# ============ Voice-to-Note Linking Routes ============

@api_router.post("/voice/upload")
async def upload_and_transcribe(
    file: UploadFile = File(...),
    language: str = Form("en"),
    folder_id: Optional[str] = Form(None),
):
    """Upload an audio file, transcribe it, and auto-link to related notes."""
    try:
        # Validate file type
        allowed_extensions = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm", ".ogg"}
        ext = Path(file.filename or "audio.wav").suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported audio format: {ext}. Supported: {', '.join(allowed_extensions)}"
            )

        # Allow up to 500MB — voice_engine will compress & chunk if needed
        contents = await file.read()
        if len(contents) > MAX_AUDIO_SIZE:
            raise HTTPException(status_code=413, detail="Audio file must be under 500MB")

        # Save audio file
        audio_id = str(uuid.uuid4())
        audio_path = AUDIO_DIR / f"{audio_id}{ext}"
        with open(audio_path, "wb") as f:
            f.write(contents)

        logger.info(f"Audio uploaded: {audio_path} ({len(contents) / 1024:.0f} KB)")

        # Transcribe
        result = voice_engine.transcribe_audio(str(audio_path), language=language)

        if not result["success"]:
            raise HTTPException(status_code=422, detail=result.get("error", "Transcription failed"))

        # Find linked notes using FAISS similarity
        linked_notes = await voice_engine.find_linked_notes(
            result["text"], rag_engine, db, folder_id=folder_id
        )

        # Store the recording in MongoDB
        recording_doc = {
            "id": audio_id,
            "filename": file.filename,
            "audio_path": str(audio_path),
            "transcript": result["text"],
            "duration_seconds": result.get("duration_seconds"),
            "segments": result.get("segments", []),
            "word_count": result["word_count"],
            "language": language,
            "folder_id": folder_id,
            "linked_note_ids": [n["id"] for n in linked_notes],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.recordings.insert_one(recording_doc)

        # Index transcript in FAISS — chunk long transcripts for better retrieval
        try:
            from rag_engine import CHUNK_SEP
            CHUNK_WORDS = 300
            CHUNK_OVERLAP = 50
            words = result["text"].split()
            chunk_title = f"Recording: {file.filename}"

            if len(words) <= CHUNK_WORDS:
                await rag_engine.index_note(audio_id, chunk_title, result["text"])
            else:
                pos, idx = 0, 0
                while pos < len(words):
                    chunk_text = " ".join(words[pos: pos + CHUNK_WORDS])
                    await rag_engine.index_note(
                        f"{audio_id}{CHUNK_SEP}{idx}", chunk_title, chunk_text
                    )
                    pos += CHUNK_WORDS - CHUNK_OVERLAP
                    idx += 1
                logger.info(f"Indexed recording in {idx} FAISS chunks")
        except Exception as e:
            logger.warning(f"Failed to index recording in FAISS: {e}")

        return {
            "success": True,
            "recording_id": audio_id,
            "transcript": result["text"],
            "word_count": result["word_count"],
            "duration_seconds": result.get("duration_seconds"),
            "processing_time": result["processing_time"],
            "linked_notes": [
                {
                    "id": n["id"],
                    "title": n.get("title", "Untitled"),
                    "snippet": n.get("transcribed_text", "")[:150] + "...",
                    "similarity": n["link_score"],
                }
                for n in linked_notes
            ],
            "total_linked": len(linked_notes),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/voice/recordings")
async def get_recordings(folder_id: Optional[str] = None, limit: int = 50):
    """List all audio recordings with their linked notes."""
    try:
        query = {"folder_id": folder_id} if folder_id else {}
        recordings = await db.recordings.find(query, {"_id": 0}).sort(
            "created_at", -1
        ).to_list(limit)
        return {"recordings": recordings, "count": len(recordings)}
    except Exception as e:
        logger.error(f"Failed to fetch recordings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/voice/recordings/{recording_id}")
async def get_recording(recording_id: str):
    """Get a specific recording with its transcript and linked notes."""
    try:
        recording = await db.recordings.find_one({"id": recording_id}, {"_id": 0})
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")

        # Fetch full linked note details
        linked_ids = recording.get("linked_note_ids", [])
        if linked_ids:
            linked_notes = await db.notes.find(
                {"id": {"$in": linked_ids}}, {"_id": 0}
            ).to_list(len(linked_ids))
            recording["linked_notes"] = linked_notes

        return recording

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/voice/recordings/{recording_id}")
async def delete_recording(recording_id: str):
    """Delete a recording and remove it from FAISS index."""
    try:
        result = await db.recordings.delete_one({"id": recording_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Recording not found")

        # Remove from FAISS (including all chunks)
        try:
            await rag_engine.remove_recording(recording_id)
        except Exception as e:
            logger.warning(f"FAISS removal for recording skipped: {e}")

        # Delete audio file
        for ext in [".mp3", ".wav", ".m4a", ".webm", ".ogg", ".mp4", ".mpeg", ".mpga"]:
            audio_file = AUDIO_DIR / f"{recording_id}{ext}"
            if audio_file.exists():
                audio_file.unlink()
                break

        return {"success": True, "message": "Recording deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete recording: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/voice/relink/{recording_id}")
async def relink_recording(recording_id: str):
    """Re-run the linking algorithm for a recording (useful after adding new notes)."""
    try:
        recording = await db.recordings.find_one({"id": recording_id}, {"_id": 0})
        if not recording:
            raise HTTPException(status_code=404, detail="Recording not found")

        linked_notes = await voice_engine.find_linked_notes(
            recording.get("transcript", ""), rag_engine, db,
            folder_id=recording.get("folder_id"),
        )

        new_linked_ids = [n["id"] for n in linked_notes]
        await db.recordings.update_one(
            {"id": recording_id},
            {"$set": {"linked_note_ids": new_linked_ids}},
        )

        return {
            "success": True,
            "recording_id": recording_id,
            "linked_notes": [
                {
                    "id": n["id"],
                    "title": n.get("title", "Untitled"),
                    "similarity": n["link_score"],
                }
                for n in linked_notes
            ],
            "total_linked": len(linked_notes),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Relinking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Tabular Extraction Routes ============

@api_router.post("/extract/table")
async def extract_table(req: TabularExtractRequest):
    """Extract structured data across notes into a cited table.

    Examples:
        - query: "all definitions"
        - query: "list all formulas"
        - query: "find key dates and events"
        - query: "extract all theorems"
    """
    try:
        # Fetch notes
        mongo_query: Dict[str, Any] = {}
        if req.note_ids:
            mongo_query["id"] = {"$in": req.note_ids}
        if req.folder_id:
            mongo_query["folder_id"] = req.folder_id

        notes = await db.notes.find(
            mongo_query, {"_id": 0, "embedding": 0}
        ).sort("created_at", -1).to_list(100)

        if not notes:
            raise HTTPException(status_code=404, detail="No notes found")

        result = await tabular_extractor.extract(
            query=req.query,
            notes=notes,
            columns=req.columns,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tabular extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/extract/definitions")
async def extract_definitions(folder_id: Optional[str] = None):
    """One-click: Extract all definitions from notes."""
    try:
        query: Dict[str, Any] = {}
        if folder_id:
            query["folder_id"] = folder_id

        notes = await db.notes.find(query, {"_id": 0, "embedding": 0}).to_list(100)
        if not notes:
            raise HTTPException(status_code=404, detail="No notes found")

        return await tabular_extractor.extract_definitions(notes)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Definition extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/extract/formulas")
async def extract_formulas(folder_id: Optional[str] = None):
    """One-click: Extract all formulas from notes."""
    try:
        query: Dict[str, Any] = {}
        if folder_id:
            query["folder_id"] = folder_id

        notes = await db.notes.find(query, {"_id": 0, "embedding": 0}).to_list(100)
        if not notes:
            raise HTTPException(status_code=404, detail="No notes found")

        return await tabular_extractor.extract_formulas(notes)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Formula extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/extract/key-points")
async def extract_key_points(folder_id: Optional[str] = None):
    """One-click: Extract key points from notes."""
    try:
        query: Dict[str, Any] = {}
        if folder_id:
            query["folder_id"] = folder_id

        notes = await db.notes.find(query, {"_id": 0, "embedding": 0}).to_list(100)
        if not notes:
            raise HTTPException(status_code=404, detail="No notes found")

        return await tabular_extractor.extract_key_points(notes)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Key points extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/extract/dates")
async def extract_dates(folder_id: Optional[str] = None):
    """One-click: Extract dates and events from notes."""
    try:
        query: Dict[str, Any] = {}
        if folder_id:
            query["folder_id"] = folder_id

        notes = await db.notes.find(query, {"_id": 0, "embedding": 0}).to_list(100)
        if not notes:
            raise HTTPException(status_code=404, detail="No notes found")

        return await tabular_extractor.extract_dates_events(notes)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dates extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Knowledge Graph Route ============

@api_router.get("/graph/knowledge")
async def get_knowledge_graph(
    folder_id: Optional[str] = None,
    max_nodes: int = 100,
):
    """Generate knowledge graph showing connections between notes and recordings.
    
    Returns nodes (notes + recordings) and edges (similarity links).
    Nodes are sized by content length, edges are weighted by similarity score.
    """
    try:
        graph_data = await knowledge_graph_generator.generate_graph(
            rag_engine=rag_engine,
            db=db,
            folder_id=folder_id,
            max_nodes=max_nodes,
        )
        return graph_data
    except Exception as e:
        logger.error(f"Knowledge graph generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/graph/clusters")
async def get_topic_clusters(
    folder_id: Optional[str] = None,
    max_k: int = 8,
):
    """Cluster notes by topic using K-means on embedding vectors.

    Returns clusters with LLM-generated 2-3 word labels and coverage scores.
    Under-covered clusters (few notes, low word count) are listed first.
    """
    try:
        cluster_data = await knowledge_graph_generator.generate_clusters(
            rag_engine=rag_engine,
            db=db,
            folder_id=folder_id,
            max_k=max_k,
        )
        return cluster_data
    except Exception as e:
        logger.error(f"Topic cluster generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/progress")
async def get_study_progress(folder_id: Optional[str] = None):
    """Study progress report derived from topic clusters.

    Returns overall coverage score, total stats, and clusters pre-segmented
    into three buckets: gaps (< 35%), moderate (35–70%), and strong (≥ 70%).
    Under-covered topics are surfaced first so students can prioritise exam prep.
    """
    try:
        cluster_data = await knowledge_graph_generator.generate_clusters(
            rag_engine=rag_engine,
            db=db,
            folder_id=folder_id,
        )

        clusters = cluster_data.get("clusters", [])
        total_notes = cluster_data.get("total_notes", 0)
        total_recordings = cluster_data.get("total_recordings", 0)
        indexed = cluster_data.get("indexed_items", 0)

        if not clusters:
            return {
                "overall_coverage": 0.0,
                "total_topics": 0,
                "total_notes": total_notes,
                "total_recordings": total_recordings,
                "total_words": 0,
                "gaps": [],
                "moderate": [],
                "strong": [],
                "needs_reindex": indexed == 0 and (total_notes + total_recordings) > 0,
            }

        all_items = sum(c["note_count"] + c.get("recording_count", 0) for c in clusters)
        total_words = sum(c["total_words"] for c in clusters)

        # Weighted average by item count
        overall = (
            sum(c["coverage_score"] * (c["note_count"] + c.get("recording_count", 0)) for c in clusters) / all_items
            if all_items > 0 else 0.0
        )

        gaps     = [c for c in clusters if c["coverage_score"] < 0.35]
        moderate = [c for c in clusters if 0.35 <= c["coverage_score"] < 0.70]
        strong   = [c for c in clusters if c["coverage_score"] >= 0.70]

        return {
            "overall_coverage": round(overall, 2),
            "total_topics": len(clusters),
            "total_notes": total_notes,
            "total_recordings": total_recordings,
            "total_words": total_words,
            "gaps": gaps,
            "moderate": moderate,
            "strong": strong,
            "needs_reindex": indexed == 0 and (total_notes + total_recordings) > 0,
        }
    except Exception as e:
        logger.error(f"Study progress report failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ PDF Routes ============

@api_router.post("/pdf/generate")
async def generate_pdf(
    image_path: str = Form(...),
    text: str = Form(...),
    searchable: bool = Form(True)
):
    """Generate PDF from image and text"""
    try:
        import re as _re
        safe_path = resolve_storage_path(image_path)
        pdf_filename = f"{Path(image_path).stem}_scribeai.pdf"
        pdf_path = PDF_DIR / pdf_filename

        if str(safe_path).lower().endswith('.pdf'):
            # Multi-page source PDF: render every page as an image
            page_images = pdf_processor.pdf_to_images(str(safe_path))
            if not page_images:
                raise HTTPException(status_code=422, detail="Could not render PDF pages")

            # Split the OCR text by page markers (--- Page N ---) to match each page
            _page_re = _re.compile(r'\s*---\s*Page\s+\d+\s*---\s*', _re.IGNORECASE)
            page_texts = [p.strip() for p in _page_re.split(text) if p.strip()]

            # Pair each image with its page text (empty string if no text for that page)
            pages = [(img, page_texts[i] if i < len(page_texts) else '') for i, img in enumerate(page_images)]
            success = pdf_generator.create_multipage_searchable_pdf(pages, str(pdf_path))
        else:
            # Single image source
            image = Image.open(safe_path)
            if searchable:
                success = pdf_generator.create_searchable_pdf(image, text, str(pdf_path))
            else:
                success = pdf_generator.create_simple_pdf(image, str(pdf_path))

        if not success:
            raise HTTPException(status_code=500, detail="PDF generation failed")

        return {
            "success": True,
            "pdf_path": str(pdf_path),
            "filename": pdf_filename
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/pdf/download/{filename}")
async def download_pdf(filename: str):
    """Download a generated PDF"""
    try:
        pdf_path = PDF_DIR / filename

        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF not found")

        return FileResponse(
            path=pdf_path,
            media_type="application/pdf",
            filename=filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF download failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Health Check ============

@api_router.get("/health")
async def health_check():
    """Server and dependency status"""
    mongo_ok = False
    try:
        await db.command("ping")
        mongo_ok = True
    except Exception:
        pass

    return {
        "status": "ok" if mongo_ok else "degraded",
        "mongodb": "connected" if mongo_ok else "unreachable",
        "ocr_engines": {
            "tesseract": ocr_engine.tesseract_available,
            "trocr": ocr_engine.trocr_model is not None,
            "gemini": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
        },
        "voice_engine": {
            "available": bool(os.environ.get("GROQ_API_KEY")),
            "whisper_model": "whisper-large-v3-turbo",
            "max_audio_size_mb": MAX_AUDIO_SIZE // (1024 * 1024),
            "ffmpeg_available": voice_engine.ffmpeg_available,
        },
        "rag": {
            "faiss_vectors": rag_engine.store.count,
            "embedding_model": EMBED_MODEL_NAME,
            "llm": "llama-3.1-8b-instant",
        },
    }

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)