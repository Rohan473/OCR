import streamlit as st
import pytesseract
from PIL import Image
import pdf2image
import pdfplumber
import io
import tempfile
import os
from pathlib import Path
import plotly.graph_objects as go
import plotly.express as px
from langdetect import detect, LangDetectException
from datetime import datetime
import base64

# Page configuration
st.set_page_config(
    page_title="Professional OCR Dashboard",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');
    
    * {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    .upload-section {
        background: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        transition: transform 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
    }
    
    .text-output {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        font-family: 'IBM Plex Mono', monospace;
        font-size: 14px;
        line-height: 1.6;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        max-height: 500px;
        overflow-y: auto;
    }
    
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    h1, h2, h3 {
        font-weight: 700;
        color: #1a202c;
    }
    
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.3s;
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(102, 126, 234, 0.6);
    }
    
    .success-message {
        background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        color: white;
        padding: 1rem;
        border-radius: 8px;
        margin: 1rem 0;
    }
    
    .info-box {
        background: #f7fafc;
        border-left: 4px solid #667eea;
        padding: 1rem;
        border-radius: 4px;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'extracted_text' not in st.session_state:
    st.session_state.extracted_text = ""
if 'ocr_history' not in st.session_state:
    st.session_state.ocr_history = []
if 'processing_time' not in st.session_state:
    st.session_state.processing_time = 0

def extract_text_from_image(image):
    """Extract text from PIL Image using Tesseract OCR"""
    try:
        # Perform OCR with detailed data
        text = pytesseract.image_to_string(image)
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        # Calculate confidence scores
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        return text, avg_confidence, data
    except Exception as e:
        st.error(f"Error during OCR: {str(e)}")
        return "", 0, None

def extract_text_from_pdf(pdf_file):
    """Extract text from PDF using both pdfplumber and OCR"""
    text = ""
    confidence_scores = []
    
    try:
        # First try text extraction with pdfplumber
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"
        
        # If no text found, use OCR on PDF images
        if not text.strip():
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_file.write(pdf_file.read())
                tmp_path = tmp_file.name
            
            images = pdf2image.convert_from_path(tmp_path)
            
            for i, image in enumerate(images):
                page_text, confidence, _ = extract_text_from_image(image)
                text += f"--- Page {i+1} ---\n{page_text}\n\n"
                confidence_scores.append(confidence)
            
            os.unlink(tmp_path)
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        else:
            avg_confidence = 95  # High confidence for native PDF text
        
        return text, avg_confidence
    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        return "", 0

def detect_language(text):
    """Detect the language of extracted text"""
    try:
        if text.strip():
            lang = detect(text)
            lang_names = {
                'en': 'English', 'es': 'Spanish', 'fr': 'French', 
                'de': 'German', 'it': 'Italian', 'pt': 'Portuguese',
                'ar': 'Arabic', 'hi': 'Hindi', 'zh-cn': 'Chinese',
                'ja': 'Japanese', 'ko': 'Korean', 'ru': 'Russian'
            }
            return lang_names.get(lang, lang.upper())
        return "Unknown"
    except LangDetectException:
        return "Unknown"

def create_word_frequency_chart(text):
    """Create word frequency visualization"""
    words = text.lower().split()
    word_freq = {}
    
    # Filter out common words and short words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'was', 'are', 'be'}
    
    for word in words:
        word = ''.join(char for char in word if char.isalnum())
        if len(word) > 3 and word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top 10 words
    top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if top_words:
        words, counts = zip(*top_words)
        fig = px.bar(x=list(counts), y=list(words), orientation='h',
                     title="Top 10 Most Frequent Words",
                     labels={'x': 'Frequency', 'y': 'Word'},
                     color=list(counts),
                     color_continuous_scale='Viridis')
        fig.update_layout(
            height=400,
            showlegend=False,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        return fig
    return None

def create_text_stats_gauge(value, max_value, title):
    """Create a gauge chart for text statistics"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title},
        gauge={
            'axis': {'range': [None, max_value]},
            'bar': {'color': "#667eea"},
            'steps': [
                {'range': [0, max_value/3], 'color': "#e0e7ff"},
                {'range': [max_value/3, 2*max_value/3], 'color': "#c7d2fe"},
                {'range': [2*max_value/3, max_value], 'color': "#a5b4fc"}
            ],
            'threshold': {
                'line': {'color': "#764ba2", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
    return fig

# Header
st.markdown("""
    <div style='text-align: center; padding: 2rem 0;'>
        <h1 style='font-size: 3rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                   background-clip: text; margin-bottom: 0.5rem;'>
            📄 Professional OCR Dashboard
        </h1>
        <p style='font-size: 1.2rem; color: #4a5568;'>
            Extract text from images and PDFs with AI-powered analysis
        </p>
    </div>
    """, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### ⚙️ Configuration")
    
    tesseract_config = st.text_input(
        "Tesseract Config",
        value="--psm 3",
        help="Page Segmentation Mode: 3=Automatic, 6=Single block, 11=Sparse text"
    )
    
    st.markdown("---")
    st.markdown("### 📊 OCR Statistics")
    if st.session_state.ocr_history:
        st.metric("Total Extractions", len(st.session_state.ocr_history))
        total_chars = sum([h['char_count'] for h in st.session_state.ocr_history])
        st.metric("Total Characters", f"{total_chars:,}")
        avg_conf = sum([h['confidence'] for h in st.session_state.ocr_history]) / len(st.session_state.ocr_history)
        st.metric("Avg Confidence", f"{avg_conf:.1f}%")
    
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown("""
        **OCR Engine:** Tesseract 5.x  
        **Supported Formats:**  
        - Images: PNG, JPG, JPEG, BMP, TIFF  
        - Documents: PDF  
        
        **Features:**  
        ✓ Text extraction  
        ✓ Language detection  
        ✓ Confidence scoring  
        ✓ Data visualization  
        ✓ Export options
    """)
    
    if st.button("🗑️ Clear History"):
        st.session_state.ocr_history = []
        st.session_state.extracted_text = ""
        st.success("History cleared!")

# Main content
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### 📤 Upload Document")
    uploaded_file = st.file_uploader(
        "Choose an image or PDF file",
        type=['png', 'jpg', 'jpeg', 'pdf', 'bmp', 'tiff'],
        help="Upload an image or PDF document to extract text"
    )
    
    if uploaded_file:
        file_details = {
            "Filename": uploaded_file.name,
            "FileType": uploaded_file.type,
            "FileSize": f"{uploaded_file.size / 1024:.2f} KB"
        }
        
        with st.expander("📋 File Details", expanded=True):
            for key, value in file_details.items():
                st.text(f"{key}: {value}")

with col2:
    st.markdown("### 🎯 Quick Actions")
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        process_btn = st.button("🚀 Extract Text", use_container_width=True, disabled=uploaded_file is None)
    
    with col_btn2:
        download_btn = st.button("💾 Download", use_container_width=True, disabled=not st.session_state.extracted_text)
    
    with col_btn3:
        clear_btn = st.button("🔄 Clear", use_container_width=True)
    
    if clear_btn:
        st.session_state.extracted_text = ""
        st.rerun()

# Processing
if process_btn and uploaded_file:
    with st.spinner("🔍 Processing document..."):
        start_time = datetime.now()
        
        file_type = uploaded_file.type
        
        if 'pdf' in file_type:
            text, confidence = extract_text_from_pdf(uploaded_file)
        else:
            image = Image.open(uploaded_file)
            text, confidence, _ = extract_text_from_image(image)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        st.session_state.extracted_text = text
        st.session_state.processing_time = processing_time
        
        # Add to history
        st.session_state.ocr_history.append({
            'filename': uploaded_file.name,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'char_count': len(text),
            'word_count': len(text.split()),
            'confidence': confidence,
            'language': detect_language(text),
            'processing_time': processing_time
        })
        
        st.success(f"✅ Text extracted successfully in {processing_time:.2f} seconds!")

# Display results
if st.session_state.extracted_text:
    st.markdown("---")
    st.markdown("## 📊 Analysis Results")
    
    # Metrics
    text = st.session_state.extracted_text
    char_count = len(text)
    word_count = len(text.split())
    line_count = len(text.split('\n'))
    language = detect_language(text)
    
    latest_history = st.session_state.ocr_history[-1] if st.session_state.ocr_history else None
    confidence = latest_history['confidence'] if latest_history else 0
    
    # Display metrics in cards
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    
    with metric_col1:
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin: 0; font-size: 2rem; color: white;">{char_count:,}</h3>
                <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Characters</p>
            </div>
        """, unsafe_allow_html=True)
    
    with metric_col2:
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin: 0; font-size: 2rem; color: white;">{word_count:,}</h3>
                <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Words</p>
            </div>
        """, unsafe_allow_html=True)
    
    with metric_col3:
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin: 0; font-size: 2rem; color: white;">{confidence:.1f}%</h3>
                <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Confidence</p>
            </div>
        """, unsafe_allow_html=True)
    
    with metric_col4:
        st.markdown(f"""
            <div class="metric-card">
                <h3 style="margin: 0; font-size: 2rem; color: white;">{language}</h3>
                <p style="margin: 0.5rem 0 0 0; opacity: 0.9;">Language</p>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Visualizations
    viz_col1, viz_col2 = st.columns(2)
    
    with viz_col1:
        st.plotly_chart(
            create_text_stats_gauge(word_count, max(word_count * 1.5, 100), "Word Count"),
            use_container_width=True
        )
    
    with viz_col2:
        st.plotly_chart(
            create_text_stats_gauge(confidence, 100, "OCR Confidence (%)"),
            use_container_width=True
        )
    
    # Word frequency chart
    if len(text.split()) > 10:
        st.markdown("### 📈 Word Frequency Analysis")
        freq_chart = create_word_frequency_chart(text)
        if freq_chart:
            st.plotly_chart(freq_chart, use_container_width=True)
    
    # Extracted text
    st.markdown("### 📝 Extracted Text")
    
    # Text editing
    edited_text = st.text_area(
        "Edit the extracted text if needed:",
        value=text,
        height=300,
        key="text_editor"
    )
    
    st.session_state.extracted_text = edited_text
    
    # Download options
    st.markdown("### 💾 Export Options")
    
    export_col1, export_col2, export_col3 = st.columns(3)
    
    with export_col1:
        st.download_button(
            label="📄 Download as TXT",
            data=edited_text,
            file_name=f"extracted_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with export_col2:
        # Create CSV format
        csv_data = f"Characters,Words,Lines,Confidence,Language,Processing Time\n"
        csv_data += f"{char_count},{word_count},{line_count},{confidence:.2f},{language},{st.session_state.processing_time:.2f}\n\n"
        csv_data += f"Extracted Text:\n{edited_text}"
        
        st.download_button(
            label="📊 Download as CSV",
            data=csv_data,
            file_name=f"ocr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with export_col3:
        # Create JSON format
        import json
        json_data = {
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "filename": latest_history['filename'] if latest_history else "unknown",
                "processing_time": st.session_state.processing_time
            },
            "statistics": {
                "characters": char_count,
                "words": word_count,
                "lines": line_count,
                "confidence": confidence,
                "language": language
            },
            "extracted_text": edited_text
        }
        
        st.download_button(
            label="🗂️ Download as JSON",
            data=json.dumps(json_data, indent=2),
            file_name=f"ocr_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )

# History section
if st.session_state.ocr_history:
    st.markdown("---")
    st.markdown("## 📜 Processing History")
    
    import pandas as pd
    history_df = pd.DataFrame(st.session_state.ocr_history)
    
    # Display as interactive table
    st.dataframe(
        history_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "timestamp": "Time",
            "filename": "File",
            "char_count": st.column_config.NumberColumn("Characters", format="%d"),
            "word_count": st.column_config.NumberColumn("Words", format="%d"),
            "confidence": st.column_config.ProgressColumn("Confidence", format="%.1f%%", min_value=0, max_value=100),
            "language": "Language",
            "processing_time": st.column_config.NumberColumn("Time (s)", format="%.2f")
        }
    )

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; padding: 2rem 0; color: #718096;'>
        <p>Built with Streamlit & Tesseract OCR | Professional Document Processing</p>
        <p style='font-size: 0.9rem;'>Supports multiple languages and document formats</p>
    </div>
    """, unsafe_allow_html=True)
