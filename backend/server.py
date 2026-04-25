from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone
from PIL import Image
import io
import base64
import shutil

# Import OCR modules
from ocr_engine import ocr_engine
from image_preprocessing import image_preprocessor
from pdf_generator import pdf_generator
from rag_engine import rag_engine
from pdf_processor import pdf_processor

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="ScribeAI API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create upload directories
UPLOAD_DIR = ROOT_DIR / "uploads"
PROCESSED_DIR = ROOT_DIR / "processed"
PDF_DIR = ROOT_DIR / "pdfs"

for directory in [UPLOAD_DIR, PROCESSED_DIR, PDF_DIR]:
    directory.mkdir(exist_ok=True)

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
    embedding: Optional[List[float]] = Field(default=None, exclude=True)

class RAGQueryRequest(BaseModel):
    question: str
    folder_id: Optional[str] = None
    history: List[Dict[str, str]] = []

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

# ============ Helper Functions ============
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
            "search": "/api/search"
        }
    }

# ============ OCR Routes ============

@api_router.post("/ocr/upload")
async def upload_image(
    file: UploadFile = File(...),
    preprocess: bool = Form(True),
    engine: str = Form("tesseract"),
    language: str = Form("eng"),
):
    """Upload and optionally preprocess an image or PDF"""
    try:
        content_type = file.content_type or ""
        is_pdf = content_type == "application/pdf" or (file.filename or "").lower().endswith(".pdf")

        if not is_pdf and not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image or PDF")

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
                try:
                    preview_images = pdf_processor.pdf_to_images(original_path, max_pages=1)
                    preview_path = str(PROCESSED_DIR / f"{Path(original_path).stem}_page1.png")
                    preview_images[0].save(preview_path)
                except Exception:
                    preview_path = original_path

                logger.info(f"PDF text layer extracted: {len(layer_text.split())} words")
                return {
                    "success": True,
                    "image_id": Path(original_path).stem,
                    "original_path": original_path,
                    "processed_path": preview_path,
                    "preprocessed": False,
                    "is_pdf": True,
                    "page_count": total_pages,
                    "ocr_text": layer_text,
                    "confidence": 1.0,
                    "engine": "pdf_text_layer",
                    "language": normalized_language,
                }

            # No embedded text — fall back to OCR on rendered images
            try:
                page_images = pdf_processor.pdf_to_images(original_path, max_pages=MAX_PDF_PAGES)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Could not read PDF: {e}")

            if not page_images:
                raise HTTPException(status_code=422, detail="PDF has no renderable pages")

            preview_path = str(PROCESSED_DIR / f"{Path(original_path).stem}_page1.png")
            page_images[0].save(preview_path)

            # Use Gemini batch (one API call for all pages) when the key is available —
            # dramatically better than Tesseract/TrOCR for handwritten content.
            gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            effective_engine = engine
            if gemini_key and engine.lower() != "tesseract" and engine.lower() != "trocr":
                effective_engine = "gemini"

            if effective_engine.lower() == "gemini":
                batch_text, confidence = ocr_engine.extract_with_gemini_batch(page_images)
                if batch_text:
                    return {
                        "success": True,
                        "image_id": Path(original_path).stem,
                        "original_path": original_path,
                        "processed_path": preview_path,
                        "preprocessed": False,
                        "is_pdf": True,
                        "page_count": total_pages,
                        "ocr_text": batch_text,
                        "confidence": round(confidence, 3),
                        "engine": "gemini",
                        "language": normalized_language,
                    }
                logger.warning("Gemini batch OCR returned empty — falling back to Tesseract")
                effective_engine = "tesseract"

            ocr_text, confidence = pdf_processor.ocr_images(
                page_images,
                ocr_fn=ocr_engine.extract_text,
                engine=effective_engine,
                languages=normalized_language,
                preprocessor=image_preprocessor if preprocess else None,
            )

            return {
                "success": True,
                "image_id": Path(original_path).stem,
                "original_path": original_path,
                "processed_path": preview_path,
                "preprocessed": preprocess,
                "is_pdf": True,
                "page_count": total_pages,
                "ocr_text": ocr_text,
                "confidence": round(confidence, 3),
                "engine": effective_engine,
                "language": normalized_language,
            }

        # --- image path (unchanged) ---
        processed_path = None
        if preprocess:
            try:
                image = Image.open(original_path)
                processed_image = image_preprocessor.preprocess_for_engine(image, engine="trocr")
                processed_path = str(PROCESSED_DIR / f"{Path(original_path).stem}_processed.png")
                processed_image.save(processed_path)
                logger.info(f"Image preprocessed: {processed_path}")
            except Exception as e:
                logger.error(f"Preprocessing failed: {str(e)}")
                processed_path = original_path

        return {
            "success": True,
            "image_id": Path(original_path).stem,
            "original_path": original_path,
            "processed_path": processed_path or original_path,
            "preprocessed": preprocess and processed_path is not None,
            "is_pdf": False,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

@api_router.post("/ocr/process")
async def process_ocr(
    image_path: str = Form(...),
    engine: str = Form("trocr"),
    language: str = Form("eng"),
    preprocess: bool = Form(True)
):
    """Process image with OCR"""
    try:
        # Load image
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        image = Image.open(image_path)
        normalized_language = normalize_ocr_languages(language)

        if preprocess:
            image = image_preprocessor.preprocess_for_engine(image, engine=engine)
        
        # Perform OCR
        result = ocr_engine.extract_text(image, engine=engine, languages=normalized_language)
        
        if not result["success"]:
            error_message = result.get("error", "OCR processing failed")
            status_code = 503 if "not available" in error_message.lower() else 500
            raise HTTPException(
                status_code=status_code,
                detail=error_message
            )
        
        return {
            "success": True,
            "text": result["text"],
            "engine": result["engine"],
            "confidence": result["confidence"],
            "processing_time": result["processing_time"],
            "language": normalized_language
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/images")
async def get_image(image_path: str):
    """Serve uploaded or processed images to the frontend."""
    file_path = resolve_storage_path(image_path)
    return FileResponse(file_path)

@api_router.post("/ocr/batch")
async def batch_ocr(
    files: List[UploadFile] = File(...),
    engine: str = Form("trocr"),
    language: str = Form("eng"),
    preprocess: bool = Form(True)
):
    """Process multiple images in batch"""
    results = []
    normalized_language = normalize_ocr_languages(language)
    
    for file in files:
        try:
            # Save and preprocess
            original_path = save_image_from_upload(file, UPLOAD_DIR)
            
            image = Image.open(original_path)
            if preprocess:
                image = image_preprocessor.preprocess(image, full_pipeline=True)
            
            # Process OCR
            ocr_result = ocr_engine.extract_text(image, engine=engine, languages=normalized_language)
            
            results.append({
                "filename": file.filename,
                "success": ocr_result["success"],
                "text": ocr_result["text"],
                "confidence": ocr_result["confidence"],
                "image_path": original_path
            })
            
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    return {"results": results, "total": len(files), "processed": len(results)}

# ============ Notes Routes ============

@api_router.post("/notes", response_model=Note)
async def create_note(note_data: NoteCreate):
    """Create a new note"""
    try:
        note_payload = note_data.model_dump()
        note_payload["language"] = normalize_ocr_languages(note_payload.get("language"))
        note = Note(**note_payload)

        doc = note.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()

        try:
            doc['embedding'] = await rag_engine.embed_text(note.transcribed_text)
        except Exception as e:
            logger.warning(f"Embedding generation skipped: {e}")
            doc['embedding'] = None

        await db.notes.insert_one(doc)

        return note

    except Exception as e:
        logger.error(f"Failed to create note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/notes", response_model=List[Note])
async def get_notes(folder_id: Optional[str] = None, limit: int = 100):
    """Get all notes, optionally filtered by folder"""
    try:
        query = {"folder_id": folder_id} if folder_id else {}
        
        notes = await db.notes.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
        
        # Convert ISO strings back to datetime
        for note in notes:
            if isinstance(note['created_at'], str):
                note['created_at'] = datetime.fromisoformat(note['created_at'])
            if isinstance(note['updated_at'], str):
                note['updated_at'] = datetime.fromisoformat(note['updated_at'])
        
        return notes
        
    except Exception as e:
        logger.error(f"Failed to get notes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/notes/{note_id}", response_model=Note)
async def get_note(note_id: str):
    """Get a specific note"""
    try:
        note = await db.notes.find_one({"id": note_id}, {"_id": 0})
        
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        # Convert ISO strings back to datetime
        if isinstance(note['created_at'], str):
            note['created_at'] = datetime.fromisoformat(note['created_at'])
        if isinstance(note['updated_at'], str):
            note['updated_at'] = datetime.fromisoformat(note['updated_at'])
        
        return note
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.patch("/notes/{note_id}", response_model=Note)
async def update_note(note_id: str, update_data: NoteUpdate):
    """Update a note"""
    try:
        # Get existing note
        existing = await db.notes.find_one({"id": note_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Note not found")
        
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        update_dict['updated_at'] = datetime.now(timezone.utc).isoformat()

        if 'transcribed_text' in update_dict:
            try:
                update_dict['embedding'] = await rag_engine.embed_text(update_dict['transcribed_text'])
            except Exception as e:
                logger.warning(f"Embedding regeneration skipped: {e}")
        
        # Update in database
        await db.notes.update_one(
            {"id": note_id},
            {"$set": update_dict}
        )
        
        # Get updated note
        updated = await db.notes.find_one({"id": note_id}, {"_id": 0})
        if not updated:
            raise HTTPException(status_code=404, detail="Note not found after update")
        
        # Convert ISO strings back to datetime
        if isinstance(updated['created_at'], str):
            updated['created_at'] = datetime.fromisoformat(updated['created_at'])
        if isinstance(updated['updated_at'], str):
            updated['updated_at'] = datetime.fromisoformat(updated['updated_at'])
        
        return updated
        
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
        
        return {"success": True, "message": "Note deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete note: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ============ Folder Routes ============

@api_router.post("/folders", response_model=Folder)
async def create_folder(folder_data: FolderCreate):
    """Create a new folder"""
    try:
        folder = Folder(**folder_data.model_dump())
        
        doc = folder.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        
        await db.folders.insert_one(doc)
        
        return folder
        
    except Exception as e:
        logger.error(f"Failed to create folder: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/folders", response_model=List[Folder])
async def get_folders():
    """Get all folders"""
    try:
        folders = await db.folders.find({}, {"_id": 0}).sort("name", 1).to_list(100)
        
        for folder in folders:
            if isinstance(folder['created_at'], str):
                folder['created_at'] = datetime.fromisoformat(folder['created_at'])
        
        return folders
        
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
        
        # Convert ISO strings back to datetime
        for note in notes:
            if isinstance(note['created_at'], str):
                note['created_at'] = datetime.fromisoformat(note['created_at'])
            if isinstance(note['updated_at'], str):
                note['updated_at'] = datetime.fromisoformat(note['updated_at'])
        
        return {"results": notes, "count": len(notes)}
        
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
    """Generate embeddings for all notes that are missing them"""
    try:
        notes = await db.notes.find(
            {"$or": [{"embedding": {"$exists": False}}, {"embedding": None}]},
            {"_id": 0, "id": 1, "transcribed_text": 1}
        ).to_list(10000)

        embedded = 0
        for note in notes:
            try:
                emb = await rag_engine.embed_text(note.get("transcribed_text", ""))
                if emb:
                    await db.notes.update_one({"id": note["id"]}, {"$set": {"embedding": emb}})
                    embedded += 1
            except Exception as e:
                logger.warning(f"Failed to embed note {note['id']}: {e}")

        return {"embedded": embedded, "skipped": len(notes) - embedded}
    except Exception as e:
        logger.error(f"Reindex failed: {str(e)}")
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
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Load image
        image = Image.open(image_path)
        
        # Generate PDF filename
        pdf_filename = f"{Path(image_path).stem}.pdf"
        pdf_path = PDF_DIR / pdf_filename
        
        # Generate PDF
        if searchable:
            success = pdf_generator.create_searchable_pdf(
                image, text, str(pdf_path)
            )
        else:
            success = pdf_generator.create_simple_pdf(
                image, str(pdf_path)
            )
        
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

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
