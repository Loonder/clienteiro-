from PIL import Image
import os

images = [
    'static/team-lucas-real.jpg',
    'static/team-miqueias-real.jpg',
    'static/team-kevin-real.jpg',
    'static/favicon.png',
    'static/og-image.png'
]

def compress_image(path, quality=50):
    if not os.path.exists(path):
        print(f"Skipping: {path} (not found)")
        return
    
    filename, extension = os.path.splitext(path)
    img = Image.open(path)
    
    # Force RGB if saving as JPG
    if img.mode in ("RGBA", "P") and extension.lower() in (".jpg", ".jpeg"):
        img = img.convert("RGB")
        
    print(f"Compressing {path} (Original: {os.path.getsize(path)/1024:.1f} KB)")
    img.save(path, optimize=True, quality=quality)
    print(f"Result: {os.path.getsize(path)/1024:.1f} KB")

if __name__ == "__main__":
    for img_path in images:
        compress_image(img_path)
