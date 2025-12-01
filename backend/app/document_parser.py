"""
Final DOCX Parser - Handles the specific format of the test documents.
"""
import re
import uuid
import os
from typing import List, Dict, Any, Optional, Tuple
import mammoth
from bs4 import BeautifulSoup, NavigableString, Tag


class DocumentParser:
    """
    Parses DOCX files to extract bilingual MCQ questions.
    Handles messy formats where questions and options are mixed in lists.
    """
    
    def __init__(self, upload_dir: str = "/tmp/qs-formatter"):
        self.upload_dir = upload_dir
    
    def parse_file(self, file_path: str, job_id: str) -> List[Dict[str, Any]]:
        """
        Parse a DOCX file and extract questions.
        """
        # Convert DOCX to HTML
        html, images = self._docx_to_html(file_path, job_id)
        
        # Parse HTML and extract questions
        questions = self._extract_questions(html, images)
        
        return questions
    
    def _docx_to_html(self, file_path: str, job_id: str) -> Tuple[str, List[Dict]]:
        """Convert DOCX to HTML with image extraction."""
        images = []
        image_dir = os.path.join(self.upload_dir, job_id, "images")
        os.makedirs(image_dir, exist_ok=True)
        
        def handle_image(image):
            with image.open() as img_stream:
                img_data = img_stream.read()
                img_id = str(uuid.uuid4())[:8]
                ext = "png" if "png" in image.content_type else "jpg"
                
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
    
    def _extract_questions(self, html: str, images: List[Dict]) -> List[Dict]:
        """
        Extract questions from HTML.
        Strategy:
        1. Flatten all content into a linear list of text blocks
        2. Identify question-start patterns
        3. Group content between question starts
        4. Extract options from each group
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Flatten content
        blocks = self._flatten_content(soup)
        
        # Group into questions
        questions = self._group_into_questions(blocks)
        
        return questions
    
    def _flatten_content(self, soup: BeautifulSoup) -> List[Dict]:
        """Flatten HTML into linear blocks of text/tables."""
        blocks = []
        
        body = soup.body if soup.body else soup
        
        for elem in body.children:
            if isinstance(elem, NavigableString):
                text = str(elem).strip()
                if text:
                    blocks.append({'type': 'text', 'content': text})
            elif elem.name == 'table':
                blocks.append({
                    'type': 'table',
                    'content': elem.get_text(' ', strip=True),
                    'html': str(elem),
                    'is_complex': self._is_complex_table(elem)
                })
            elif elem.name in ['ol', 'ul']:
                # Each list item becomes a separate block
                for li in elem.find_all('li', recursive=False):
                    text = li.get_text(' ', strip=True)
                    if text:
                        blocks.append({'type': 'list_item', 'content': text})
            elif elem.name == 'p':
                text = elem.get_text(' ', strip=True)
                if text:
                    blocks.append({'type': 'paragraph', 'content': text})
            elif elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = elem.get_text(' ', strip=True)
                if text:
                    blocks.append({'type': 'heading', 'content': text})
        
        return blocks
    
    def _group_into_questions(self, blocks: List[Dict]) -> List[Dict]:
        """Group blocks into questions."""
        questions = []
        current_q = None
        q_num = 0
        
        i = 0
        while i < len(blocks):
            block = blocks[i]
            text = block['content']
            block_type = block['type']
            
            # Check if this starts a new question
            if self._is_question_start(text, block_type):
                # Save current question
                if current_q:
                    current_q['options'] = self._normalize_options(current_q['options'])
                    questions.append(current_q)
                
                q_num += 1
                q_text = self._clean_question_text(text)
                
                current_q = {
                    'number': q_num,
                    'text': q_text,
                    'options': [],
                    'tables': [],
                    'images': []
                }
                
                # Look ahead to collect question content
                i += 1
                while i < len(blocks):
                    next_block = blocks[i]
                    next_text = next_block['content']
                    next_type = next_block['type']
                    
                    # If next block is a new question, stop
                    if self._is_question_start(next_text, next_type):
                        break
                    
                    # Handle table
                    if next_type == 'table':
                        current_q['tables'].append({
                            'id': str(uuid.uuid4())[:8],
                            'html': next_block.get('html', ''),
                            'is_complex': next_block.get('is_complex', False)
                        })
                        i += 1
                        continue
                    
                    # Check if it's an option
                    if self._is_option_text(next_text):
                        opt = self._parse_option(next_text)
                        if opt:
                            current_q['options'].append(opt)
                    else:
                        # Append to question text (might be continuation or statement)
                        if self._is_continuation_text(next_text):
                            current_q['text'] += ' ' + next_text
                    
                    i += 1
                
                continue
            
            i += 1
        
        # Don't forget last question
        if current_q:
            current_q['options'] = self._normalize_options(current_q['options'])
            questions.append(current_q)
        
        return questions
    
    def _is_question_start(self, text: str, block_type: str) -> bool:
        """
        Determine if this text starts a new question.
        Questions typically:
        - Are longer than options
        - Contain question indicators
        - End with ? or ask for selection
        """
        text = text.strip()
        
        # Too short
        if len(text) < 20:
            return False
        
        # If it looks like a pure option, it's not a question
        if self._is_pure_option(text):
            return False
        
        # Question patterns
        question_patterns = [
            r'(?:consider|विचार).+(?:following|निम्नलिखित)',
            r'(?:which|कौन).+(?:of the|में से)',
            r'(?:select|चुनिए|चयन).+(?:correct|सही)',
            r'(?:choose|चुनिए)',
            r'(?:with reference|के संदर्भ)',
            r'(?:given below|नीचे दिए)',
            r'(?:match|मिलान)',
            r'(?:assertion|अभिकथन)',
            r'(?:statement|कथन)',
            r'\?$',  # Ends with ?
            r'(?:following pairs|निम्नलिखित युग्मों)',
            r'(?:correct(?:ly)? (?:paired|matched)|सही.*(?:जोड़|मिला))',
        ]
        
        text_lower = text.lower()
        for pattern in question_patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        
        # Long text that's not an option is likely a question
        if len(text) > 50 and not self._is_option_text(text):
            # Additional checks
            if block_type == 'list_item':
                # In list context, only if contains question indicators
                return any(ind in text_lower for ind in ['which', 'select', 'choose', 'consider', '?',
                                                          'कौन', 'चुनिए', 'विचार'])
            return True
        
        return False
    
    def _is_pure_option(self, text: str) -> bool:
        """Check if text is purely an option (not mixed with question)."""
        text = text.strip()
        
        # Standard option patterns that are short
        if len(text) < 80:
            patterns = [
                r'^\s*[\(\[]?\s*[A-Da-d]\s*[\)\]\.]\s*.+$',
                r'^\s*[1-4]\s*[\)\]\.]\s*.+$',
                r'^\s*(?:only|केवल)\s+[0-9]',
                r'^\s*[0-9]+\s*(?:and|और)\s*[0-9]+',
                r'^\s*(?:Both|Neither|दोनों|न तो)',
                r'^\s*(?:All|None|सभी|कोई नहीं)',
            ]
            for pattern in patterns:
                if re.match(pattern, text, re.IGNORECASE):
                    return True
        
        return False
    
    def _is_option_text(self, text: str) -> bool:
        """Check if text looks like an option."""
        text = text.strip()
        
        patterns = [
            r'^\s*[\(\[]?\s*[A-Da-d]\s*[\)\]\.]\s*',
            r'^\s*[1-4]\s*[\)\]\.]\s*',
            r'^(?:only|केवल)\s+[0-9]',
            r'^[0-9]+\s*(?:and|और)\s*[0-9]+\s*(?:only|केवल)?',
            r'^(?:Both|Neither|All|None)',
            r'^(?:दोनों|न तो|सभी|कोई नहीं)',
            r'^[A-D]-[0-9]',  # Match patterns like A-3, B-1
        ]
        
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _is_continuation_text(self, text: str) -> bool:
        """Check if text is a continuation of the question (like numbered statements)."""
        text = text.strip()
        
        # Numbered statements like "1 statement text" or "2. statement text"
        if re.match(r'^\s*[1-9]\s+\w', text):
            return True
        
        # Continuation patterns
        patterns = [
            r'^(?:Assertion|Reason|अभिकथन|कारण)',
            r'^(?:Statement|कथन)',
        ]
        
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _clean_question_text(self, text: str) -> str:
        """Clean up question text."""
        text = text.strip()
        # Remove leading question patterns if present
        text = re.sub(r'^\s*Q\.?\s*\d+[\.\):]?\s*', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _parse_option(self, text: str) -> Optional[Dict]:
        """Parse option text into label and content."""
        text = text.strip()
        
        # Try to extract label
        patterns = [
            r'^\s*[\(\[]?\s*([A-Da-d])\s*[\)\]\.:\-]\s*(.+)$',
            r'^\s*([1-4])\s*[\)\]\.:\-]\s*(.+)$',
            r'^([A-D])-(\d+,?\s*[A-D]-\d+.*)$',  # Match patterns like A-3, B-1...
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                label = match.group(1).upper()
                if label.isdigit():
                    label = chr(ord('A') + int(label) - 1)
                return {
                    'label': label,
                    'text': match.group(2).strip()
                }
        
        # Handle "only X and Y" style options
        only_match = re.match(r'^(?:only|केवल)\s*(.+)$', text, re.IGNORECASE)
        if only_match:
            return {
                'label': '?',  # Will be assigned later
                'text': text
            }
        
        # Handle "Both X and Y" style
        both_match = re.match(r'^(Both|Neither|All|None|दोनों|न तो|सभी|कोई नहीं)\s*(.*)$', text, re.IGNORECASE)
        if both_match:
            return {
                'label': '?',
                'text': text
            }
        
        # Numbered options without prefix
        num_match = re.match(r'^(\d+)\s*(?:and|और|,)\s*(\d+.*)', text)
        if num_match:
            return {
                'label': '?',
                'text': text
            }
        
        return None
    
    def _normalize_options(self, options: List[Dict]) -> List[Dict]:
        """Normalize options to have proper labels A, B, C, D."""
        if not options:
            return []
        
        # First, handle options that already have labels
        labeled = [o for o in options if o.get('label') != '?']
        unlabeled = [o for o in options if o.get('label') == '?']
        
        # Assign labels to unlabeled options
        used_labels = set(o['label'] for o in labeled)
        available_labels = [l for l in ['A', 'B', 'C', 'D', 'E', 'F'] if l not in used_labels]
        
        for i, opt in enumerate(unlabeled):
            if i < len(available_labels):
                opt['label'] = available_labels[i]
        
        # Combine and sort
        all_options = labeled + unlabeled
        all_options.sort(key=lambda x: x.get('label', 'Z'))
        
        # Keep only first 4-6 options
        return all_options[:6]
    
    def _is_complex_table(self, table: Tag) -> bool:
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
