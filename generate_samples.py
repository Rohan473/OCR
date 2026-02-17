#!/usr/bin/env python3
"""
Generate Sample Test Images for OCR Testing
Creates various types of test images with different text layouts
"""

from PIL import Image, ImageDraw, ImageFont
import os

def create_sample_invoice():
    """Create a sample invoice image"""
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)
    
    # Invoice header
    draw.rectangle([0, 0, 800, 100], fill='#667eea')
    draw.text((50, 30), "INVOICE", fill='white')
    draw.text((50, 60), "Invoice #: INV-2026-001", fill='white')
    
    # Company details
    draw.text((50, 150), "ABC Company Inc.", fill='black')
    draw.text((50, 180), "123 Business Street", fill='black')
    draw.text((50, 210), "New York, NY 10001", fill='black')
    
    # Customer details
    draw.text((500, 150), "Bill To:", fill='black')
    draw.text((500, 180), "John Doe", fill='black')
    draw.text((500, 210), "456 Customer Ave", fill='black')
    
    # Line separator
    draw.line([50, 260, 750, 260], fill='black', width=2)
    
    # Items
    draw.text((50, 290), "Description", fill='black')
    draw.text((500, 290), "Amount", fill='black')
    draw.line([50, 310, 750, 310], fill='black', width=1)
    
    draw.text((50, 340), "OCR Processing Service", fill='black')
    draw.text((500, 340), "$500.00", fill='black')
    
    draw.text((50, 380), "Cloud Storage", fill='black')
    draw.text((500, 380), "$150.00", fill='black')
    
    draw.text((50, 420), "Support Package", fill='black')
    draw.text((500, 420), "$200.00", fill='black')
    
    # Total
    draw.line([50, 460, 750, 460], fill='black', width=2)
    draw.text((50, 490), "TOTAL", fill='black')
    draw.text((500, 490), "$850.00", fill='black')
    
    # Footer
    draw.text((50, 850), "Thank you for your business!", fill='#667eea')
    draw.text((50, 880), "Payment due within 30 days", fill='black')
    
    return img

def create_sample_document():
    """Create a sample document with paragraphs"""
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)
    
    # Title
    draw.text((50, 50), "Optical Character Recognition", fill='black')
    draw.text((50, 80), "Technology Overview", fill='#667eea')
    
    # Paragraph 1
    para1 = """OCR technology converts images of typed,
handwritten, or printed text into machine-
encoded text. It is widely used for data
entry from printed paper records."""
    
    y_position = 150
    for line in para1.split('\n'):
        draw.text((50, y_position), line.strip(), fill='black')
        y_position += 30
    
    # Paragraph 2
    draw.text((50, 300), "Key Applications:", fill='#764ba2')
    
    applications = [
        "• Document digitization",
        "• Automated data entry",
        "• Text searchability",
        "• Accessibility features",
        "• Invoice processing"
    ]
    
    y_position = 340
    for app in applications:
        draw.text((70, y_position), app, fill='black')
        y_position += 35
    
    # Paragraph 3
    draw.text((50, 550), "Benefits:", fill='#764ba2')
    
    benefits = """Time savings: Reduces manual data entry
Accuracy: Minimizes human errors
Scalability: Processes large volumes
Cost effective: Lower operational costs"""
    
    y_position = 590
    for line in benefits.split('\n'):
        draw.text((50, y_position), line.strip(), fill='black')
        y_position += 35
    
    return img

def create_sample_receipt():
    """Create a sample receipt"""
    img = Image.new('RGB', (600, 800), color='white')
    draw = ImageDraw.Draw(img)
    
    # Store header
    draw.text((200, 30), "QuickMart", fill='black')
    draw.text((150, 60), "Your Neighborhood Store", fill='gray')
    draw.text((180, 90), "123 Main Street", fill='black')
    draw.text((150, 120), "Phone: (555) 123-4567", fill='black')
    
    # Receipt details
    draw.line([50, 160, 550, 160], fill='black', width=2)
    draw.text((50, 180), "Date: 01/17/2026", fill='black')
    draw.text((50, 210), "Time: 14:32:15", fill='black')
    draw.text((50, 240), "Receipt #: 00012345", fill='black')
    draw.line([50, 270, 550, 270], fill='black', width=1)
    
    # Items
    items = [
        ("Milk (1 gallon)", "4.99"),
        ("Bread (whole wheat)", "3.49"),
        ("Eggs (dozen)", "5.99"),
        ("Coffee (12 oz)", "8.99"),
        ("Bananas (3 lbs)", "2.97")
    ]
    
    y_pos = 300
    for item, price in items:
        draw.text((50, y_pos), item, fill='black')
        draw.text((450, y_pos), f"${price}", fill='black')
        y_pos += 35
    
    # Totals
    draw.line([50, 520, 550, 520], fill='black', width=1)
    draw.text((50, 540), "Subtotal:", fill='black')
    draw.text((450, 540), "$26.43", fill='black')
    
    draw.text((50, 570), "Tax (8%):", fill='black')
    draw.text((450, 570), "$2.11", fill='black')
    
    draw.line([50, 600, 550, 600], fill='black', width=2)
    draw.text((50, 620), "TOTAL:", fill='black')
    draw.text((450, 620), "$28.54", fill='black')
    
    # Footer
    draw.text((150, 700), "Thank you for shopping!", fill='black')
    draw.text((180, 730), "Visit us again soon!", fill='#667eea')
    
    return img

def create_sample_form():
    """Create a sample form"""
    img = Image.new('RGB', (800, 1000), color='white')
    draw = ImageDraw.Draw(img)
    
    # Form header
    draw.rectangle([0, 0, 800, 80], fill='#667eea')
    draw.text((250, 25), "Registration Form", fill='white')
    
    # Form fields
    fields = [
        ("First Name:", "John"),
        ("Last Name:", "Doe"),
        ("Email:", "john.doe@example.com"),
        ("Phone:", "(555) 123-4567"),
        ("Address:", "123 Main Street"),
        ("City:", "New York"),
        ("State:", "NY"),
        ("ZIP Code:", "10001"),
        ("Date:", "01/17/2026")
    ]
    
    y_pos = 120
    for label, value in fields:
        draw.text((50, y_pos), label, fill='#764ba2')
        draw.rectangle([250, y_pos-5, 750, y_pos+25], outline='black', width=1)
        draw.text((260, y_pos), value, fill='black')
        y_pos += 60
    
    # Checkbox section
    draw.text((50, 700), "Preferences:", fill='#764ba2')
    draw.rectangle([50, 730, 70, 750], outline='black', width=2)
    draw.text((80, 732), "Email notifications", fill='black')
    
    draw.rectangle([50, 770, 70, 790], outline='black', width=2)
    draw.text((35, 752), "X", fill='black')
    draw.text((80, 772), "SMS notifications", fill='black')
    
    # Signature
    draw.text((50, 850), "Signature:", fill='#764ba2')
    draw.line([200, 875, 600, 875], fill='black', width=1)
    draw.text((350, 880), "John Doe", fill='black')
    
    return img

def main():
    """Generate all sample images"""
    output_dir = "/app/sample_images"
    os.makedirs(output_dir, exist_ok=True)
    
    print("📸 Generating sample test images...")
    print("-" * 50)
    
    # Generate images
    samples = [
        ("invoice", create_sample_invoice(), "Sample invoice with header, items, and total"),
        ("document", create_sample_document(), "Multi-paragraph document with formatting"),
        ("receipt", create_sample_receipt(), "Store receipt with items and prices"),
        ("form", create_sample_form(), "Registration form with fields and checkboxes")
    ]
    
    for name, img, description in samples:
        filepath = f"{output_dir}/{name}.png"
        img.save(filepath)
        print(f"✓ Created: {name}.png")
        print(f"  Description: {description}")
        print(f"  Path: {filepath}")
        print()
    
    print("-" * 50)
    print(f"✅ Generated {len(samples)} sample images")
    print(f"📁 Location: {output_dir}/")
    print("\n🚀 You can now use these images to test the OCR dashboard!")
    print("\nTo test:")
    print("1. Access the Streamlit dashboard")
    print("2. Upload any of the generated images")
    print("3. Click 'Extract Text' to see OCR in action")

if __name__ == "__main__":
    main()
