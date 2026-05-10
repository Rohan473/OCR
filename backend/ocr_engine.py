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
        self._torch: Optional[Any] = None  # loaded on first use
        self._torch_loaded = False
        self.tesseract_path = self._configure_tesseract_path()
        self.tesseract_available = bool(self.tesseract_path)
        logger.info("OCR Engine initialized (torch loads on first TrOCR use)")

    @property
    def torch(self):
        if not self._torch_loaded:
            self._torch_loaded = True
            self._torch = self._load_torch()
        return self._torch

    @property
    def device(self):
        return self._resolve_device()

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

    def _compute_sequence_confidence(self, scores, sequences, seq_idx: int) -> float:
        """Compute geometric-mean token probability for one generated sequence."""
        import math
        if not scores:
            return 0.0
        F = self.torch.nn.functional
        eos_id = getattr(self.trocr_processor.tokenizer, "eos_token_id", None)
        log_probs = []
        for step_idx, step_scores in enumerate(scores):
            token_pos = step_idx + 1  # sequences[:,0] is the BOS token
            if token_pos >= sequences.shape[1]:
                break
            token_id = sequences[seq_idx, token_pos].item()
            if eos_id is not None and token_id == eos_id:
                break
            probs = F.softmax(step_scores[seq_idx], dim=-1)
            prob = float(probs[token_id].item())
            log_probs.append(math.log(max(prob, 1e-10)))
        if not log_probs:
            return 0.0
        return math.exp(sum(log_probs) / len(log_probs))

    def _crop_has_content(self, crop: "Image.Image", min_ink_ratio: float = 0.03) -> bool:
        """Return True if the crop has enough dark pixels to plausibly contain text."""
        try:
            import numpy as np
            arr = np.array(crop.convert("L"))
            return float(np.sum(arr < 128)) / arr.size >= min_ink_ratio
        except Exception:
            return True  # default to keeping the crop when numpy isn't available

    def _is_hallucination(self, text: str) -> bool:
        """Detect common TrOCR hallucination patterns."""
        if not text or len(text.strip()) < 2:
            return True
        compact = re.sub(r'\s+', '', text)
        # Same character repeated 5+ times consecutively
        if re.search(r'(.)\1{4,}', text):
            return True
        # Mostly digits from a handwriting-trained model
        if compact and sum(c.isdigit() for c in compact) / len(compact) > 0.75:
            return True
        words = text.split()
        # Repeating bigram pattern (>60% repeated bigrams = looping output)
        if len(words) >= 6:
            bigrams = [(words[i], words[i + 1]) for i in range(len(words) - 1)]
            if len(set(bigrams)) / len(bigrams) < 0.4:
                return True
        # "a b c d e f ..." — single-letter alphabet run memorised from training data
        single_letter_words = [w for w in words if len(w) == 1 and w.isalpha()]
        if len(single_letter_words) >= 4 and len(single_letter_words) / max(len(words), 1) >= 0.35:
            return True
        # Wikipedia-style citation noise: "via Newspapers com" or "a b c d" mixed with entities
        if re.search(r'\bvia\b.{0,30}\bcom\b', text, re.IGNORECASE):
            return True
        return False

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
            # Cap at 30 lines; batch inference is fast so this is generous
            if len(line_crops) > 30:
                line_crops = line_crops[:30]

            # Drop near-blank crops — feeding empty regions causes the model to free-generate
            line_crops = [c for c in line_crops if self._crop_has_content(c)]
            if not line_crops:
                logger.warning("TrOCR: all crops were blank, skipping model inference")
                return {
                    "text": "",
                    "engine": "TrOCR",
                    "confidence": 0.0,
                    "processing_time": time.time() - start_time,
                    "success": False,
                    "error": "no content detected in line crops",
                }

            logger.info(f"TrOCR: {len(line_crops)} non-blank lines segmented")

            # Batch all crops in one forward pass — much faster than N sequential calls
            pixel_values = trocr_processor(
                images=line_crops, return_tensors="pt"
            ).pixel_values.to(self.device)

            with torch_module.no_grad():
                gen_output = trocr_model.generate(
                    pixel_values,
                    max_length=48,
                    num_beams=1,            # greedy — 4-8x faster than beam search on CPU
                    repetition_penalty=1.8, # suppress hallucinated digit repetitions
                    output_scores=True,
                    return_dict_in_generate=True,
                )

            generated_ids = gen_output.sequences
            scores = gen_output.scores  # tuple of (batch, vocab) tensors, one per step

            decoded = trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)

            line_results = []
            for i, raw_text in enumerate(decoded):
                # Get actual model token-level confidence instead of text heuristic
                seq_conf = self._compute_sequence_confidence(scores, generated_ids, i)

                # Clean trailing digit-run hallucinations common on sparse images
                cleaned = re.sub(r'(\s*\b[0-9]\b\s*){3,}$', '', raw_text).strip()

                if self._is_hallucination(cleaned):
                    logger.debug("TrOCR line %d dropped as hallucination: %r (conf=%.2f)", i, cleaned, seq_conf)
                    continue
                if seq_conf < 0.05:
                    logger.debug("TrOCR line %d dropped: confidence too low (%.3f)", i, seq_conf)
                    continue

                line_results.append((cleaned, seq_conf))

            if line_results:
                generated_text = "\n".join(t for t, _ in line_results)
                avg_confidence = sum(c for _, c in line_results) / len(line_results)
            else:
                generated_text = ""
                avg_confidence = 0.0

            logger.info(
                "TrOCR: %d/%d lines kept, avg confidence=%.2f",
                len(line_results), len(decoded), avg_confidence,
            )

            processing_time = time.time() - start_time

            return {
                "text": generated_text,
                "engine": "TrOCR",
                "confidence": avg_confidence,
                "processing_time": processing_time,
                "success": bool(generated_text)
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
                    for psm in (3, 6, 4)
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
                        "You are a document digitiser. Process this image in reading order (top-to-bottom, left-to-right) and output everything you see:\n"
                        "1. HANDWRITTEN / PRINTED TEXT — transcribe exactly, preserving line breaks.\n"
                        "2. DIAGRAMS / FIGURES — write [DIAGRAM: <concise description of what it shows, labels, arrows, and key elements>]\n"
                        "3. CHARTS / GRAPHS — write [CHART: <type, axes, trend or data described>]\n"
                        "4. TABLES — reproduce using plain-text pipe formatting (| col | col |).\n"
                        "5. MATHEMATICAL EXPRESSIONS — write in LaTeX inline notation.\n"
                        "Output only the document content — no meta-commentary, no explanations."
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

    @staticmethod
    def _describe_diagrams(markdown: str, img_map: Dict[str, str], budget: list) -> str:
        """Replace ![img-N.xxx](img-N.xxx) placeholders with [DIAGRAM: ...] descriptions.

        budget is a one-element list [remaining_calls] shared across pages so the
        total Groq vision calls per document stay within rate-limit bounds.
        """
        import re

        pattern = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')

        def replace(match: re.Match) -> str:
            img_id = match.group(1)
            b64 = img_map.get(img_id)
            if not b64:
                return "[DIAGRAM]"

            if budget[0] <= 0:
                return "[DIAGRAM]"

            # Mistral returns image_base64 already as a data URL
            data_url = b64 if b64.startswith("data:") else f"data:image/jpeg;base64,{b64}"

            try:
                groq_key = os.environ.get("GROQ_API_KEY")
                if not groq_key:
                    return "[DIAGRAM]"
                from groq import Groq
                groq_client = Groq(api_key=groq_key)
                resp = groq_client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {
                                "type": "text",
                                "text": (
                                    "Describe this diagram or figure from a student's notes in 1-3 sentences. "
                                    "Include all labels, axes, arrows, and key elements. "
                                    "Be concise and factual. Do not start with 'This image shows'."
                                ),
                            },
                        ],
                    }],
                    max_tokens=150,
                )
                budget[0] -= 1
                desc = resp.choices[0].message.content.strip()
                return f"[DIAGRAM: {desc}]"
            except Exception as exc:
                logger.warning("Groq vision failed for diagram: %s", str(exc)[:120])
                return "[DIAGRAM]"

        return pattern.sub(replace, markdown)

    def _mistral_ocr_page(
        self, client: Any, image: Image.Image, page_label: str = "", budget: list = None
    ) -> str:
        """Run Mistral OCR on one image and return markdown with diagrams described."""
        import base64
        import io

        if budget is None:
            budget = [8]

        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "image_url",
                "image_url": f"data:image/png;base64,{image_b64}",
            },
            include_image_base64=True,
        )

        img_map: Dict[str, str] = {}
        for page in response.pages:
            for img_obj in (page.images or []):
                img_map[img_obj.id] = img_obj.image_base64

        parts = []
        for page in response.pages:
            md = page.markdown or ""
            if img_map and budget[0] > 0:
                md = self._describe_diagrams(md, img_map, budget)
            elif img_map:
                md = re.sub(r'!\[[^\]]*\]\([^)]+\)', '[DIAGRAM]', md)
            parts.append(md)

        text = "\n\n".join(parts).strip()
        if page_label:
            return f"{page_label}\n{text}" if text else ""
        return text

    def extract_with_mistral(self, image: Image.Image) -> Dict:
        """Extract text using Mistral OCR — handles handwriting, diagrams, tables, math."""
        start_time = time.time()
        try:
            api_key = os.environ.get("MISTRAL_API_KEY")
            if not api_key:
                raise RuntimeError("MISTRAL_API_KEY is not set")

            from mistralai.client import Mistral

            client = Mistral(api_key=api_key)
            text = self._mistral_ocr_page(client, image)
            return {
                "text": text,
                "engine": "Mistral",
                "confidence": 0.90,
                "processing_time": time.time() - start_time,
                "success": bool(text),
            }
        except Exception as e:
            logger.error(f"Mistral OCR failed: {e}")
            return {
                "text": "",
                "engine": "Mistral",
                "confidence": 0.0,
                "processing_time": time.time() - start_time,
                "success": False,
                "error": str(e),
            }

    def extract_with_mistral_batch(self, images: List[Image.Image]) -> tuple:
        """Process multiple page images with Mistral OCR, return (combined_text, confidence).

        Each page is wrapped in its own try/except so a single bad page (rate limit,
        empty response, oversized image) cannot drop the whole document.
        """
        start_time = time.time()
        api_key = os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            logger.error("MISTRAL_API_KEY is not set")
            return "", 0.0

        try:
            from mistralai.client import Mistral
        except Exception as e:
            logger.error(f"Mistral SDK import failed: {type(e).__name__}: {e!r}")
            return "", 0.0

        client = Mistral(api_key=api_key)
        page_texts: List[str] = []
        budget = [8]  # max 8 diagram descriptions per document
        failed_pages: List[int] = []

        for idx, image in enumerate(images):
            page_num = idx + 1
            try:
                text = self._mistral_ocr_page(
                    client, image, page_label=f"--- Page {page_num} ---", budget=budget
                )
                if text:
                    page_texts.append(text)
                else:
                    page_texts.append(f"--- Page {page_num} ---\n[No text extracted]")
            except Exception as e:
                logger.warning(
                    f"Mistral OCR failed on page {page_num}: {type(e).__name__}: {e!r}"
                )
                failed_pages.append(page_num)
                page_texts.append(f"--- Page {page_num} ---\n[Page OCR failed]")

        combined = "\n\n".join(page_texts)
        logger.info(
            f"Mistral batch OCR: {len(images)} pages "
            f"({len(failed_pages)} failed: {failed_pages}), "
            f"{len(combined.split())} words, {time.time() - start_time:.1f}s"
        )
        confidence = 0.90 if combined and not failed_pages else (0.7 if combined else 0.0)
        return combined, confidence

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
            parts.append(
                f"You are a document digitiser. This is a {n}-page document. "
                "Process each page in reading order (top-to-bottom, left-to-right) and output everything you see:\n"
                "1. HANDWRITTEN / PRINTED TEXT — transcribe exactly, preserving line breaks.\n"
                "2. DIAGRAMS / FIGURES — write [DIAGRAM: <concise description of what it shows, labels, arrows, and key elements>]\n"
                "3. CHARTS / GRAPHS — write [CHART: <type, axes, trend or data described>]\n"
                "4. TABLES — reproduce using plain-text pipe formatting (| col | col |).\n"
                "5. MATHEMATICAL EXPRESSIONS — write in LaTeX inline notation.\n"
                f"Separate pages with '--- Page 1 ---', '--- Page 2 ---', etc. "
                "Output only the document content — no meta-commentary, no explanations."
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
        engine: str = "mistral",
        languages: str = "eng",
        fast: bool = False,
    ) -> Dict:
        """Main extraction method with engine selection.

        Mistral is the primary engine. Falls back through Gemini → TrOCR → Tesseract.
        """
        languages = self._normalize_languages(languages)
        mistral_key = os.environ.get("MISTRAL_API_KEY")
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

        # Mistral: primary for 'mistral' or 'auto' when key is present
        if engine.lower() in ("mistral", "auto") and mistral_key:
            result = self.extract_with_mistral(image)
            if result["success"]:
                return result
            logger.warning("Mistral OCR failed (%s), falling back to next engine",
                           result.get("error", "unknown"))
        elif engine.lower() == "mistral" and not mistral_key:
            return {
                "text": "",
                "engine": "Mistral",
                "confidence": 0.0,
                "processing_time": 0.0,
                "success": False,
                "error": "MISTRAL_API_KEY is not set. Get a free key at https://console.mistral.ai/",
            }

        # Gemini: secondary API engine
        if engine.lower() in ("gemini", "auto") and gemini_key:
            result = self.extract_with_gemini(image)
            if result["success"]:
                return result
            logger.warning("Gemini OCR failed (%s), falling back to local engines",
                           result.get("error", "unknown"))
        elif engine.lower() == "gemini" and not gemini_key:
            return {
                "text": "",
                "engine": "Gemini",
                "confidence": 0.0,
                "processing_time": 0.0,
                "success": False,
                "error": "GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey",
            }

        # TrOCR: good for handwriting
        if engine.lower() in ("trocr", "auto"):
            result = self.extract_with_trocr(image)
            if result["success"] and not self._is_low_quality_text(result.get("text", "")):
                return result
            logger.warning("TrOCR result unusable, falling back to Tesseract")

        # Tesseract: final fallback
        tesseract_ready_image = image_preprocessor.preprocess_for_engine(image, engine="tesseract")
        return self.extract_with_tesseract(tesseract_ready_image, languages, fast=fast)

# Global OCR engine instance
ocr_engine = OCREngine()
