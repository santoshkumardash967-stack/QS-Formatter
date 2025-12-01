"""
DOCX Parser Module - Converts DOCX to HTML and extracts question blocks.
"""
import re
import uuid
import os
import base64
from typing import List, Tuple, Optional, Dict, Any
from io import BytesIO
import mammoth
from bs4 import BeautifulSoup, NavigableString
from PIL import Image

from .models import (
    Question, Option, TableData, ImageData, QuestionFlag, 
    QuestionType, TableRenderMode
)


class DOCXParser:
    """Parser for DOCX files - extracts questions, options, tables, images."""
    
    # Patterns for question detection
    QUESTION_PATTERNS = [
        # Q1. or Q1) or Q.1 or Q 1
        r'^\s*(?:Q\.?\s*)?(\d{1,3})[\.\)]\s*',
        # 1. or 1) at start of line
        r'^\s*(\d{1,3})[\.\)]\s+',
        # Question 1: or Question 1.
        r'^\s*(?:Question|प्रश्न)\s*(\d{1,3})[\.:]\s*',
    ]
    
    # Option patterns
    OPTION_PATTERNS = [
        # (A), (a), A), a), A., a.
        r'^\s*[\(\[]?\s*([A-Da-d1-4])\s*[\)\]\.]\s*',
        # Options inline: A. x B. y C. z D. w
        r'([A-Da-d])\s*[\.\)]\s*([^A-D]+?)(?=\s*[A-D]\s*[\.\)]|$)',
    ]
    
    def __init__(self, upload_dir: str = "/tmp/qs-formatter"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
    
    def parse_docx(self, file_path: str, job_id: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parse DOCX file to HTML and extract images.
        Returns (html_content, list_of_image_info)
        """
        images = []
        image_dir = os.path.join(self.upload_dir, job_id, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        def handle_image(image):
            """Custom image handler for mammoth."""
            with image.open() as img_stream:
                img_data = img_stream.read()
                img_id = str(uuid.uuid4())[:8]
                
                # Determine extension
                content_type = image.content_type
                ext = "png"
                if "jpeg" in content_type or "jpg" in content_type:
                    ext = "jpg"
                elif "gif" in content_type:
                    ext = "gif"
                
                filename = f"img_{img_id}.{ext}"
                filepath = os.path.join(image_dir, filename)
                
                with open(filepath, "wb") as f:
                    f.write(img_data)
                
                images.append({
                    "id": img_id,
                    "filename": filename,
                    "path": filepath,
                    "content_type": content_type
                })
                
                return {"src": f"__IMAGE__{img_id}__"}
        
        with open(file_path, "rb") as f:
            result = mammoth.convert_to_html(
                f,
                convert_image=mammoth.images.img_element(handle_image)
            )
        
        return result.value, images
    
    def normalize_html(self, html: str) -> str:
        """
        Normalize HTML: remove headers/footers, clean whitespace, etc.
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Remove script and style elements
        for tag in soup(['script', 'style', 'header', 'footer']):
            tag.decompose()
        
        # Get text content and normalize whitespace
        html_str = str(soup)
        
        # Clean up excessive whitespace but preserve structure
        html_str = re.sub(r'\n\s*\n', '\n', html_str)
        
        return html_str
    
    def detect_questions(self, html: str) -> List[Dict[str, Any]]:
        """
        Detect question boundaries in HTML and extract question blocks.
        Returns list of question dictionaries.
        """
        soup = BeautifulSoup(html, 'lxml')
        questions = []
        current_question = None
        current_content = []
        
        # Flatten content into processable blocks
        blocks = self._extract_blocks(soup)
        
        for block in blocks:
            text = block.get('text', '').strip()
            html_content = block.get('html', '')
            
            # Check if this starts a new question
            q_num = self._extract_question_number(text)
            
            if q_num is not None:
                # Save previous question
                if current_question is not None:
                    current_question['content'] = current_content
                    questions.append(current_question)
                
                # Start new question
                current_question = {
                    'number': q_num,
                    'raw_text': text,
                    'raw_html': html_content
                }
                current_content = [block]
            elif current_question is not None:
                current_content.append(block)
        
        # Don't forget the last question
        if current_question is not None:
            current_question['content'] = current_content
            questions.append(current_question)
        
        return questions
    
    def _extract_blocks(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract text blocks from soup, preserving tables and images."""
        blocks = []
        
        for element in soup.body.children if soup.body else soup.children:
            if isinstance(element, NavigableString):
                text = str(element).strip()
                if text:
                    blocks.append({'type': 'text', 'text': text, 'html': text})
            elif element.name == 'table':
                # Keep table as-is
                blocks.append({
                    'type': 'table',
                    'text': element.get_text(' ', strip=True),
                    'html': str(element)
                })
            elif element.name in ['ol', 'ul']:
                # Process list items individually
                for li in element.find_all('li', recursive=False):
                    text = li.get_text(' ', strip=True)
                    blocks.append({
                        'type': 'list_item',
                        'text': text,
                        'html': str(li)
                    })
            elif element.name:
                text = element.get_text(' ', strip=True)
                if text:
                    blocks.append({
                        'type': element.name,
                        'text': text,
                        'html': str(element)
                    })
        
        return blocks
    
    def _extract_question_number(self, text: str) -> Optional[int]:
        """Extract question number from text if it starts a question."""
        for pattern in self.QUESTION_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        return None
    
    def extract_question_content(
        self, 
        question_data: Dict[str, Any],
        images: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract structured content from a question block.
        Returns dict with text, options, tables, images.
        """
        content_blocks = question_data.get('content', [])
        
        # Collect all text
        full_text = []
        options = []
        tables = []
        question_images = []
        
        for block in content_blocks:
            block_type = block.get('type')
            text = block.get('text', '')
            html = block.get('html', '')
            
            if block_type == 'table':
                table_id = str(uuid.uuid4())[:8]
                is_complex = self._is_complex_table(html)
                tables.append({
                    'id': table_id,
                    'html': html,
                    'is_complex': is_complex
                })
            else:
                # Check for images in this block
                for img_info in images:
                    img_marker = f"__IMAGE__{img_info['id']}__"
                    if img_marker in html:
                        question_images.append(img_info)
                
                # Check if this is an option
                opt = self._extract_option(text)
                if opt:
                    options.append(opt)
                else:
                    full_text.append(text)
        
        # Clean up the question text
        question_text = ' '.join(full_text)
        question_text = self._clean_question_text(question_text, question_data.get('number'))
        
        # Normalize option labels
        options = self._normalize_options(options)
        
        return {
            'number': question_data.get('number'),
            'text': question_text,
            'options': options,
            'tables': tables,
            'images': question_images
        }
    
    def _extract_option(self, text: str) -> Optional[Dict[str, str]]:
        """Extract option label and text if this is an option line."""
        text = text.strip()
        
        # Check common option patterns
        patterns = [
            r'^\s*[\(\[]?\s*([A-Da-d])\s*[\)\]\.]\s*(.+)$',
            r'^\s*([1-4])\s*[\)\]\.]\s*(.+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text)
            if match:
                label = match.group(1).upper()
                # Convert numeric to letter
                if label.isdigit():
                    label = chr(ord('A') + int(label) - 1)
                return {
                    'label': label,
                    'text': match.group(2).strip()
                }
        
        return None
    
    def _normalize_options(self, options: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Normalize option labels to A, B, C, D."""
        normalized = []
        label_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3, '1': 0, '2': 1, '3': 2, '4': 3}
        
        for opt in options:
            label = opt['label'].upper()
            if label in label_map or label in ['A', 'B', 'C', 'D']:
                normalized.append(opt)
        
        # Sort by label
        normalized.sort(key=lambda x: x['label'])
        
        return normalized
    
    def _clean_question_text(self, text: str, q_num: Optional[int]) -> str:
        """Remove question number prefix and clean up text."""
        # Remove question number patterns
        for pattern in self.QUESTION_PATTERNS:
            text = re.sub(pattern, '', text, count=1)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def _is_complex_table(self, html: str) -> bool:
        """Determine if a table is complex (merged cells, nested tables, etc.)."""
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
        
        # Check for irregular row lengths
        rows = table.find_all('tr')
        if rows:
            cell_counts = [len(row.find_all(['td', 'th'])) for row in rows]
            if len(set(cell_counts)) > 1:
                return True
        
        return False
    
    def parse_file_to_questions(
        self, 
        file_path: str, 
        job_id: str,
        language: str = "english"
    ) -> List[Dict[str, Any]]:
        """
        Complete parsing pipeline: DOCX -> HTML -> Questions
        """
        # Parse DOCX to HTML
        html, images = self.parse_docx(file_path, job_id)
        
        # Normalize HTML
        html = self.normalize_html(html)
        
        # Detect questions
        question_blocks = self.detect_questions(html)
        
        # Extract structured content
        questions = []
        for q_block in question_blocks:
            q_content = self.extract_question_content(q_block, images)
            q_content['language'] = language
            questions.append(q_content)
        
        return questions


class QuestionExtractor:
    """
    Improved question extractor that handles edge cases better.
    """
    
    def __init__(self):
        self.parser = DOCXParser()
    
    def extract_from_html(self, html: str, images: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Extract questions from HTML content using multiple strategies.
        """
        if images is None:
            images = []
        
        soup = BeautifulSoup(html, 'lxml')
        
        # Strategy 1: Look for <ol> lists where each item might be a question
        questions = self._extract_from_ordered_list(soup, images)
        
        if questions:
            return questions
        
        # Strategy 2: Look for paragraph-based questions
        questions = self._extract_from_paragraphs(soup, images)
        
        return questions
    
    def _extract_from_ordered_list(
        self, 
        soup: BeautifulSoup, 
        images: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract questions from ordered lists."""
        questions = []
        current_question = None
        question_num = 0
        
        # Get all top-level elements
        elements = list(soup.body.children) if soup.body else list(soup.children)
        
        i = 0
        while i < len(elements):
            element = elements[i]
            
            if isinstance(element, NavigableString):
                i += 1
                continue
            
            if element.name == 'ol':
                # Process list items
                for li in element.find_all('li', recursive=False):
                    text = li.get_text(' ', strip=True)
                    
                    # Check if this looks like a question start
                    if self._looks_like_question_start(text):
                        # Save previous question
                        if current_question:
                            questions.append(current_question)
                        
                        question_num += 1
                        current_question = {
                            'number': question_num,
                            'text': self._clean_text(text),
                            'options': [],
                            'tables': [],
                            'images': [],
                            'raw_html': str(li)
                        }
                    elif self._looks_like_option(text):
                        if current_question:
                            opt = self._parse_option(text)
                            if opt:
                                current_question['options'].append(opt)
                    elif current_question:
                        # Append to current question text
                        current_question['text'] += ' ' + self._clean_text(text)
            
            elif element.name == 'table':
                if current_question:
                    table_html = str(element)
                    current_question['tables'].append({
                        'id': str(uuid.uuid4())[:8],
                        'html': table_html,
                        'is_complex': self._is_complex_table(element)
                    })
            
            elif element.name == 'p':
                text = element.get_text(' ', strip=True)
                
                if self._looks_like_question_start(text):
                    if current_question:
                        questions.append(current_question)
                    
                    question_num += 1
                    current_question = {
                        'number': question_num,
                        'text': self._clean_text(text),
                        'options': [],
                        'tables': [],
                        'images': []
                    }
                elif current_question:
                    # Check for options in paragraph
                    if self._looks_like_option(text):
                        opt = self._parse_option(text)
                        if opt:
                            current_question['options'].append(opt)
                    else:
                        # Check for inline options (A. x B. y C. z D. w pattern)
                        inline_opts = self._extract_inline_options(text)
                        if inline_opts:
                            current_question['options'].extend(inline_opts)
                        else:
                            current_question['text'] += ' ' + self._clean_text(text)
            
            i += 1
        
        # Don't forget last question
        if current_question:
            questions.append(current_question)
        
        return questions
    
    def _extract_from_paragraphs(
        self, 
        soup: BeautifulSoup, 
        images: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract questions from paragraph-based content."""
        questions = []
        current_question = None
        question_num = 0
        
        for element in soup.find_all(['p', 'table', 'ol', 'ul']):
            if element.name == 'table':
                if current_question:
                    current_question['tables'].append({
                        'id': str(uuid.uuid4())[:8],
                        'html': str(element),
                        'is_complex': self._is_complex_table(element)
                    })
                continue
            
            text = element.get_text(' ', strip=True)
            
            # Check for question number pattern
            q_match = re.match(r'^\s*(?:Q\.?\s*)?(\d{1,3})[\.\)]\s*(.+)', text)
            
            if q_match:
                if current_question:
                    questions.append(current_question)
                
                question_num = int(q_match.group(1))
                current_question = {
                    'number': question_num,
                    'text': self._clean_text(q_match.group(2)),
                    'options': [],
                    'tables': [],
                    'images': []
                }
            elif current_question:
                if self._looks_like_option(text):
                    opt = self._parse_option(text)
                    if opt:
                        current_question['options'].append(opt)
                else:
                    current_question['text'] += ' ' + text
        
        if current_question:
            questions.append(current_question)
        
        return questions
    
    def _looks_like_question_start(self, text: str) -> bool:
        """Check if text looks like the start of a question."""
        text = text.strip()
        
        # Shouldn't be too short
        if len(text) < 10:
            return False
        
        # Check for question patterns
        patterns = [
            r'^(?:Q\.?\s*)?\d{1,3}[\.\)]\s*.+',
            r'^(?:Question|प्रश्न)\s*\d+',
            r'^.+\?$',  # Ends with question mark
            r'^.+(?:consider|which|what|who|when|where|how|why|select|choose)',
        ]
        
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # Check for common question indicators
        indicators = [
            'consider the following',
            'निम्नलिखित',
            'which of the',
            'select the correct',
            'choose the',
            'with reference to',
            'के संदर्भ में',
        ]
        
        text_lower = text.lower()
        return any(ind in text_lower for ind in indicators)
    
    def _looks_like_option(self, text: str) -> bool:
        """Check if text looks like an option."""
        text = text.strip()
        return bool(re.match(r'^\s*[\(\[]?\s*[A-Da-d1-4]\s*[\)\]\.]\s*.+', text))
    
    def _parse_option(self, text: str) -> Optional[Dict[str, str]]:
        """Parse option text into label and content."""
        match = re.match(r'^\s*[\(\[]?\s*([A-Da-d1-4])\s*[\)\]\.]\s*(.+)$', text.strip())
        if match:
            label = match.group(1).upper()
            if label.isdigit():
                label = chr(ord('A') + int(label) - 1)
            return {
                'label': label,
                'text': match.group(2).strip()
            }
        return None
    
    def _extract_inline_options(self, text: str) -> List[Dict[str, str]]:
        """Extract options that are inline (A. x B. y C. z D. w)."""
        options = []
        # Pattern to match inline options
        pattern = r'[\(\[]?\s*([A-Da-d])\s*[\)\]\.]\s*([^A-D\(\[\]\)]+?)(?=\s*[\(\[]?\s*[A-Da-d]\s*[\)\]\.]\s*|$)'
        
        matches = re.findall(pattern, text, re.IGNORECASE)
        for label, content in matches:
            options.append({
                'label': label.upper(),
                'text': content.strip()
            })
        
        return options
    
    def _clean_text(self, text: str) -> str:
        """Clean up text by removing extra whitespace."""
        return re.sub(r'\s+', ' ', text).strip()
    
    def _is_complex_table(self, table) -> bool:
        """Check if table is complex."""
        if table.find(attrs={'colspan': True}) or table.find(attrs={'rowspan': True}):
            return True
        if len(table.find_all('table')) > 0:
            return True
        rows = table.find_all('tr')
        if rows:
            cell_counts = [len(row.find_all(['td', 'th'])) for row in rows]
            if len(set(cell_counts)) > 1:
                return True
        return False
