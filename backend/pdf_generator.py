"""PDF generation with searchable text layer"""
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import io
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Generate searchable PDFs with image and text layer"""
    
    def __init__(self):
        # Register fonts for Hindi support if available
        try:
            # Try to register a Hindi-compatible font
            # In production, you would include Noto Sans Devanagari or similar
            pass
        except Exception as e:
            logger.warning(f"Could not load Hindi font: {str(e)}")
    
    def create_searchable_pdf(
        self,
        image: Image.Image,
        text: str,
        output_path: str,
        page_size: Tuple = A4
    ) -> bool:
        """Create PDF with image and invisible searchable text layer"""
        try:
            # Create canvas
            c = canvas.Canvas(output_path, pagesize=page_size)
            page_width, page_height = page_size
            
            # Calculate image dimensions to fit page
            img_width, img_height = image.size
            aspect_ratio = img_width / img_height
            
            # Fit image to page with margins
            margin = 40
            available_width = page_width - (2 * margin)
            available_height = page_height - (2 * margin)
            
            if aspect_ratio > available_width / available_height:
                # Width is limiting factor
                scaled_width = available_width
                scaled_height = scaled_width / aspect_ratio
            else:
                # Height is limiting factor
                scaled_height = available_height
                scaled_width = scaled_height * aspect_ratio
            
            # Center image on page
            x = (page_width - scaled_width) / 2
            y = (page_height - scaled_height) / 2
            
            # Draw image
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            c.drawImage(
                ImageReader(img_buffer),
                x, y,
                width=scaled_width,
                height=scaled_height,
                preserveAspectRatio=True
            )
            
            # Add invisible searchable text layer
            # Place text at same position as image
            c.setFillColorRGB(1, 1, 1, alpha=0)  # Transparent text
            c.setFont("Helvetica", 12)
            
            # Split text into lines and add to PDF
            text_object = c.beginText(x, y + scaled_height - 20)
            text_object.setFont("Helvetica", 10)
            
            for line in text.split('\n'):
                if line.strip():
                    text_object.textLine(line.strip())
            
            c.drawText(text_object)
            
            # Add metadata
            c.setTitle("OCR Processed Document")
            c.setAuthor("ScribeAI")
            c.setSubject("Handwritten Notes Digitized")
            
            # Save PDF
            c.save()
            
            logger.info(f"Searchable PDF created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"PDF generation failed: {str(e)}")
            return False
    
    def create_simple_pdf(
        self,
        image: Image.Image,
        output_path: str,
        page_size: Tuple = A4
    ) -> bool:
        """Create simple PDF with just the image"""
        try:
            c = canvas.Canvas(output_path, pagesize=page_size)
            page_width, page_height = page_size
            
            # Calculate image dimensions
            img_width, img_height = image.size
            aspect_ratio = img_width / img_height
            
            margin = 40
            available_width = page_width - (2 * margin)
            available_height = page_height - (2 * margin)
            
            if aspect_ratio > available_width / available_height:
                scaled_width = available_width
                scaled_height = scaled_width / aspect_ratio
            else:
                scaled_height = available_height
                scaled_width = scaled_height * aspect_ratio
            
            x = (page_width - scaled_width) / 2
            y = (page_height - scaled_height) / 2
            
            # Save image to buffer
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            c.drawImage(
                ImageReader(img_buffer),
                x, y,
                width=scaled_width,
                height=scaled_height,
                preserveAspectRatio=True
            )
            
            c.save()
            logger.info(f"Simple PDF created: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Simple PDF generation failed: {str(e)}")
            return False

# Global PDF generator instance
pdf_generator = PDFGenerator()
