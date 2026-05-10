import sys, time
sys.path.insert(0, '.')
from ocr_engine import ocr_engine
from PIL import Image, ImageDraw

# Create a multi-line test image (simulates a page)
img = Image.new('RGB', (600, 300), color='white')
draw = ImageDraw.Draw(img)
lines = [
    "Hello World Test",
    "Transaction Cost Analysis",
    "Market Data Pipeline",
    "DBMS Notes Page 1",
    "SELECT * FROM orders",
]
for i, line in enumerate(lines):
    draw.text((10, 20 + i * 50), line, fill='black')

img.save('test_ocr_multiline.png')
print(f"Test image: {img.size}")

start = time.time()
result = ocr_engine.extract_text(img, engine='trocr')
elapsed = time.time() - start
print(f"Engine: {result['engine']}")
print(f"Confidence: {result['confidence']}")
print(f"Text:\n{result['text'][:400]}")
print(f"Elapsed: {elapsed:.1f}s")
print(f"Success: {result['success']}")
