import sys, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()

from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 100), color='white')
draw = ImageDraw.Draw(img)
draw.text((10, 30), 'Test handwriting OCR', fill='black')

from ocr_engine import ocr_engine
result = ocr_engine.extract_with_gemini(img)
print(f"Engine: {result['engine']}")
print(f"Success: {result['success']}")
print(f"Text: {repr(result['text'])}")
if 'error' in result:
    print(f"Error: {result['error']}")
