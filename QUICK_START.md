# 🚀 Quick Start Guide - OCR Dashboard

## Accessing Your Streamlit Dashboard

### Local Access
If you're running this locally:
```
http://localhost:8501
```

### Production/Cloud Access
The Streamlit dashboard runs on port 8501. You can access it through your deployment URL.

**Note**: If port 8501 is not accessible externally, you may need to:
1. Configure port forwarding in your deployment
2. Use SSH tunneling: `ssh -L 8501:localhost:8501 user@your-server`
3. Contact your infrastructure team to open port 8501

## 📋 Testing the OCR Functionality

### Quick Test
Run the test script to verify OCR is working:
```bash
cd /app
python test_ocr.py
```

### Manual Testing Steps

1. **Access the Dashboard**
   - Navigate to http://localhost:8501
   - You should see the "Professional OCR Dashboard" homepage

2. **Upload a Test Image**
   You can test with any image containing text, such as:
   - Screenshots of documents
   - Photos of books or papers
   - Scanned documents
   - Receipts or invoices
   - Any image with readable text

3. **Upload a PDF**
   - Test with any PDF document
   - Both native text PDFs and scanned PDFs are supported

4. **View Results**
   After uploading and clicking "Extract Text":
   - View extracted text in the editor
   - See analytics (word count, character count, confidence)
   - Check visualizations (word frequency, gauge charts)
   - Download results in TXT, CSV, or JSON format

## 🎯 What to Expect

### Image OCR
- Processing time: 1-3 seconds per image
- Confidence scores: 70-95% for good quality images
- Supports: PNG, JPG, JPEG, BMP, TIFF

### PDF Processing
- **Native text PDFs**: Near instant extraction
- **Scanned PDFs**: 2-5 seconds per page (OCR required)
- Multi-page support with page-by-page processing

### Analytics
- Real-time character and word counting
- Language detection (12+ languages)
- Confidence scoring
- Word frequency analysis
- Processing history tracking

## 📊 Dashboard Features Overview

### Main Interface
- **Upload Area**: Drag and drop files or click to browse
- **File Details**: Automatic display of file information
- **Quick Actions**: Extract, Download, Clear buttons

### Results Section
- **Metric Cards**: Character count, word count, confidence, language
- **Gauge Charts**: Visual representation of statistics
- **Word Frequency Chart**: Bar chart of most common words
- **Text Editor**: Edit extracted text before export

### Sidebar
- **Configuration**: Tesseract OCR settings
- **Statistics**: Running totals across all extractions
- **About**: Information about features and formats
- **Clear History**: Reset all session data

### Export Options
- **TXT**: Plain text file
- **CSV**: Spreadsheet with statistics and text
- **JSON**: Structured data with metadata

## 🔧 Troubleshooting

### Dashboard Won't Load
```bash
# Check if Streamlit is running
sudo supervisorctl status streamlit

# Restart if needed
sudo supervisorctl restart streamlit

# Check logs
tail -f /var/log/supervisor/streamlit.out.log
```

### Port 8501 Not Accessible
```bash
# Verify the service is listening
netstat -tuln | grep 8501

# Check firewall rules
sudo ufw status

# View Streamlit configuration
cat /etc/supervisor/conf.d/streamlit.conf
```

### OCR Not Working
```bash
# Test Tesseract directly
tesseract --version

# Test with sample image
python /app/test_ocr.py

# Check available languages
tesseract --list-langs
```

## 📱 Sample Test Cases

### Test Case 1: Simple Text Image
1. Create a screenshot of any text
2. Upload to the dashboard
3. Click "Extract Text"
4. Verify the text matches the original

### Test Case 2: Multi-Language Document
1. Upload a document in French, Spanish, or German
2. Extract text
3. Check if language is correctly detected

### Test Case 3: PDF Document
1. Upload any PDF file
2. Observe if it uses native extraction or OCR
3. Check processing time and confidence

### Test Case 4: Low Quality Image
1. Upload a blurry or low-resolution image
2. Note the confidence score
3. Compare with high-quality image results

### Test Case 5: Batch Processing
1. Upload and process multiple documents
2. View processing history
3. Compare statistics across documents

## 📈 Performance Tips

### For Best Results
- Use high-resolution images (300+ DPI)
- Ensure good contrast between text and background
- Rotate images to correct orientation
- Crop out unnecessary areas
- Use well-lit, clear photos

### For Faster Processing
- Use native PDF text when available
- Compress large images before upload
- Process one document at a time
- Clear history periodically

## 🎨 UI Features

### Professional Design
- Modern gradient backgrounds
- Smooth animations and transitions
- Responsive layout
- IBM Plex Sans font family
- Interactive hover effects

### Data Visualizations
- Plotly-powered interactive charts
- Real-time gauge displays
- Color-coded confidence scores
- Dynamic word frequency analysis

## 📞 Support Resources

### Documentation
- Full README: `/app/README_OCR.md`
- Test Script: `/app/test_ocr.py`
- Application Code: `/app/streamlit_app.py`

### Logs
```bash
# Streamlit logs
tail -f /var/log/supervisor/streamlit.out.log
tail -f /var/log/supervisor/streamlit.err.log
```

### Configuration
- Supervisor config: `/etc/supervisor/conf.d/streamlit.conf`
- Application: `/app/streamlit_app.py`

## 🏁 Getting Started Checklist

- [ ] Access dashboard at http://localhost:8501
- [ ] Run test script: `python /app/test_ocr.py`
- [ ] Upload a test image or PDF
- [ ] Extract text and view results
- [ ] Check analytics and visualizations
- [ ] Download results in preferred format
- [ ] Test with different document types
- [ ] Explore processing history

## 🚀 Next Steps

1. **Test the application**: Upload various documents to see OCR in action
2. **Customize settings**: Adjust Tesseract parameters for your use case
3. **Integrate**: Use the extracted data in your workflows
4. **Scale**: Process multiple documents and track history
5. **Optimize**: Fine-tune for your specific document types

---

**Need Help?**
- Check logs: `/var/log/supervisor/streamlit.*.log`
- Run test: `python /app/test_ocr.py`
- Verify service: `sudo supervisorctl status streamlit`

**Ready to Use!** 🎉
The OCR Dashboard is fully configured and ready for document processing!
