"""
Final robust DOCX Parser for QS-Formatter.
Handles the specific document format where questions, options, and tables are interleaved.
"""
import re
import uuid
import os
from typing import List, Dict, Any, Optional, Tuple
import mammoth
from bs4 import BeautifulSoup, NavigableString, Tag


class RobustDocumentParser:
    """
    Robust parser for bilingual MCQ DOCX documents.
    """
    
    def __init__(self, upload_dir: str = "/tmp/qs-formatter"):
        self.upload_dir = upload_dir
    
    def parse_file(self, file_path: str, job_id: str) -> List[Dict[str, Any]]:
        """Parse a DOCX file and extract questions."""
        html, images = self._docx_to_html(file_path, job_id)
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
        """Extract questions from HTML."""
        soup = BeautifulSoup(html, 'lxml')
        body = soup.body if soup.body else soup
        
        # Convert to element stream
        elements = self._get_elements(body)
        
        # Process elements to extract questions
        questions = self._process_elements(elements)
        
        return questions
    
    def _get_elements(self, body) -> List[Dict]:
        """Convert HTML body to a list of typed elements."""
        elements = []
        
        for elem in body.children:
            if isinstance(elem, NavigableString):
                text = str(elem).strip()
                if text:
                    elements.append({'type': 'text', 'content': text, 'html': text})
                continue
            
            if not hasattr(elem, 'name') or not elem.name:
                continue
            
            if elem.name == 'ol' or elem.name == 'ul':
                lis = elem.find_all('li', recursive=False)
                li_texts = [li.get_text(' ', strip=True) for li in lis]
                elements.append({
                    'type': 'list',
                    'items': li_texts,
                    'count': len(lis),
                    'html': str(elem)
                })
            elif elem.name == 'table':
                elements.append({
                    'type': 'table',
                    'content': elem.get_text(' ', strip=True),
                    'html': str(elem),
                    'is_complex': self._is_complex_table(elem)
                })
            elif elem.name == 'p':
                text = elem.get_text(' ', strip=True)
                if text:
                    elements.append({
                        'type': 'paragraph',
                        'content': text,
                        'html': str(elem)
                    })
            elif elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = elem.get_text(' ', strip=True)
                if text:
                    elements.append({
                        'type': 'heading',
                        'content': text,
                        'html': str(elem)
                    })
        
        return elements
    
    def _process_elements(self, elements: List[Dict]) -> List[Dict]:
        """Process elements to extract questions."""
        questions = []
        current_q = None
        q_num = 0
        
        i = 0
        while i < len(elements):
            elem = elements[i]
            elem_type = elem['type']
            
            # Check for question start patterns
            if elem_type == 'list' and elem['count'] == 1:
                # Single-item list is usually a question start
                text = elem['items'][0]
                if self._looks_like_question(text):
                    # Save previous question
                    if current_q:
                        questions.append(self._finalize_question(current_q))
                    
                    q_num += 1
                    current_q = {
                        'number': q_num,
                        'text': text,
                        'options': [],
                        'tables': [],
                        'images': []
                    }
                    i += 1
                    continue
            
            # Table - add to current question
            if elem_type == 'table' and current_q:
                current_q['tables'].append({
                    'id': str(uuid.uuid4())[:8],
                    'html': elem['html'],
                    'is_complex': elem.get('is_complex', False)
                })
                i += 1
                continue
            
            # Paragraph - could be continuation, "which of" question, or numbered statement
            if elem_type == 'paragraph':
                text = elem['content']
                
                # Check if it's a "which of the following" type question part
                if self._is_question_prompt(text) and current_q:
                    current_q['text'] += ' ' + text
                # Numbered statement (1, 2, 3...)
                elif self._is_numbered_statement(text) and current_q:
                    current_q['text'] += ' ' + text
                # Assertion/Reason pattern
                elif self._is_assertion_reason(text) and current_q:
                    current_q['text'] += ' ' + text
                # Standalone question with Q prefix
                elif self._is_q_prefixed(text):
                    if current_q:
                        questions.append(self._finalize_question(current_q))
                    q_num += 1
                    current_q = {
                        'number': q_num,
                        'text': self._clean_q_prefix(text),
                        'options': [],
                        'tables': [],
                        'images': []
                    }
                i += 1
                continue
            
            # Multi-item list - these are options (and sometimes next question mixed in)
            if elem_type == 'list' and elem['count'] > 1 and current_q:
                items = elem['items']
                
                for item_text in items:
                    # Check if this item is actually a new question
                    if self._looks_like_question(item_text) and len(item_text) > 50:
                        # Save current question first
                        questions.append(self._finalize_question(current_q))
                        q_num += 1
                        current_q = {
                            'number': q_num,
                            'text': item_text,
                            'options': [],
                            'tables': [],
                            'images': []
                        }
                    else:
                        # It's an option
                        opt = self._parse_option(item_text)
                        if opt:
                            current_q['options'].append(opt)
                
                i += 1
                continue
            
            i += 1
        
        # Don't forget last question
        if current_q:
            questions.append(self._finalize_question(current_q))
        
        return questions
    
    def _looks_like_question(self, text: str) -> bool:
        """Check if text looks like a question."""
        text = text.strip()
        
        if len(text) < 15:
            return False
        
        # Question indicators
        patterns = [
            r'consider\s+the\s+following',
            r'with\s+reference\s+to',
            r'which\s+of\s+the\s+following',
            r'select\s+the\s+correct',
            r'choose\s+the',
            r'match\s+the\s+following',
            r'given\s+below',
            r'following\s+pairs',
            r'following\s+statements',
            r'\?$',
            # Hindi
            r'निम्नलिखित',
            r'के\s+संदर्भ\s+में',
            r'विचार\s+कीजिए',
            r'सही.*चुनिए',
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        
        return False
    
    def _is_question_prompt(self, text: str) -> bool:
        """Check if text is a question prompt like 'Which of the above...'"""
        prompts = [
            r'^which\s+of\s+the',
            r'^select\s+the\s+correct',
            r'^choose\s+the\s+correct',
            r'^the\s+correct\s+',
            r'^ऊपर\s+दिए',
            r'^उपर्युक्त',
            r'^सही\s+उत्तर',
        ]
        
        text_lower = text.lower().strip()
        for pattern in prompts:
            if re.match(pattern, text_lower):
                return True
        
        return False
    
    def _is_numbered_statement(self, text: str) -> bool:
        """Check if text is a numbered statement like '1 statement...'"""
        return bool(re.match(r'^\s*[1-9]\s+\w', text))
    
    def _is_assertion_reason(self, text: str) -> bool:
        """Check if text is Assertion/Reason pattern."""
        return bool(re.match(r'^\s*(Assertion|Reason|अभिकथन|कारण)', text, re.IGNORECASE))
    
    def _is_q_prefixed(self, text: str) -> bool:
        """Check if text starts with Q1. or similar."""
        return bool(re.match(r'^\s*Q\.?\s*\d+[\.\):]', text, re.IGNORECASE))
    
    def _clean_q_prefix(self, text: str) -> str:
        """Remove Q1. prefix from text."""
        return re.sub(r'^\s*Q\.?\s*\d+[\.\):]\s*', '', text).strip()
    
    def _parse_option(self, text: str) -> Optional[Dict]:
        """Parse option text."""
        text = text.strip()
        
        # Standard option patterns
        patterns = [
            r'^\s*[\(\[]?\s*([A-Da-d])\s*[\)\]\.:\-]\s*(.+)$',
            r'^\s*([1-4])\s*[\)\]\.:\-]\s*(.+)$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, text, re.DOTALL)
            if match:
                label = match.group(1).upper()
                if label.isdigit():
                    label = chr(ord('A') + int(label) - 1)
                return {
                    'label': label,
                    'text': match.group(2).strip()
                }
        
        # Handle text that looks like an option but no clear prefix
        if self._looks_like_option_content(text):
            return {
                'label': '?',
                'text': text
            }
        
        return None
    
    def _looks_like_option_content(self, text: str) -> bool:
        """Check if text content looks like an option."""
        patterns = [
            r'^only\s+[0-9]',
            r'^[0-9]+\s*(?:and|&)\s*[0-9]+',
            r'^(?:Both|Neither|All|None)',
            r'^(?:केवल|दोनों|न\s+तो)',
            r'^[A-D]-[0-9]',
        ]
        
        for pattern in patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _finalize_question(self, q: Dict) -> Dict:
        """Finalize a question - normalize options, clean up text."""
        # Normalize options
        q['options'] = self._normalize_options(q['options'])
        
        # Clean up question text
        q['text'] = re.sub(r'\s+', ' ', q['text']).strip()
        
        return q
    
    def _normalize_options(self, options: List[Dict]) -> List[Dict]:
        """Normalize options to have proper labels."""
        if not options:
            return []
        
        # Separate labeled and unlabeled
        labeled = [o for o in options if o.get('label') != '?']
        unlabeled = [o for o in options if o.get('label') == '?']
        
        # Assign labels to unlabeled
        used = set(o['label'] for o in labeled)
        available = [l for l in ['A', 'B', 'C', 'D', 'E', 'F'] if l not in used]
        
        for i, opt in enumerate(unlabeled):
            if i < len(available):
                opt['label'] = available[i]
        
        all_opts = labeled + unlabeled
        all_opts.sort(key=lambda x: x.get('label', 'Z'))
        
        return all_opts[:6]
    
    def _is_complex_table(self, table: Tag) -> bool:
        """Check if table is complex."""
        if table.find(attrs={'colspan': True}) or table.find(attrs={'rowspan': True}):
            return True
        if table.find_all('table'):
            return True
        rows = table.find_all('tr')
        if rows:
            counts = [len(r.find_all(['td', 'th'])) for r in rows]
            if len(set(counts)) > 1:
                return True
        return False


# Convenience function
def parse_document(file_path: str, job_id: str, upload_dir: str = "/tmp/qs-formatter") -> List[Dict]:
    """Parse a DOCX document and return list of questions."""
    parser = RobustDocumentParser(upload_dir)
    return parser.parse_file(file_path, job_id)
