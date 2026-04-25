"""Image preprocessing utilities for better OCR accuracy"""
import cv2
import numpy as np
from PIL import Image
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """Advanced image preprocessing for OCR"""

    def preprocess_for_engine(
        self,
        pil_image: Image.Image,
        engine: str = "trocr"
    ) -> Image.Image:
        """Apply an OCR-engine-specific preprocessing profile."""
        try:
            cv2_image = self.pil_to_cv2(pil_image)
            normalized_engine = (engine or "trocr").lower()

            cv2_image = self.resize_for_ocr(cv2_image)
            cv2_image = self.deskew(cv2_image)
            cv2_image = self.grayscale(cv2_image)
            cv2_image = self.enhance_contrast(cv2_image)

            if normalized_engine == "tesseract":
                cv2_image = self.remove_noise(cv2_image)
                cv2_image = self.adaptive_threshold(cv2_image)
            else:
                # TrOCR generally performs better with enhanced grayscale input than hard-binarized text.
                cv2_image = self.remove_noise(cv2_image)

            if len(cv2_image.shape) == 2:
                processed_image = Image.fromarray(cv2_image)
            else:
                processed_image = self.cv2_to_pil(cv2_image)

            logger.info(f"Image preprocessing completed for engine: {normalized_engine}")
            return processed_image

        except Exception as e:
            logger.error(f"Engine-specific preprocessing failed: {str(e)}")
            return pil_image
    
    @staticmethod
    def pil_to_cv2(pil_image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV format"""
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    
    @staticmethod
    def cv2_to_pil(cv2_image: np.ndarray) -> Image.Image:
        """Convert OpenCV image to PIL format"""
        return Image.fromarray(cv2.cvtColor(cv2_image, cv2.COLOR_BGR2RGB))
    
    @staticmethod
    def grayscale(image: np.ndarray) -> np.ndarray:
        """Convert to grayscale"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image
    
    @staticmethod
    def deskew(image: np.ndarray) -> np.ndarray:
        """Auto-rotate skewed image"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Apply threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Invert if necessary
            if np.mean(binary) > 127:
                binary = 255 - binary
            
            # Find contours
            coords = np.column_stack(np.where(binary > 0))
            if len(coords) == 0:
                return image
            
            # Calculate rotation angle
            angle = cv2.minAreaRect(coords)[-1]
            
            # Adjust angle
            if angle < -45:
                angle = 90 + angle
            elif angle > 45:
                angle = angle - 90
            
            # Only rotate if angle is significant
            if abs(angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(
                    image, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
                logger.info(f"Image deskewed by {angle:.2f} degrees")
                return rotated
            
            return image
            
        except Exception as e:
            logger.error(f"Deskew failed: {str(e)}")
            return image
    
    @staticmethod
    def enhance_contrast(image: np.ndarray) -> np.ndarray:
        """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Apply CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            
            return enhanced
            
        except Exception as e:
            logger.error(f"Contrast enhancement failed: {str(e)}")
            return image
    
    @staticmethod
    def remove_noise(image: np.ndarray) -> np.ndarray:
        """Apply noise removal"""
        try:
            # Apply bilateral filter to remove noise while keeping edges sharp
            denoised = cv2.bilateralFilter(image, 9, 75, 75)
            return denoised
        except Exception as e:
            logger.error(f"Noise removal failed: {str(e)}")
            return image
    
    @staticmethod
    def adaptive_threshold(image: np.ndarray) -> np.ndarray:
        """Apply adaptive thresholding"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()
            
            # Apply adaptive threshold
            binary = cv2.adaptiveThreshold(
                gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )
            
            return binary
            
        except Exception as e:
            logger.error(f"Adaptive thresholding failed: {str(e)}")
            return image
    
    @staticmethod
    def resize_for_ocr(image: np.ndarray, target_height: int = 1200) -> np.ndarray:
        """Resize image to optimal size for OCR"""
        try:
            height, width = image.shape[:2]
            
            # Only resize if image is too small or too large
            if height < 800 or height > 2400:
                ratio = target_height / height
                new_width = int(width * ratio)
                resized = cv2.resize(
                    image, 
                    (new_width, target_height),
                    interpolation=cv2.INTER_CUBIC
                )
                logger.info(f"Image resized from {width}x{height} to {new_width}x{target_height}")
                return resized
            
            return image
            
        except Exception as e:
            logger.error(f"Resize failed: {str(e)}")
            return image
    
    def preprocess(
        self, 
        pil_image: Image.Image, 
        full_pipeline: bool = True
    ) -> Image.Image:
        """Complete preprocessing pipeline"""
        try:
            # Convert to OpenCV format
            cv2_image = self.pil_to_cv2(pil_image)
            
            if full_pipeline:
                # Full pipeline for handwritten notes
                cv2_image = self.resize_for_ocr(cv2_image)
                cv2_image = self.deskew(cv2_image)
                cv2_image = self.grayscale(cv2_image)
                cv2_image = self.enhance_contrast(cv2_image)
                cv2_image = self.remove_noise(cv2_image)
                cv2_image = self.adaptive_threshold(cv2_image)
            else:
                # Basic pipeline
                cv2_image = self.grayscale(cv2_image)
                cv2_image = self.enhance_contrast(cv2_image)
            
            # Convert back to PIL
            # Handle grayscale images
            if len(cv2_image.shape) == 2:
                processed_image = Image.fromarray(cv2_image)
            else:
                processed_image = self.cv2_to_pil(cv2_image)
            
            logger.info("Image preprocessing completed")
            return processed_image
            
        except Exception as e:
            logger.error(f"Preprocessing failed: {str(e)}")
            # Return original image if preprocessing fails
            return pil_image

# Global preprocessor instance
image_preprocessor = ImagePreprocessor()
