# Professional OCR Dashboard

A powerful Optical Character Recognition (OCR) application built with Streamlit and Tesseract OCR. Extract text from images and PDF documents with professional data visualization and analytics.

## 🌟 Features

### Core Capabilities
- **Multi-Format Support**: Process images (PNG, JPG, JPEG, BMP, TIFF) and PDF documents
- **Tesseract OCR Engine**: Industry-standard text extraction with high accuracy
- **Dual PDF Processing**: Combines native PDF text extraction with OCR fallback
- **Language Detection**: Automatically identifies the language of extracted text
- **Confidence Scoring**: Real-time OCR confidence metrics

### Professional Dashboard
- **Real-time Analytics**: Character count, word count, confidence scores
- **Data Visualizations**: 
  - Interactive gauge charts for statistics
  - Word frequency analysis with bar charts
  - Processing history tracking
- **Text Editing**: Edit extracted text before export
- **Multiple Export Formats**: TXT, CSV, JSON

### Advanced Features
- **Processing History**: Track all OCR operations with detailed metrics
- **Configurable OCR**: Adjust Tesseract parameters for optimal results
- **Session Management**: Persistent data during your session
- **Professional UI**: Modern gradient design with smooth animations

## 🚀 Getting Started

### Prerequisites
The application requires:
- Python 3.11+
- Tesseract OCR (pre-installed in the environment)
- Poppler utilities (pre-installed for PDF processing)

### Installation

All dependencies are already installed:
```bash
streamlit
pytesseract
pillow
pdf2image
pdfplumber
langdetect
plotly
```

### Running the Application

The Streamlit app is managed by supervisord and runs automatically on port 8501:

```bash
# Check status
sudo supervisorctl status streamlit

# Restart if needed
sudo supervisorctl restart streamlit

# View logs
tail -f /var/log/supervisor/streamlit.out.log
```

### Accessing the Dashboard

**Local Access**: http://localhost:8501

**External Access**: The application is accessible through your deployment URL on port 8501

## 📖 How to Use

### 1. Upload Document
- Click on the file uploader in the main interface
- Select an image (PNG, JPG, etc.) or PDF document
- File details will be displayed automatically

### 2. Configure Settings (Optional)
- Use the sidebar to adjust Tesseract configuration
- Default settings work well for most documents
- PSM modes: 3=Automatic, 6=Single block, 11=Sparse text

### 3. Extract Text
- Click the "🚀 Extract Text" button
- Processing time and confidence scores are displayed
- View real-time analytics and visualizations

### 4. Review Results
- **Metrics Dashboard**: View character count, word count, confidence, and detected language
- **Gauge Charts**: Visual representation of key statistics
- **Word Frequency**: See the most common words in your document
- **Text Editor**: Edit the extracted text if needed

### 5. Export Data
Choose from multiple export formats:
- **TXT**: Plain text file
- **CSV**: Includes statistics and extracted text
- **JSON**: Complete data structure with metadata

### 6. Track History
- View all processed documents in the history table
- See processing times, confidence scores, and languages
- Clear history using the sidebar button

## 🎨 Dashboard Features

### Main Interface
- **Upload Section**: Drag-and-drop or click to upload
- **File Details**: View filename, type, and size
- **Quick Actions**: Extract, Download, Clear buttons

### Analytics Display
- **Metric Cards**: Beautiful gradient cards showing key statistics
- **Gauge Charts**: Interactive visualizations for word count and confidence
- **Word Frequency Chart**: Horizontal bar chart of top 10 words
- **Processing History Table**: Sortable, filterable data grid

### Sidebar
- **Configuration**: Tesseract OCR settings
- **Statistics**: Running totals across all extractions
- **About**: Information about the OCR engine and features
- **Clear History**: Reset all session data

## 🔧 Technical Details

### OCR Processing

**Image Processing**:
```python
- Pillow for image loading
- Tesseract OCR for text extraction
- Confidence scoring with detailed data analysis
```

**PDF Processing**:
```python
- pdfplumber for native text extraction (preferred)
- pdf2image + Tesseract for scanned PDFs (fallback)
- Page-by-page processing with progress tracking
```

### Language Support
Detects multiple languages including:
- English, Spanish, French, German, Italian, Portuguese
- Arabic, Hindi, Chinese, Japanese, Korean, Russian
- And more through Tesseract language packs

### Data Analysis
- Character and word counting
- Line counting
- Confidence score averaging
- Language detection using langdetect
- Word frequency analysis with stop-word filtering

## 📊 Supported Document Types

### Images
- Standard documents (letters, forms, invoices)
- Receipts and bills
- IDs and passports
- Handwritten text (with varying accuracy)
- Screenshots and digital images

### PDFs
- Native text PDFs (direct extraction)
- Scanned PDFs (OCR processing)
- Mixed content PDFs (hybrid approach)
- Multi-page documents

## 🎯 Use Cases

1. **Document Digitization**: Convert paper documents to digital text
2. **Receipt Processing**: Extract data from receipts for expense tracking
3. **Form Processing**: Digitize filled forms and applications
4. **Book Scanning**: Convert printed books to digital text
5. **Invoice Management**: Extract text from invoices for accounting
6. **ID Verification**: Read text from identification documents
7. **Archive Conversion**: Digitize old documents and archives

## 🔒 Privacy & Security

- All processing is done locally on the server
- No data is sent to external services
- Session data is temporary and cleared on browser close
- History is stored in session state only

## 🛠️ Troubleshooting

### OCR Not Working
```bash
# Verify Tesseract installation
tesseract --version

# Check language packs
tesseract --list-langs
```

### Low Confidence Scores
- Ensure good image quality (high resolution)
- Check for proper contrast and lighting
- Try different PSM modes in configuration
- Pre-process images (rotate, crop, enhance)

### PDF Processing Issues
```bash
# Verify poppler installation
pdftoppm -v

# Check PDF file integrity
pdfinfo your_file.pdf
```

### Performance Optimization
- Use native PDF text extraction when possible (faster)
- Compress large images before upload
- Process multi-page PDFs in smaller batches

## 📦 Architecture

```
streamlit_app.py          # Main application
├── UI Components         # Streamlit interface
├── OCR Functions         # Text extraction logic
├── Data Processing       # Analytics and statistics
├── Visualizations        # Plotly charts
└── Export Functions      # File download options
```

## 🔄 Updates & Maintenance

### Updating Dependencies
```bash
cd /app/backend
pip install --upgrade streamlit pytesseract
pip freeze > requirements.txt
sudo supervisorctl restart streamlit
```

### Adding Language Packs
```bash
# Install additional Tesseract languages
sudo apt-get install tesseract-ocr-fra  # French
sudo apt-get install tesseract-ocr-spa  # Spanish
sudo apt-get install tesseract-ocr-deu  # German
```

## 📈 Performance Metrics

- **Image Processing**: ~1-3 seconds per image
- **PDF Native Text**: <1 second per page
- **PDF OCR**: ~2-5 seconds per page
- **Confidence Scores**: 85-95% for good quality documents

## 🤝 Best Practices

1. **Image Quality**: Use high-resolution scans (300+ DPI)
2. **File Format**: PDF with native text is fastest
3. **Preprocessing**: Crop and rotate images before upload
4. **Language**: Ensure correct language pack is installed
5. **Batch Processing**: Process similar documents together

## 📝 Notes

- The application uses session state for data persistence
- History is cleared when the browser session ends
- Large PDFs may take longer to process
- Confidence scores indicate OCR accuracy
- Some handwritten text may have lower accuracy

## 🎨 Customization

The dashboard uses custom CSS for styling:
- Gradient backgrounds (purple/blue theme)
- Professional metric cards
- Smooth transitions and hover effects
- IBM Plex Sans font family
- Responsive layout for all screen sizes

## 📞 Support

For issues with:
- **Tesseract OCR**: Check official Tesseract documentation
- **Streamlit**: Visit Streamlit documentation
- **PDF Processing**: Verify poppler-utils installation

## 🏆 Credits

Built with:
- **Streamlit**: Web framework
- **Tesseract OCR**: Text extraction engine
- **Plotly**: Interactive visualizations
- **Pillow**: Image processing
- **pdfplumber**: PDF text extraction
- **pdf2image**: PDF to image conversion
- **langdetect**: Language detection

---

**Version**: 1.0.0  
**Last Updated**: January 2026  
**License**: MIT  
**Platform**: Streamlit Dashboard
