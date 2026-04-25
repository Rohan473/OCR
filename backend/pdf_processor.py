import logging
from pathlib import Path
from typing import List, Tuple
from PIL import Image
import pypdfium2 as pdfium

logger = logging.getLogger(__name__)

RENDER_SCALE = 2.5  # 2.5x = ~180 DPI — good quality without memory spike


class PDFProcessor:
    def extract_text_layer(self, pdf_path: str, max_pages: int = 0) -> Tuple[str, bool]:
        """Extract the embedded text layer from a PDF without rendering.
        Returns (text, has_meaningful_text). Falls back gracefully if no layer exists."""
        doc = pdfium.PdfDocument(pdf_path)
        page_texts = []
        try:
            total = len(doc)
            limit = min(total, max_pages) if max_pages > 0 else total
            multi = limit > 1
            for i in range(limit):
                page = doc[i]
                try:
                    textpage = page.get_textpage()
                    text = textpage.get_text_range().strip()
                    textpage.close()
                    if text:
                        page_texts.append(f"--- Page {i + 1} ---\n{text}" if multi else text)
                finally:
                    page.close()
        finally:
            doc.close()

        combined = "\n\n".join(page_texts)
        # Require at least 30 words to consider the text layer meaningful
        has_meaningful_text = len(combined.split()) >= 30
        return combined, has_meaningful_text

    def page_count(self, pdf_path: str) -> int:
        doc = pdfium.PdfDocument(pdf_path)
        try:
            return len(doc)
        finally:
            doc.close()

    def pdf_to_images(self, pdf_path: str, max_pages: int = 0) -> List[Image.Image]:
        """Render PDF pages as PIL Images, optionally capped at max_pages."""
        doc = pdfium.PdfDocument(pdf_path)
        images = []
        try:
            total = len(doc)
            limit = min(total, max_pages) if max_pages > 0 else total
            if max_pages > 0 and total > max_pages:
                logger.warning(f"PDF has {total} pages, rendering only first {max_pages}")
            for page_index in range(limit):
                page = doc[page_index]
                bitmap = page.render(scale=RENDER_SCALE, rotation=0)
                pil_image = bitmap.to_pil()
                images.append(pil_image.convert("RGB"))
                bitmap.close()
                page.close()
        finally:
            doc.close()
        return images

    def ocr_images(
        self,
        images: List[Image.Image],
        ocr_fn,
        engine: str = "tesseract",
        languages: str = "eng",
        preprocessor=None,
    ) -> Tuple[str, float]:
        """Run OCR on a list of already-rendered page images."""
        page_texts = []
        confidences = []
        multi = len(images) > 1

        for i, image in enumerate(images):
            try:
                proc_image = preprocessor.preprocess_for_engine(image, engine=engine) if preprocessor else image
                result = ocr_fn(proc_image, engine=engine, languages=languages, fast=True)
                if result.get("success"):
                    text = result.get("text", "").strip()
                    if text:
                        page_texts.append(f"--- Page {i + 1} ---\n{text}" if multi else text)
                    confidences.append(result.get("confidence", 0.0))
            except Exception as e:
                logger.warning(f"OCR failed on page {i + 1}: {e}")

        combined = "\n\n".join(page_texts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return combined, avg_confidence

    def extract_text_with_ocr(
        self,
        pdf_path: str,
        ocr_fn,
        engine: str = "tesseract",
        languages: str = "eng",
        preprocessor=None,
        max_pages: int = 20,
    ) -> Tuple[str, float]:
        images = self.pdf_to_images(pdf_path, max_pages=max_pages)
        if not images:
            return "", 0.0
        return self.ocr_images(images, ocr_fn, engine=engine, languages=languages, preprocessor=preprocessor)


pdf_processor = PDFProcessor()
