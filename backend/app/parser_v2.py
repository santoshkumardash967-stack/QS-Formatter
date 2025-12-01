"""
Improved DOCX Parser - Better question/option detection for messy documents.
"""
import re
import uuid
import os
from typing import List, Tuple, Optional, Dict, Any
from io import BytesIO
import mammoth
from bs4 import BeautifulSoup, NavigableString


class ImprovedQuestionExtractor:
    """
    Extracts questions from DOCX files converted to HTML.
    Handles the specific format of the test files with ordered lists.
    """
    
    def __init__(self, upload_dir: str = "/tmp/qs-formatter"):
        self.upload_dir = upload_dir
    
    def parse_docx_to_html(self, file_path: str, job_id: str) -> Tuple[str, List[Dict]]:
        """Parse DOCX to HTML and extract images."""
        images = []
        image_dir = os.path.join(self.upload_dir, job_id, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        def handle_image(image):
            with image.open() as img_stream:
                img_data = img_stream.read()
                img_id = str(uuid.uuid4())[:8]
                ext = "png"
                if "jpeg" in image.content_type or "jpg" in image.content_type:
                    ext = "jpg"
                
                filename = f"img_{img_id}.{ext}"
                filepath = os.path.join(image_dir, filename)
                
                with open(filepath, "wb") as f:
                    f.write(img_data)
                
                images.append({
                    "id": img_id,
                    "filename": filename,
                    "path": filepath,
                    "content_type": image.content_type
                })
                
                return {"src": f"__IMAGE__{img_id}__"}
        
        with open(file_path, "rb") as f:
            result = mammoth.convert_to_html(
                f,
                convert_image=mammoth.images.img_element(handle_image)
            )
        
        return result.value, images
    
    def extract_questions(self, html: str, images: List[Dict] = None) -> List[Dict]:
        """
        Extract questions from HTML.
        The input format has questions and options in <ol><li> format.
        """
        if images is None:
            images = []
        
        soup = BeautifulSoup(html, 'lxml')
        questions = []
        
        # Get all elements in order
        elements = []
        for elem in soup.body.children if soup.body else soup.children:
            if isinstance(elem, NavigableString):
                text = str(elem).strip()
                if text:
                    elements.append({'type': 'text', 'content': text, 'html': text})
            elif elem.name == 'ol':
                # Flatten list items
                for li in elem.find_all('li', recursive=False):
                    text = li.get_text(' ', strip=True)
                    elements.append({'type': 'li', 'content': text, 'html': str(li)})
            elif elem.name == 'ul':
                for li in elem.find_all('li', recursive=False):
                    text = li.get_text(' ', strip=True)
                    elements.append({'type': 'li', 'content': text, 'html': str(li)})
            elif elem.name == 'table':
                elements.append({
                    'type': 'table',
                    'content': elem.get_text(' ', strip=True),
                    'html': str(elem)
                })
            elif elem.name == 'p':
                text = elem.get_text(' ', strip=True)
                if text:
                    elements.append({'type': 'p', 'content': text, 'html': str(elem)})
            elif elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = elem.get_text(' ', strip=True)
                if text:
                    elements.append({'type': 'heading', 'content': text, 'html': str(elem)})
        
        # Now process elements to identify questions
        current_question = None
        question_num = 0
        
        i = 0
        while i < len(elements):
            elem = elements[i]
            text = elem['content']
            elem_type = elem['type']
            
            # Check if this looks like a question start
            is_question_start = self._is_question_start(text)
            
            if is_question_start and elem_type == 'li':
                # Save previous question
                if current_question is not None:
                    questions.append(current_question)
                
                question_num += 1
                
                # Extract question text (remove numbering if present)
                q_text = self._clean_question_text(text)
                
                current_question = {
                    'number': question_num,
                    'text': q_text,
                    'options': [],
                    'tables': [],
                    'images': []
                }
                
                # Look ahead for options and content
                i += 1
                while i < len(elements):
                    next_elem = elements[i]
                    next_text = next_elem['content']
                    next_type = next_elem['type']
                    
                    # Check if this is a new question
                    if next_type == 'li' and self._is_question_start(next_text):
                        break
                    
                    # Handle table
                    if next_type == 'table':
                        current_question['tables'].append({
                            'id': str(uuid.uuid4())[:8],
                            'html': next_elem['html'],
                            'is_complex': self._is_complex_table(next_elem['html'])
                        })
                        i += 1
                        continue
                    
                    # Check if this is an option
                    if next_type == 'li' and self._is_option(next_text):
                        opt = self._parse_option(next_text)
                        if opt:
                            current_question['options'].append(opt)
                        i += 1
                        continue
                    
                    # Check for paragraph that might be part of question or have options
                    if next_type == 'p':
                        # Check for inline options
                        inline_opts = self._extract_inline_options(next_text)
                        if inline_opts:
                            current_question['options'].extend(inline_opts)
                        elif self._is_option(next_text):
                            opt = self._parse_option(next_text)
                            if opt:
                                current_question['options'].append(opt)
                        else:
                            # Append to question text
                            current_question['text'] += ' ' + next_text
                        i += 1
                        continue
                    
                    i += 1
                
                continue
            
            # Handle paragraph-based questions (Q1. format)
            if elem_type == 'p' and self._is_numbered_question(text):
                if current_question is not None:
                    questions.append(current_question)
                
                q_match = re.match(r'^\s*Q\.?\s*(\d+)[\.\)]\s*(.+)', text, re.IGNORECASE)
                if q_match:
                    question_num = int(q_match.group(1))
                    q_text = q_match.group(2)
                else:
                    question_num += 1
                    q_text = self._clean_question_text(text)
                
                current_question = {
                    'number': question_num,
                    'text': q_text,
                    'options': [],
                    'tables': [],
                    'images': []
                }
            
            i += 1
        
        # Don't forget the last question
        if current_question is not None:
            questions.append(current_question)
        
        return questions
    
    def _is_question_start(self, text: str) -> bool:
        """
        Determine if text looks like the start of a question.
        Questions typically have substantial content and aren't just options.
        """
        text = text.strip()
        
        # Too short to be a question
        if len(text) < 15:
            return False
        
        # If it starts with option pattern, it's not a question
        if re.match(r'^\s*[\(\[]?\s*[A-Da-d1-4]\s*[\)\]\.]\s*', text):
            return False
        
        # If it looks like just an option letter with short text
        if re.match(r'^\s*[A-Da-d]\s*[\.\)]\s*.{1,30}$', text):
            return False
        
        # Check for question indicators
        question_indicators = [
            r'consider the following',
            r'which of the',
            r'select the correct',
            r'choose the',
            r'with reference to',
            r'given below',
            r'statements?',
            r'\?$',  # Ends with question mark
            r'निम्नलिखित',
            r'के संदर्भ में',
            r'विचार कीजिए',
            r'कथन',
            r'कौन',
        ]
        
        text_lower = text.lower()
        for indicator in question_indicators:
            if re.search(indicator, text_lower):
                return True
        
        # If it's long enough and contains certain patterns
        if len(text) > 50:
            # Check if it contains numbered statements
            if re.search(r'[12345]\s+\w', text):
                return True
        
        # Default: if it's reasonably long and not an option, consider it a question
        if len(text) > 40 and not self._is_option(text):
            return True
        
        return False
    
    def _is_option(self, text: str) -> bool:
        """Check if text is an option."""
        text = text.strip()
        
        # Standard option patterns
        patterns = [
            r'^\s*[\(\[]?\s*[A-Da-d]\s*[\)\]\.]\s*.+',
            r'^\s*[\(\[]?\s*[1-4]\s*[\)\]\.]\s*.+',
            r'^\s*केवल\s+[0-9]',  # Hindi "only X"
            r'^\s*\d+\s+(?:और|and)\s+\d+',  # "X and Y"
        ]
        
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_numbered_question(self, text: str) -> bool:
        """Check if text is a Q1. style question."""
        return bool(re.match(r'^\s*Q\.?\s*\d+[\.\)]\s*.+', text, re.IGNORECASE))
    
    def _clean_question_text(self, text: str) -> str:
        """Clean up question text."""
        # Remove numbering patterns
        text = re.sub(r'^\s*Q\.?\s*\d+[\.\)]\s*', '', text)
        text = re.sub(r'^\s*\d+[\.\)]\s*', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _parse_option(self, text: str) -> Optional[Dict]:
        """Parse option text into label and content."""
        text = text.strip()
        
        # Try various patterns
        patterns = [
            r'^\s*[\(\[]?\s*([A-Da-d])\s*[\)\]\.]\s*(.+)$',
            r'^\s*[\(\[]?\s*([1-4])\s*[\)\]\.]\s*(.+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text, re.DOTALL)
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
    
    def _extract_inline_options(self, text: str) -> List[Dict]:
        """Extract inline options like 'A. x B. y C. z D. w'."""
        options = []
        
        # Pattern for inline options
        pattern = r'[\(\[]?\s*([A-Da-d])\s*[\)\]\.]\s*([^A-Da-d\(\[\]\)]+?)(?=\s*[\(\[]?\s*[A-Da-d]\s*[\)\]\.]\s*|$)'
        
        matches = re.findall(pattern, text, re.IGNORECASE)
        for label, content in matches:
            content = content.strip()
            if content:
                options.append({
                    'label': label.upper(),
                    'text': content
                })
        
        return options if len(options) >= 2 else []
    
    def _is_complex_table(self, html: str) -> bool:
        """Check if table is complex."""
        soup = BeautifulSoup(html, 'lxml')
        table = soup.find('table')
        
        if not table:
            return False
        
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


def parse_document(file_path: str, job_id: str, upload_dir: str = "/tmp/qs-formatter") -> List[Dict]:
    """
    Main function to parse a DOCX document.
    """
    extractor = ImprovedQuestionExtractor(upload_dir)
    html, images = extractor.parse_docx_to_html(file_path, job_id)
    questions = extractor.extract_questions(html, images)
    
    return questions
