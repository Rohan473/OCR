"""OCR Engine with TrOCR and Tesseract support"""
# Lazy import transformers to speed up server startup
# from transformers import TrOCRProcessor, VisionEncoderDecoderModel
from PIL import Image
import pytesseract
import logging
from typing import Any, Dict, List, Optional
import time
import os
import re
import shutil
from pathlib import Path

from image_preprocessing import image_preprocessor

logger = logging.getLogger(__name__)

class OCREngine:
    """Multi-engine OCR processor with TrOCR and Tesseract"""
    
    def __init__(self):
        self.trocr_processor: Optional[Any] = None
        self.trocr_model: Optional[Any] = None
        self.torch: Optional[Any] = self._load_torch()
        self.device = self._resolve_device()
        self.tesseract_path = self._configure_tesseract_path()
        self.tesseract_available = bool(self.tesseract_path)
        logger.info(f"OCR Engine initialized on device: {self.device}")

    def _load_torch(self) -> Optional[Any]:
        """Load torch lazily so the server can still boot without ML dependencies."""
        try:
            import torch  # type: ignore

            return torch
        except Exception as exc:
            logger.warning(f"PyTorch is not available, TrOCR will be disabled: {exc}")
            return None

    def _resolve_device(self) -> str:
        """Pick the runtime device for TrOCR if torch is installed."""
        if self.torch is not None and self.torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _configure_tesseract_path(self) -> str:
        """Locate and configure the Tesseract executable for pytesseract."""
        configured_cmd = os.getenv("TESSERACT_CMD", "").strip()
        search_candidates = [configured_cmd] if configured_cmd else []

        discovered_on_path = shutil.which("tesseract")
        if discovered_on_path:
            search_candidates.append(discovered_on_path)

        # Common Windows install locations
        search_candidates.extend(
            [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
        )

        for candidate in search_candidates:
            if not candidate:
                continue

            candidate_path = Path(candidate)
            if candidate_path.exists():
                pytesseract.pytesseract.tesseract_cmd = str(candidate_path)
                logger.info(f"Using Tesseract executable: {candidate_path}")
                return str(candidate_path)

        logger.warning(
            "Tesseract executable not found. Install Tesseract and either add it to PATH "
            "or set the TESSERACT_CMD environment variable."
        )
        return ""

    def _format_tesseract_missing_error(self) -> str:
        """Return a user-facing setup message when Tesseract is unavailable."""
        return (
            "Tesseract OCR is not available. Install it and configure one of: "
            "(1) add the install directory to PATH, or "
            "(2) set TESSERACT_CMD to the full executable path, e.g. "
            "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        )

    def _normalize_languages(self, languages: Optional[str]) -> str:
        """Normalize a Tesseract language list and default to English when omitted."""
        tokens = [token.strip() for token in (languages or "").split("+") if token.strip()]
        if not tokens:
            return "eng"

        normalized_tokens = []
        seen = set()
        for token in tokens:
            if token not in seen:
                normalized_tokens.append(token)
                seen.add(token)

        return "+".join(normalized_tokens)

    def _is_low_quality_text(self, text: str) -> bool:
        """Detect clearly unusable OCR output so we can fall back to another engine."""
        normalized = (text or "").strip()
        if not normalized:
            return True

        compact = re.sub(r"\s+", "", normalized)
        if len(compact) <= 1:
            return True

        if compact in {"0", "1", "-", ".", ",", ":", ";", "_"}:
            return True

        alnum_chars = [char for char in compact if char.isalnum()]
        if not alnum_chars:
            return True

        alpha_chars = [char for char in alnum_chars if char.isalpha()]
        if len(compact) <= 3 and len(alpha_chars) == 0:
            return True

        return False

    def _score_text_quality(self, text: str) -> float:
        """Score OCR output quality using simple text heuristics."""
        normalized = (text or "").strip()
        if not normalized:
            return 0.0

        compact = re.sub(r"\s+", "", normalized)
        alnum_chars = [char for char in compact if char.isalnum()]
        if not alnum_chars:
            return 0.0

        alpha_ratio = sum(1 for char in alnum_chars if char.isalpha()) / len(alnum_chars)
        length_bonus = min(len(compact) / 120.0, 1.0)
        unique_ratio = len(set(compact)) / max(len(compact), 1)
        return (alpha_ratio * 0.45) + (length_bonus * 0.4) + (unique_ratio * 0.15)

    def _run_tesseract_pass(
        self,
        image: Image.Image,
        languages: str,
        psm: int,
    ) -> Dict:
        """Run a single Tesseract pass with a specific page segmentation mode."""
        languages = self._normalize_languages(languages)
        custom_config = f'--oem 3 --psm {psm} -l {languages}'
        text = pytesseract.image_to_string(image, config=custom_config)
        data = pytesseract.image_to_data(
            image,
            config=custom_config,
            output_type=pytesseract.Output.DICT
        )

        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        quality_score = self._score_text_quality(text)

        return {
            "text": text,
            "confidence": avg_confidence / 100.0,
            "word_confidences": confidences,
            "quality_score": quality_score,
            "psm": psm,
        }
    
    def load_trocr_model(self, model_name="microsoft/trocr-base-handwritten"):
        """Lazy load TrOCR model"""
        try:
            if self.torch is None:
                raise RuntimeError("PyTorch is not installed, so TrOCR is unavailable")

            if self.trocr_model is None:
                # Import transformers only when needed
                from transformers import TrOCRProcessor, VisionEncoderDecoderModel
                
                logger.info(f"Loading TrOCR model: {model_name} (this may take 1-2 minutes on first run)")
                self.trocr_processor = TrOCRProcessor.from_pretrained(model_name)
                self.trocr_model = VisionEncoderDecoderModel.from_pretrained(model_name)
                self.trocr_model.to(self.device)
                self.trocr_model.eval()  # Set to evaluation mode for faster inference
                logger.info("TrOCR model loaded successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to load TrOCR model: {str(e)}")
            return False
    
    def _segment_lines(self, image: Image.Image) -> List[Image.Image]:
        """Segment a full-page image into individual text-line crops for TrOCR."""
        import cv2
        import numpy as np

        img_array = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Merge characters/words into horizontal line blobs
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (60, 4))
        dilated = cv2.dilate(binary, kernel, iterations=2)

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return [image]

        h_total, w_total = gray.shape
        boxes = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w > w_total * 0.04 and h > 6:
                boxes.append((y, h))

        if not boxes:
            return [image]

        boxes.sort(key=lambda b: b[0])

        pad = 5
        crops = []
        for y, h in boxes:
            y1 = max(0, y - pad)
            y2 = min(h_total, y + h + pad)
            crops.append(image.crop((0, y1, w_total, y2)))

        return crops

    def extract_with_trocr(self, image: Image.Image) -> Dict:
        """Extract text using TrOCR for handwritten text"""
        start_time = time.time()

        try:
            # Load model if not already loaded
            if not self.load_trocr_model():
                raise Exception("TrOCR model failed to load")

            if self.torch is None or self.trocr_processor is None or self.trocr_model is None:
                raise RuntimeError("TrOCR components are not initialized")

            torch_module = self.torch
            trocr_processor = self.trocr_processor
            trocr_model = self.trocr_model

            if image.mode != 'RGB':
                image = image.convert('RGB')

            # TrOCR expects single-line images — segment the page first
            line_crops = self._segment_lines(image)
            logger.info(f"TrOCR: {len(line_crops)} lines segmented")

            line_texts = []
            for crop in line_crops:
                pixel_values = trocr_processor(
                    images=crop, return_tensors="pt"
                ).pixel_values.to(self.device)

                with torch_module.no_grad():
                    generated_ids = trocr_model.generate(
                        pixel_values,
                        max_length=128,
                        num_beams=4,
                    )
                text = trocr_processor.batch_decode(
                    generated_ids, skip_special_tokens=True
                )[0].strip()
                if text:
                    line_texts.append(text)

            generated_text = "\n".join(line_texts)
            processing_time = time.time() - start_time

            return {
                "text": generated_text,
                "engine": "TrOCR",
                "confidence": 0.85,
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
        languages: str = "eng",
        fast: bool = False,
    ) -> Dict:
        """Extract text using Tesseract OCR"""
        start_time = time.time()

        try:
            if not self.tesseract_available:
                raise RuntimeError(self._format_tesseract_missing_error())

            if fast:
                # Single PSM 6 pass — best for document pages, 3× faster
                best_result = self._run_tesseract_pass(image, languages, 6)
            else:
                candidate_results = [
                    self._run_tesseract_pass(image, languages, psm)
                    for psm in (6, 4, 11)
                ]
                best_result = max(
                    candidate_results,
                    key=lambda result: (result["confidence"] * 0.7) + (result["quality_score"] * 0.3)
                )
            
            processing_time = time.time() - start_time
            
            return {
                "text": best_result["text"],
                "engine": "Tesseract",
                "confidence": best_result["confidence"],
                "processing_time": processing_time,
                "success": True,
                "word_confidences": best_result["word_confidences"],
                "psm": best_result["psm"]
            }
            
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {str(e)}")
            self.tesseract_available = bool(self._configure_tesseract_path())
            return {
                "text": "",
                "engine": "Tesseract",
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "success": False,
                "error": str(e)
            }
    
    def extract_with_gemini(self, image: Image.Image) -> Dict:
        """Extract text using Gemini Vision — best for handwritten notes."""
        start_time = time.time()
        try:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is not set")

            from google import genai
            from google.genai import types
            import io

            client = genai.Client(api_key=api_key)

            buf = io.BytesIO()
            image.convert("RGB").save(buf, format="PNG")
            image_bytes = buf.getvalue()

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                    (
                        "Transcribe every word of handwritten text visible in this image. "
                        "Preserve line breaks and the original structure. "
                        "Output only the transcribed text — no commentary, no explanations."
                    ),
                ],
            )

            text = response.text.strip() if response.text else ""
            return {
                "text": text,
                "engine": "Gemini",
                "confidence": 0.92,
                "processing_time": time.time() - start_time,
                "success": bool(text),
            }
        except Exception as e:
            logger.error(f"Gemini OCR failed: {e}")
            return {
                "text": "",
                "engine": "Gemini",
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "success": False,
                "error": str(e),
            }

    def extract_with_gemini_batch(self, images: List[Image.Image]) -> tuple:
        """Send all page images in a single Gemini call and return (combined_text, confidence).
        This avoids per-page rate limits and is faster than N sequential calls."""
        start_time = time.time()
        try:
            api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is not set")

            from google import genai
            from google.genai import types
            import io

            client = genai.Client(api_key=api_key)

            parts = []
            for image in images:
                buf = io.BytesIO()
                image.convert("RGB").save(buf, format="PNG")
                parts.append(types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"))

            n = len(images)
            sep = "--- Page {n} ---"
            parts.append(
                f"This is a {n}-page document. "
                "Transcribe every word of handwritten text visible in each page image. "
                "Preserve line breaks and structure. "
                f"Separate pages with '--- Page 1 ---', '--- Page 2 ---', etc. "
                "Output only the transcribed text — no commentary."
            )

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=parts,
            )

            text = response.text.strip() if response.text else ""
            logger.info(
                f"Gemini batch OCR: {n} pages, {len(text.split())} words, "
                f"{time.time() - start_time:.1f}s"
            )
            return text, 0.92 if text else 0.0

        except Exception as e:
            logger.error(f"Gemini batch OCR failed: {e}")
            return "", 0.0

    def extract_text(
        self,
        image: Image.Image,
        engine: str = "trocr",
        languages: str = "eng",
        fast: bool = False,
    ) -> Dict:
        """Main extraction method with engine selection"""
        languages = self._normalize_languages(languages)

        if engine.lower() == "gemini":
            return self.extract_with_gemini(image)

        if engine.lower() == "trocr":
            result = self.extract_with_trocr(image)
            if not result["success"] or self._is_low_quality_text(result.get("text", "")):
                if result["success"]:
                    logger.warning(
                        "TrOCR produced low-quality output '%s', falling back to Tesseract",
                        result.get("text", "")
                    )
                else:
                    logger.warning("TrOCR failed, falling back to Tesseract")
                tesseract_ready_image = image_preprocessor.preprocess_for_engine(image, engine="tesseract")
                result = self.extract_with_tesseract(tesseract_ready_image, languages, fast=fast)
        else:
            result = self.extract_with_tesseract(image, languages, fast=fast)

        return result

# Global OCR engine instance
ocr_engine = OCREngine()
