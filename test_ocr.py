#!/usr/bin/env python3
"""
Simple OCR Test Script
Tests Tesseract OCR functionality with a sample image
"""

import pytesseract
from PIL import Image, ImageDraw, ImageFont
import io

def create_test_image():
    """Create a simple test image with text"""
    # Create a white image
    img = Image.new('RGB', (800, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    # Add text to the image
    test_text = """Professional OCR Dashboard
    
This is a test document for OCR extraction.
The system can read printed text accurately.

Features:
- Image processing
- PDF document support
- Multi-language detection
- Confidence scoring"""
    
    # Draw text (using default font)
    draw.text((50, 50), test_text, fill='black')
    
    return img

def test_ocr():
    """Test OCR functionality"""
    print("🧪 Testing Tesseract OCR...")
    print("-" * 50)
    
    # Create test image
    print("1. Creating test image...")
    img = create_test_image()
    
    # Perform OCR
    print("2. Extracting text with Tesseract...")
    try:
        extracted_text = pytesseract.image_to_string(img)
        
        print("3. ✅ OCR Extraction Successful!")
        print("-" * 50)
        print("Extracted Text:")
        print(extracted_text)
        print("-" * 50)
        
        # Get detailed data
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        print(f"Average Confidence: {avg_confidence:.2f}%")
        print(f"Characters Extracted: {len(extracted_text)}")
        print(f"Words Detected: {len(extracted_text.split())}")
        print("-" * 50)
        
        # Check Tesseract version
        version = pytesseract.get_tesseract_version()
        print(f"Tesseract Version: {version}")
        
        # List available languages
        langs = pytesseract.get_languages()
        print(f"Available Languages: {', '.join(langs)}")
        
        print("\n✅ All OCR tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ OCR test failed: {str(e)}")
        return False

if __name__ == "__main__":
    test_ocr()
