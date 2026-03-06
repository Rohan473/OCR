from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException, Form
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
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
    confidence: float
    engine: str
    language: str = "eng+hin"
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
    language: str = "eng+hin"
    folder_id: Optional[str] = None
    tags: List[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    language: str = "eng+hin"
    preprocess: bool = True

class SearchRequest(BaseModel):
    query: str
    folder_id: Optional[str] = None

# ============ Helper Functions ============

def save_image_from_upload(upload_file: UploadFile, directory: Path) -> str:
    """Save uploaded image to disk"""
    file_id = str(uuid.uuid4())
    file_extension = Path(upload_file.filename).suffix
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
    preprocess: bool = Form(True)
):
    """Upload and optionally preprocess an image"""
    try:
        # Validate file type
        if not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Save original image
        original_path = save_image_from_upload(file, UPLOAD_DIR)
        logger.info(f"Image uploaded: {original_path}")
        
        # Preprocess if requested
        processed_path = None
        if preprocess:
            try:
                image = Image.open(original_path)
                processed_image = image_preprocessor.preprocess(image, full_pipeline=True)
                
                # Save processed image
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
            "preprocessed": preprocess and processed_path is not None
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ocr/process")
async def process_ocr(
    image_path: str = Form(...),
    engine: str = Form("trocr"),
    language: str = Form("eng+hin")
):
    """Process image with OCR"""
    try:
        # Load image
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail="Image not found")
        
        image = Image.open(image_path)
        
        # Perform OCR
        result = ocr_engine.extract_text(image, engine=engine, languages=language)
        
        if not result["success"]:
            raise HTTPException(
                status_code=500, 
                detail=result.get("error", "OCR processing failed")
            )
        
        return {
            "success": True,
            "text": result["text"],
            "engine": result["engine"],
            "confidence": result["confidence"],
            "processing_time": result["processing_time"],
            "language": language
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/ocr/batch")
async def batch_ocr(
    files: List[UploadFile] = File(...),
    engine: str = Form("trocr"),
    language: str = Form("eng+hin"),
    preprocess: bool = Form(True)
):
    """Process multiple images in batch"""
    results = []
    
    for file in files:
        try:
            # Save and preprocess
            original_path = save_image_from_upload(file, UPLOAD_DIR)
            
            image = Image.open(original_path)
            if preprocess:
                image = image_preprocessor.preprocess(image, full_pipeline=True)
            
            # Process OCR
            ocr_result = ocr_engine.extract_text(image, engine=engine, languages=language)
            
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
        note = Note(**note_data.model_dump())
        
        # Convert to dict and serialize datetime
        doc = note.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        doc['updated_at'] = doc['updated_at'].isoformat()
        
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
        
        # Prepare update
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        update_dict['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        # Update in database
        await db.notes.update_one(
            {"id": note_id},
            {"$set": update_dict}
        )
        
        # Get updated note
        updated = await db.notes.find_one({"id": note_id}, {"_id": 0})
        
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
        query = {
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
