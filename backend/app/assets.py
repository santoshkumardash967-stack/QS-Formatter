"""
Assets Module - Handle image and table extraction/processing.
"""
import os
import uuid
import subprocess
from typing import Optional
from PIL import Image
from io import BytesIO


class ImageProcessor:
    """Process and manage images extracted from documents."""
    
    def __init__(self, base_dir: str = "/tmp/qs-formatter"):
        self.base_dir = base_dir
    
    def save_image(self, image_data: bytes, job_id: str, filename: str = None) -> str:
        """
        Save image data to disk.
        Returns the file path.
        """
        if filename is None:
            filename = f"img_{uuid.uuid4().hex[:8]}.png"
        
        image_dir = os.path.join(self.base_dir, job_id, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        filepath = os.path.join(image_dir, filename)
        
        with open(filepath, "wb") as f:
            f.write(image_data)
        
        return filepath
    
    def resize_image(self, filepath: str, max_width: int = 600, max_height: int = 400) -> str:
        """
        Resize image if too large.
        Returns path to resized image.
        """
        try:
            with Image.open(filepath) as img:
                if img.width > max_width or img.height > max_height:
                    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                    img.save(filepath)
        except Exception as e:
            print(f"Error resizing image {filepath}: {e}")
        
        return filepath
    
    def get_image_base64(self, filepath: str) -> Optional[str]:
        """Get base64 encoded image for web display."""
        import base64
        
        try:
            with open(filepath, "rb") as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            return None


class TableProcessor:
    """Process tables - render complex tables to images."""
    
    def __init__(self, base_dir: str = "/tmp/qs-formatter"):
        self.base_dir = base_dir
    
    def render_table_to_image(self, html: str, job_id: str) -> Optional[str]:
        """
        Render HTML table to PNG image using wkhtmltoimage or fallback.
        Returns path to image file or None.
        """
        table_id = uuid.uuid4().hex[:8]
        output_dir = os.path.join(self.base_dir, job_id, "tables")
        os.makedirs(output_dir, exist_ok=True)
        
        html_path = os.path.join(output_dir, f"table_{table_id}.html")
        img_path = os.path.join(output_dir, f"table_{table_id}.png")
        
        # Create full HTML document
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 10px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                td, th {{ 
                    border: 1px solid #333; 
                    padding: 8px; 
                    text-align: left;
                }}
                th {{ background-color: #f0f0f0; font-weight: bold; }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """
        
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(full_html)
        
        # Try wkhtmltoimage
        try:
            result = subprocess.run(
                ["wkhtmltoimage", "--quality", "90", html_path, img_path],
                capture_output=True,
                timeout=30
            )
            if result.returncode == 0 and os.path.exists(img_path):
                return img_path
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        # Fallback: Try with chromium/puppeteer if available
        # For now, return None to indicate table should be rebuilt
        return None
    
    def is_complex_table(self, html: str) -> bool:
        """Determine if table is complex and needs image rendering."""
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table')
        
        if not table:
            return False
        
        # Check for colspan/rowspan
        if table.find(attrs={'colspan': True}) or table.find(attrs={'rowspan': True}):
            return True
        
        # Check for nested tables
        if len(table.find_all('table')) > 0:
            return True
        
        # Check row consistency
        rows = table.find_all('tr')
        if rows:
            cell_counts = [len(row.find_all(['td', 'th'])) for row in rows]
            if len(set(cell_counts)) > 1:
                return True
        
        return False
