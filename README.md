# ScribeAI — Handwritten Notes Digitizer

AI-powered document digitization with React + FastAPI. Upload handwritten notes or PDFs and get accurate, editable transcriptions.

## Features

- **Gemini Vision OCR** — Google's multimodal model; best accuracy for handwriting, diagrams, and mixed scripts. Batch-processes entire PDFs in a single API call.
- **TrOCR** — Microsoft's transformer OCR for handwritten text, with automatic line segmentation (OpenCV) before inference.
- **Tesseract** — Fast OCR for printed documents with adaptive PSM selection.
- **PDF text layer extraction** — If a PDF already has selectable text, it's extracted directly (instant, lossless — no OCR needed).
- **RAG Q&A** — Ask natural-language questions across all saved notes using semantic search (Groq embeddings).
- **Image preprocessing** — Auto-deskew, CLAHE contrast enhancement, noise removal, adaptive thresholding.
- **Searchable PDFs** — Export notes as PDFs with an invisible OCR text layer.
- **MongoDB storage** — Notes, folders, tags, and full-text search.
- **Multi-language** — English, Hindi (Devanagari), and mixed scripts.

## Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Shadcn/UI, Tailwind CSS, Framer Motion |
| Backend | FastAPI, Python 3.11 |
| OCR | Gemini 2.0 Flash, TrOCR (Microsoft), Tesseract |
| Database | MongoDB |
| Embeddings | Groq (for RAG) |
| PDF | pypdfium2, ReportLab |

## Prerequisites

- Python 3.11+
- Node.js 18+ and Yarn
- MongoDB running locally (`mongod`)
- Tesseract OCR — [download](https://github.com/UB-Mannheim/tesseract/wiki) and install to `C:\Program Files\Tesseract-OCR\`
- A free [Gemini API key](https://aistudio.google.com/apikey) (for best OCR quality)
- A free [Groq API key](https://console.groq.com) (for RAG Q&A)

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
```

Create `backend/.env`:

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=scribeai
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Required for Gemini OCR (best quality)
GEMINI_API_KEY=your_gemini_key_here

# Required for RAG Q&A
GROQ_API_KEY=your_groq_key_here
```

```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd frontend
yarn install
yarn start
```

Open **http://localhost:3000**

## How It Works

1. **Upload** an image or PDF (up to 15 pages for PDFs).
2. The backend checks for an embedded text layer first — if found, it's returned instantly.
3. Otherwise, if a `GEMINI_API_KEY` is set, all pages are sent to Gemini Vision in one batch call.
4. The result lands in the **Editor** where you can correct, retitle, and save the note.
5. Re-process any note with a different engine (Gemini / TrOCR / Tesseract) or language directly from the Editor.
6. Use the **RAG sidebar** to ask questions across all saved notes.

## OCR Engine Comparison

| Engine | Best For | Notes |
|--------|----------|-------|
| Gemini (Best) | Handwriting, diagrams, mixed content | Requires API key; free tier: 1500 req/day |
| TrOCR | Handwritten English | Runs locally; slower on CPU |
| Tesseract | Printed / typed text | Fastest; good for clean scans |

## Architecture

```
frontend (React :3000)
    └── backend (FastAPI :8001)
            ├── ocr_engine.py       — Gemini / TrOCR / Tesseract
            ├── pdf_processor.py    — PDF rendering & text layer extraction
            ├── image_preprocessing.py — OpenCV pipeline
            ├── rag_engine.py       — Groq embeddings + semantic search
            └── pdf_generator.py    — Searchable PDF export
```
