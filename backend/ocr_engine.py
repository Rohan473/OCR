"""OCR Engine with TrOCR and Tesseract support"""
import torch
from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import pytesseract
import numpy as np
import logging
from typing import Dict, List, Tuple
import time

logger = logging.getLogger(__name__)

class OCREngine:
    """Multi-engine OCR processor with TrOCR and Tesseract"""
    
    def __init__(self):
        self.trocr_processor = None
        self.trocr_model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"OCR Engine initialized on device: {self.device}")
    
    def load_trocr_model(self, model_name="microsoft/trocr-base-handwritten"):
        """Lazy load TrOCR model"""
        try:
            if self.trocr_model is None:
                logger.info(f"Loading TrOCR model: {model_name}")
                self.trocr_processor = TrOCRProcessor.from_pretrained(model_name)
                self.trocr_model = VisionEncoderDecoderModel.from_pretrained(model_name)
                self.trocr_model.to(self.device)
                logger.info("TrOCR model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load TrOCR model: {str(e)}")
            return False
    
    def extract_with_trocr(self, image: Image.Image) -> Dict:
        """Extract text using TrOCR for handwritten text"""
        start_time = time.time()
        
        try:
            # Load model if not already loaded
            if not self.load_trocr_model():
                raise Exception("TrOCR model failed to load")
            
            # Convert image to RGB
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Process image
            pixel_values = self.trocr_processor(
                images=image, 
                return_tensors="pt"
            ).pixel_values.to(self.device)
            
            # Generate text
            generated_ids = self.trocr_model.generate(pixel_values)
            generated_text = self.trocr_processor.batch_decode(
                generated_ids, 
                skip_special_tokens=True
            )[0]
            
            processing_time = time.time() - start_time
            
            return {
                "text": generated_text,
                "engine": "TrOCR",
                "confidence": 0.85,  # TrOCR doesn't provide confidence, using estimated
                "processing_time": processing_time,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"TrOCR extraction failed: {str(e)}")
            return {
                "text": "",
                "engine": "TrOCR",
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    def extract_with_tesseract(
        self, 
        image: Image.Image, 
        languages: str = "eng+hin"
    ) -> Dict:
        """Extract text using Tesseract OCR"""
        start_time = time.time()
        
        try:
            # Extract text
            custom_config = f'--oem 3 --psm 6 -l {languages}'
            text = pytesseract.image_to_string(image, config=custom_config)
            
            # Get confidence data
            data = pytesseract.image_to_data(
                image, 
                config=custom_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Calculate average confidence
            confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            processing_time = time.time() - start_time
            
            return {
                "text": text,
                "engine": "Tesseract",
                "confidence": avg_confidence / 100.0,  # Normalize to 0-1
                "processing_time": processing_time,
                "success": True,
                "word_confidences": confidences
            }
            
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {str(e)}")
            return {
                "text": "",
                "engine": "Tesseract",
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    def extract_text(
        self, 
        image: Image.Image, 
        engine: str = "trocr",
        languages: str = "eng+hin"
    ) -> Dict:
        """Main extraction method with engine selection"""
        
        if engine.lower() == "trocr":
            result = self.extract_with_trocr(image)
            # Fallback to Tesseract if TrOCR fails
            if not result["success"]:
                logger.warning("TrOCR failed, falling back to Tesseract")
                result = self.extract_with_tesseract(image, languages)
        else:
            result = self.extract_with_tesseract(image, languages)
        
        return result

# Global OCR engine instance
ocr_engine = OCREngine()
