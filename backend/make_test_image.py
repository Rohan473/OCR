from PIL import Image, ImageDraw
img = Image.new('RGB', (400, 100), color='white')
draw = ImageDraw.Draw(img)
draw.text((10, 30), 'Hello World Test', fill='black')
img.save('test_ocr.png')
print('saved test_ocr.png')
