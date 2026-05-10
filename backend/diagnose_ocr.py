"""
ScribeAI OCR Diagnostic Script
Run: python diagnose_ocr.py <image_path>
"""
import sys
import time
from PIL import Image
import pytesseract
import shutil
from pathlib import Path

# ── Tesseract setup ──────────────────────────────────────────────────────────
def setup_tesseract():
    for candidate in [
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if candidate and Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            return True
    return False

# ── PSM descriptions ─────────────────────────────────────────────────────────
PSM_LABELS = {
    3:  "Fully automatic (default)",
    4:  "Single column, varying sizes",
    6:  "Uniform block of text",
    7:  "Single text line",
    8:  "Single word",
    11: "Sparse text (no structure)",
    12: "Sparse text + OSD",
    13: "Raw line (bypass heuristics)",
}

# ── Preprocessing variants ───────────────────────────────────────────────────
def no_preprocessing(img):
    """Return image as-is"""
    return img

def basic_preprocessing(img):
    """Grayscale only"""
    import cv2, numpy as np
    arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2GRAY)
    return Image.fromarray(arr)

def full_preprocessing(img):
    """Full pipeline: resize → deskew → grayscale → CLAHE → denoise → threshold"""
    import cv2, numpy as np
    arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    # Resize
    h, w = arr.shape[:2]
    if h < 800 or h > 2400:
        ratio = 2400 / h
        arr = cv2.resize(arr, (int(w * ratio), 2400), interpolation=cv2.INTER_CUBIC)
    # Grayscale
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    # CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    # Denoise
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    # Adaptive threshold
    gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 11, 2)
    return Image.fromarray(gray)

def high_dpi_preprocessing(img):
    """Force high DPI (2400px height) + grayscale, no threshold"""
    import cv2, numpy as np
    arr = cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    h, w = arr.shape[:2]
    ratio = 2400 / h
    arr = cv2.resize(arr, (int(w * ratio), 2400), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(arr, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    return Image.fromarray(gray)

PREPROCESSING_VARIANTS = {
    "No preprocessing":        no_preprocessing,
    "Grayscale only":          basic_preprocessing,
    "Full pipeline (current)": full_preprocessing,
    "High DPI + CLAHE":        high_dpi_preprocessing,
}

# ── Single Tesseract pass ────────────────────────────────────────────────────
def run_pass(img, psm, lang="eng"):
    config = f"--oem 3 --psm {psm} -l {lang}"
    try:
        data = pytesseract.image_to_data(img, config=config,
                                          output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(img, config=config).strip()
        confs = [int(c) for c in data["conf"] if int(c) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0
        word_count = len([w for w in text.split() if w])
        return avg_conf, word_count, text[:120].replace("\n", " ")
    except Exception as e:
        return 0, 0, f"ERROR: {e}"

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python diagnose_ocr.py <path_to_image>")
        sys.exit(1)

    image_path = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "eng"

    if not setup_tesseract():
        print("❌  Tesseract not found. Add it to PATH or set TESSERACT_CMD.")
        sys.exit(1)

    img = Image.open(image_path).convert("RGB")
    print(f"\n{'='*65}")
    print(f"  ScribeAI OCR Diagnostic")
    print(f"  Image : {image_path}  ({img.size[0]}x{img.size[1]} px)")
    print(f"  Language: {lang}")
    print(f"{'='*65}\n")

    best_conf  = 0
    best_combo = ("", 0)

    for prep_name, prep_fn in PREPROCESSING_VARIANTS.items():
        print(f"── Preprocessing: {prep_name} ──")
        print(f"  {'PSM':<4} {'Label':<38} {'Conf%':>6}  {'Words':>5}  Preview")
        print(f"  {'-'*4} {'-'*38} {'-'*6}  {'-'*5}  {'-'*30}")

        processed = prep_fn(img)

        for psm, label in PSM_LABELS.items():
            conf, words, preview = run_pass(processed, psm, lang)
            marker = " ◀ BEST" if conf > best_conf else ""
            if conf > best_conf:
                best_conf  = conf
                best_combo = (prep_name, psm)
            print(f"  {psm:<4} {label:<38} {conf:>5.1f}%  {words:>5}  {preview[:50]}{marker}")

        print()

    print(f"{'='*65}")
    print(f"  ✅  BEST COMBO  →  Preprocessing: '{best_combo[0]}'")
    print(f"                     PSM: {best_combo[1]} — {PSM_LABELS[best_combo[1]]}")
    print(f"                     Confidence: {best_conf:.1f}%")
    print(f"{'='*65}")
    print()
    print("ACTION:")
    print(f"  In ocr_engine.py → extract_with_tesseract():")
    print(f"  Change PSM candidates to include PSM {best_combo[1]} as the first option.")
    if best_combo[0] == "No preprocessing":
        print("  Skip preprocessing for this image type — it's hurting accuracy.")
    elif best_combo[0] == "High DPI + CLAHE":
        print("  Switch to high-DPI + CLAHE only (skip adaptive threshold).")
    elif best_combo[0] == "Full pipeline (current)":
        print("  Current pipeline is already the best — the PSM change alone should help.")

if __name__ == "__main__":
    main()
