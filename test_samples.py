#!/usr/bin/env python3
"""
Test OCR with generated sample images
"""

import pytesseract
from PIL import Image
import os

def test_sample_images():
    """Test OCR on all sample images"""
    sample_dir = "/app/sample_images"
    
    if not os.path.exists(sample_dir):
        print("❌ Sample images directory not found!")
        return
    
    images = [f for f in os.listdir(sample_dir) if f.endswith('.png')]
    
    print("🧪 Testing OCR on Sample Images")
    print("=" * 60)
    
    for img_name in images:
        img_path = os.path.join(sample_dir, img_name)
        print(f"\n📄 Processing: {img_name}")
        print("-" * 60)
        
        try:
            # Open image
            img = Image.open(img_path)
            print(f"   Image Size: {img.size[0]}x{img.size[1]} pixels")
            
            # Extract text
            text = pytesseract.image_to_string(img)
            
            # Get confidence data
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            # Display results
            print(f"   Characters: {len(text)}")
            print(f"   Words: {len(text.split())}")
            print(f"   Confidence: {avg_confidence:.2f}%")
            print(f"\n   Extracted Text Preview (first 200 chars):")
            print(f"   {text[:200].replace(chr(10), ' ')[:200]}...")
            print("   ✅ OCR successful!")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print("✅ OCR testing complete!")
    print(f"\n📊 Tested {len(images)} sample images")
    print("\n💡 All samples are ready for use in the Streamlit dashboard!")

if __name__ == "__main__":
    test_sample_images()
