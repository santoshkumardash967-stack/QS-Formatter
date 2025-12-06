"""
Adaptive DOCX Parser for QS-Formatter.

This parser intelligently detects question boundaries instead of assuming
a fixed number of items per question. It handles:
- Variable number of options (4-8)
- Image-based options
- Tables within questions
- Mixed content types
"""
import os
import re
import uuid
import base64
from typing import Optional, List, Dict, Any, Tuple
from bs4 import BeautifulSoup, Tag
import mammoth


def is_likely_question(text: str, has_img: bool = False) -> bool:
    """
    Determine if a text item is likely a question rather than an option.
    
    Questions typically:
    - Are longer than options
    - End with ? or :
    - Contain question keywords
    - Have fill-in-the-blank patterns
    - Don't start with single short answers
    """
    text = text.strip()
    
    if not text and not has_img:
        return False
    
    # If it's just an image with no text, likely an option
    if has_img and len(text) < 10:
        return False
    
    text_lower = text.lower()
    
    # Check for fill-in-the-blank patterns first
    has_blank = '_____' in text or '______' in text or '___' in text
    
    # Fill-in-the-blank patterns are questions regardless of length
    if has_blank and len(text) > 20:
        return True
    
    # Short questions that are clearly questions (specific patterns)
    short_question_patterns = [
        r'^zip files are',
        r'^simplify\s*:',
        r'^calculate\s*:',
        r'^solve\s*:',
        r'^evaluate\s*:',
        r'^find\s+the\s+value',
        r'^what\s+is\s+',
        r'^\.+\s+are\s+',  # "... are" patterns like "Zip files are"
    ]
    
    for pattern in short_question_patterns:
        if re.match(pattern, text_lower):
            return True
    
    # Very short text is likely an option
    if len(text) < 15 and not has_blank:
        return False
    
    # Options that START with answer-like words are likely options
    option_start_patterns = [
        r'^only\s+\d',  # "Only 1", "Only 2"
        r'^\d+\s+and\s+\d+',  # "1 and 2"
        r'^all\s+of\s+the\s+above',
        r'^none\s+of\s+the',
        r'^both\s+\(',
        r'^\(\w\)\s+and\s+\(\w\)',  # (A) and (B)
        r'^[A-D]\s+and\s+[A-D]',
        r'^always[,\s]',  # "Always, ..." is an option
        r'^never[,\s]',   # "Never, ..." is an option
        r'^sometimes[,\s]',
        r'^when\s+sending',  # "When sending a message..." as option
        r'^to\s+[a-z]+\s+',  # "To improve..." as option
        r'^by\s+[a-z]+',  # "By using..." as option
    ]
    
    for pattern in option_start_patterns:
        if re.match(pattern, text_lower):
            return False
    
    # Question indicators (strong signals)
    question_keywords = [
        'which of the following', 'what is the', 'who is the', 'who was the',
        'where is', 'when was', 'when did', 'why is', 'how many', 'how much',
        'consider the following', 'select the', 'choose the', 'identify the',
        'find the', 'match the', 'arrange the',
        'with reference to', 'with respect to', 'regarding the',
        'in the context of', 'in relation to',
        'statement', 'assertion', 'reason',
        'following is not', 'following is true', 'following is false',
        'correct statement', 'incorrect statement',
        'full form of', 'stands for', 'abbreviation of',
        'rank of', 'position of', 'capital of',
        # Hindi keywords
        'निम्नलिखित', 'कौन सा', 'क्या है', 'किसका', 'कहाँ है', 'कब हुआ',
    ]
    
    # Check for question indicators
    has_question_phrase = any(kw in text_lower for kw in question_keywords)
    ends_with_question = text.rstrip().endswith('?')
    ends_with_colon = text.rstrip().endswith(':')
    is_long = len(text) > 60
    
    # Strong indicators
    if has_question_phrase:
        return True
    
    if ends_with_question:
        return True
    
    # Medium-length text ending with colon
    if ends_with_colon and len(text) > 25:
        return True
    
    # Very long text is likely a question (but not if starts with option patterns)
    if len(text) > 100:
        return True
    
    # Contains blank to fill - likely question
    if has_blank:
        return True
    
    return False


def is_likely_option(text: str, has_img: bool = False) -> bool:
    """
    Determine if a text item is likely an option.
    """
    text = text.strip()
    
    # Image-only items are options
    if has_img and len(text) < 10:
        return True
    
    # Short text is likely an option
    if len(text) < 50:
        return True
    
    # Very short is definitely an option
    if len(text) < 20:
        return True
    
    return False


def extract_images_from_element(element: Tag, job_id: str, upload_dir: str) -> List[Dict]:
    """Extract images from an element and save them."""
    images = []
    
    for img in element.find_all('img'):
        src = img.get('src', '')
        
        if src.startswith('data:'):
            # Base64 encoded image
            try:
                # Parse data URL
                match = re.match(r'data:([^;]+);base64,(.+)', src)
                if match:
                    content_type = match.group(1)
                    data = match.group(2)
                    
                    # Determine extension
                    ext_map = {
                        'image/png': 'png',
                        'image/jpeg': 'jpg',
                        'image/gif': 'gif',
                        'image/webp': 'webp',
                    }
                    ext = ext_map.get(content_type, 'png')
                    
                    # Save image
                    img_id = str(uuid.uuid4())[:8]
                    filename = f"img_{img_id}.{ext}"
                    img_dir = os.path.join(upload_dir, job_id, "images")
                    os.makedirs(img_dir, exist_ok=True)
                    
                    img_path = os.path.join(img_dir, filename)
                    with open(img_path, 'wb') as f:
                        f.write(base64.b64decode(data))
                    
                    images.append({
                        'id': img_id,
                        'filename': filename,
                        'path': img_path,
                        'content_type': content_type,
                        'data_url': src[:100] + '...'  # Truncated for reference
                    })
            except Exception as e:
                print(f"Error extracting image: {e}")
    
    return images


def parse_docx_adaptive(file_path: str, job_id: str, upload_dir: str) -> List[Dict]:
    """
    Parse a DOCX file using adaptive question detection.
    
    Instead of assuming 5 items per question, this parser:
    1. Identifies question boundaries by content analysis
    2. Collects all options until the next question
    3. Handles variable numbers of options
    4. Extracts embedded images
    """
    with open(file_path, "rb") as f:
        result = mammoth.convert_to_html(f)
        html = result.value
    
    soup = BeautifulSoup(html, 'html.parser')
    all_lis = soup.find_all('li')
    
    questions = []
    current_question = None
    option_labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    
    for i, li in enumerate(all_lis):
        text = li.get_text(strip=True)
        has_img = len(li.find_all('img')) > 0
        images = extract_images_from_element(li, job_id, upload_dir)
        
        # Determine if this is a question or option
        if is_likely_question(text, has_img):
            # Save previous question if exists
            if current_question:
                questions.append(current_question)
            
            # Detect question type
            question_type = 'single'
            text_lower = text.lower()
            if 'assertion' in text_lower or 'reason' in text_lower:
                question_type = 'assertion-reason'
            elif 'match' in text_lower:
                question_type = 'matching'
            elif any(x in text_lower for x in ['statement', 'कथन']):
                question_type = 'statement-based'
            elif 'how many' in text_lower or 'कितने' in text:
                question_type = 'how-many'
            
            # Extract tables
            tables = []
            for table in li.find_all('table'):
                tables.append({
                    'id': str(uuid.uuid4())[:8],
                    'html': str(table),
                    'rows': len(table.find_all('tr')),
                    'cols': len(table.find('tr').find_all(['td', 'th'])) if table.find('tr') else 0
                })
            
            current_question = {
                'id': len(questions) + 1,
                'english_text': text,
                'hindi_text': '',
                'question_type': question_type,
                'options': [],
                'tables': tables,
                'images': images,
                'answer': '',
                'solution_english': '',
                'solution_hindi': '',
                'confidence': 1.0,
                'flags': []
            }
        else:
            # This is an option
            if current_question:
                opt_index = len(current_question['options'])
                if opt_index < len(option_labels):
                    label = option_labels[opt_index]
                else:
                    label = f"O{opt_index + 1}"  # Fallback for many options
                
                current_question['options'].append({
                    'label': label,
                    'english_text': text,
                    'hindi_text': '',
                    'is_correct': False,
                    'images': images
                })
    
    # Don't forget the last question
    if current_question:
        questions.append(current_question)
    
    # Post-process: flag questions with unusual option counts
    for q in questions:
        num_opts = len(q['options'])
        if num_opts > 4:
            q['flags'].append('EXTRA_OPTIONS')
            q['confidence'] = 0.8
        elif num_opts < 4:
            q['flags'].append('MISSING_OPTIONS')
            q['confidence'] = 0.7
        elif num_opts == 0:
            q['flags'].append('NO_OPTIONS')
            q['confidence'] = 0.5
        
        # Flag if options contain images
        if any(opt.get('images') for opt in q['options']):
            q['flags'].append('IMAGE_OPTIONS')
    
    return questions


def parse_document(file_path: str, job_id: str, upload_dir: str) -> List[Dict]:
    """Main entry point for parsing."""
    return parse_docx_adaptive(file_path, job_id, upload_dir)


# Test
if __name__ == "__main__":
    import json
    
    test_file = "/workspaces/QS-Formatter/new-files/1 MOCK LATEST ENGLISH.docx"
    
    if os.path.exists(test_file):
        print("Parsing new English file with adaptive parser...")
        questions = parse_docx_adaptive(test_file, "test", "/tmp/qs-test")
        
        print(f"\nExtracted {len(questions)} questions")
        
        # Stats
        opt_counts = {}
        flagged = []
        for q in questions:
            n = len(q['options'])
            opt_counts[n] = opt_counts.get(n, 0) + 1
            if q['flags']:
                flagged.append((q['id'], q['flags']))
        
        print(f"\nOption count distribution:")
        for n, count in sorted(opt_counts.items()):
            print(f"  {n} options: {count} questions")
        
        print(f"\nFlagged questions: {len(flagged)}")
        for qid, flags in flagged[:10]:
            print(f"  Q{qid}: {flags}")
        
        # Show a few questions
        print("\n--- Sample questions ---")
        for q in questions[60:65]:
            print(f"\nQ{q['id']}: {q['english_text'][:70]}...")
            print(f"  Options: {len(q['options'])}, Flags: {q['flags']}")
            for opt in q['options'][:6]:
                opt_text = opt['english_text'][:40] if opt['english_text'] else "[IMAGE]"
                print(f"    {opt['label']}) {opt_text}")
    else:
        print(f"Test file not found: {test_file}")
