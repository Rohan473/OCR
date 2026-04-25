# ScribeAI - Smart Handwritten Notes Digitizer

AI-powered document digitization system with React + FastAPI architecture. Extract text from handwritten and printed documents with state-of-the-art accuracy.

## 🌟 Features

- **TrOCR Integration** - Microsoft's Transformer-based OCR for handwritten text
- **Tesseract Fallback** - Reliable OCR for printed documents
- **Advanced Preprocessing** - Auto-deskew, CLAHE, noise removal, adaptive thresholding
- **Modern React UI** - Professional interface with Shadcn/UI components
- **MongoDB Storage** - Persistent notes with folders and search
- **Searchable PDFs** - Generate PDFs with invisible OCR text layer
- **Multi-language Support** - English + Hindi (Devanagari) mixed scripts

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 16+ and Yarn
- MongoDB running locally
- Tesseract OCR installed at `C:\Program Files\Tesseract-OCR\`

### Backend Setup

```powershell
cd backend
pip install -r requirements.txt

# Create .env file with:
# MONGO_URL=mongodb://localhost:27017
# DB_NAME=scribeai
# CORS_ORIGINS=http://localhost:3000

uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend Setup

```powershell
cd frontend
yarn install
yarn start
```

Access the app at **http://localhost:3000**

## 📖 Documentation

- [ScribeAI Summary](SCRIBEAI_SUMMARY.md) - Complete feature overview
- [Deployment Summary](DEPLOYMENT_SUMMARY.md) - Deployment status and architecture

## 🏗️ Architecture

- **Backend**: FastAPI (Python) on port 8001
- **Frontend**: React 19 on port 3000
- **Database**: MongoDB
- **OCR Engines**: TrOCR (handwritten) + Tesseract (printed)

## 🔧 Tech Stack

**Backend**: FastAPI, PyTorch, Transformers, OpenCV, Tesseract, ReportLab, Motor  
**Frontend**: React, TanStack Query, Framer Motion, Shadcn/UI, Tailwind CSS  
**Database**: MongoDB
