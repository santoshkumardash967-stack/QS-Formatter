"""
Smart DOCX Parser for QS-Formatter.

Handles multiple document structures:
1. Main OLs (100+ items): Question + 4 options pattern
2. Small OLs (5 items): 4 options + Question (reversed) - figure-based questions
3. Mixed OLs: Multiple questions with varying structures
4. MOCK format: Flattened <li> + <p> structure with interleaved questions/options

Also captures images embedded in questions/options.
Flags questions/options that contain "(Image)" for manual review.
"""
import os
import re
import uuid
import base64
from typing import Optional, List, Dict, Any, Tuple
from bs4 import BeautifulSoup, Tag, NavigableString
import mammoth


def extract_text_and_html(element: Tag) -> tuple[str, str]:
    """Extract plain text and inner HTML from an element."""
    text = element.get_text(strip=True)
    html = ''.join(str(c) for c in element.children)
    return text, html


def check_needs_image(text: str) -> bool:
    """Check if text contains (Image) marker indicating manual image insertion needed."""
    return '(Image)' in text or '(image)' in text.lower()


def extract_images(element: Tag, job_id: str, upload_dir: str) -> List[Dict]:
    """Extract images from an element and save them."""
    images = []
    for img in element.find_all('img'):
        src = img.get('src', '')
        if src.startswith('data:image'):
            # Base64 encoded image
            try:
                # Parse data URL
                header, data = src.split(',', 1)
                # Get mime type
                mime_match = re.search(r'data:(image/[^;]+)', header)
                mime_type = mime_match.group(1) if mime_match else 'image/png'
                ext = mime_type.split('/')[-1]
                
                # Generate filename
                img_id = str(uuid.uuid4())[:8]
                filename = f"{img_id}.{ext}"
                
                # Save image
                img_dir = os.path.join(upload_dir, job_id, 'images')
                os.makedirs(img_dir, exist_ok=True)
                img_path = os.path.join(img_dir, filename)
                
                with open(img_path, 'wb') as f:
                    f.write(base64.b64decode(data))
                
                images.append({
                    'id': img_id,
                    'path': img_path,
                    'content_type': mime_type,
                    'filename': filename
                })
            except Exception as e:
                print(f"Warning: Failed to extract image: {e}")
    
    return images


def is_question_text(text: str) -> bool:
    """Check if text looks like a question (long, has question patterns)."""
    if len(text) < 30:
        return False
    
    question_patterns = [
        'which', 'what', 'who', 'when', 'where', 'how', 'why',
        'select', 'choose', 'find', 'identify', 'consider',
        'following', 'statement', 'assertion', 'match',
        '?', 'निम्न', 'कौन', 'क्या', 'किस', 'चुनें', 'चयन'
    ]
    
    text_lower = text.lower()
    return any(p in text_lower for p in question_patterns) or len(text) > 60


def is_option_text(text: str) -> bool:
    """Check if text looks like an option (short, or numbered 1,2,3,4 or A,B,C,D)."""
    text = text.strip()
    if len(text) == 0:
        return True  # Empty items are likely image placeholders
    if len(text) <= 3 and text in ['1', '2', '3', '4', 'A', 'B', 'C', 'D', 'a', 'b', 'c', 'd']:
        return True
    if len(text) < 100:
        return True
    return False


def detect_question_type(text: str) -> str:
    """Detect question type from text patterns."""
    text_lower = text.lower()
    if 'assertion' in text_lower or 'reason' in text_lower:
        return 'assertion-reason'
    elif 'match' in text_lower or 'matching' in text_lower:
        return 'matching'
    elif 'how many' in text_lower or 'कितने' in text:
        return 'how-many'
    elif any(x in text_lower for x in ['statement', 'statements', 'कथन', 'कथनों']):
        return 'statement-based'
    elif 'figure' in text_lower or 'image' in text_lower or 'diagram' in text_lower:
        return 'figure-based'
    return 'single'


def parse_standard_ol(items: List[Tag], start_q_id: int, job_id: str, upload_dir: str) -> List[Dict]:
    """Parse OL with standard structure: Question + 4 options."""
    questions = []
    num_items = len(items)
    q_id = start_q_id
    i = 0
    
    while i + 4 < num_items:
        q_li = items[i]
        q_text, q_html = extract_text_and_html(q_li)
        
        # Get images from question
        q_images = extract_images(q_li, job_id, upload_dir)
        
        # Get the 4 options
        options = []
        option_labels = ['A', 'B', 'C', 'D']
        
        for j in range(4):
            opt_li = items[i + 1 + j]
            opt_text, opt_html = extract_text_and_html(opt_li)
            opt_images = extract_images(opt_li, job_id, upload_dir)
            needs_img = check_needs_image(opt_text)
            
            options.append({
                'label': option_labels[j],
                'english_text': opt_text,
                'hindi_text': '',
                'is_correct': False,
                'images': opt_images,
                'needs_image': needs_img
            })
        
        # Get tables from question
        tables = []
        for table in q_li.find_all('table'):
            tables.append({
                'id': str(uuid.uuid4())[:8],
                'html': str(table),
                'rows': len(table.find_all('tr')),
                'cols': len(table.find('tr').find_all(['td', 'th'])) if table.find('tr') else 0
            })
        
        # Check if question needs image
        q_needs_image = check_needs_image(q_text)
        flags = []
        if q_needs_image:
            flags.append('needs_image')
        if any(opt.get('needs_image') for opt in options):
            flags.append('options_need_images')
        
        question = {
            'id': q_id,
            'english_text': q_text,
            'hindi_text': '',
            'question_type': detect_question_type(q_text),
            'options': options,
            'answer': '',
            'solution_english': '',
            'solution_hindi': '',
            'grading': '',
            'tables': tables,
            'images': q_images,
            'confidence': 1.0,
            'flags': flags,
            'needs_image': q_needs_image
        }
        
        questions.append(question)
        q_id += 1
        i += 5
    
    return questions


def parse_reversed_ol(items: List[Tag], start_q_id: int, job_id: str, upload_dir: str) -> List[Dict]:
    """Parse OL with reversed structure: 4 options + Question (for figure questions)."""
    questions = []
    num_items = len(items)
    q_id = start_q_id
    i = 0
    
    while i + 4 < num_items:
        # In reversed structure: items[0-3] are options, items[4] is question
        option_labels = ['A', 'B', 'C', 'D']
        options = []
        
        for j in range(4):
            opt_li = items[i + j]
            opt_text, opt_html = extract_text_and_html(opt_li)
            opt_images = extract_images(opt_li, job_id, upload_dir)
            needs_img = check_needs_image(opt_text)
            
            options.append({
                'label': option_labels[j],
                'english_text': opt_text,
                'hindi_text': '',
                'is_correct': False,
                'images': opt_images,
                'needs_image': needs_img
            })
        
        # Question is the 5th item
        q_li = items[i + 4]
        q_text, q_html = extract_text_and_html(q_li)
        q_images = extract_images(q_li, job_id, upload_dir)
        
        tables = []
        for table in q_li.find_all('table'):
            tables.append({
                'id': str(uuid.uuid4())[:8],
                'html': str(table),
                'rows': len(table.find_all('tr')),
                'cols': len(table.find('tr').find_all(['td', 'th'])) if table.find('tr') else 0
            })
        
        # Check if question needs image
        q_needs_image = check_needs_image(q_text)
        flags = []
        if q_needs_image:
            flags.append('needs_image')
        if any(opt.get('needs_image') for opt in options):
            flags.append('options_need_images')
        
        question = {
            'id': q_id,
            'english_text': q_text,
            'hindi_text': '',
            'question_type': 'figure-based',
            'options': options,
            'answer': '',
            'solution_english': '',
            'solution_hindi': '',
            'grading': '',
            'tables': tables,
            'images': q_images,
            'confidence': 1.0,
            'flags': flags,
            'needs_image': q_needs_image
        }
        
        questions.append(question)
        q_id += 1
        i += 5
    
    return questions


def detect_ol_structure(items: List[Tag]) -> str:
    """
    Detect whether OL has standard (Q+4opts) or reversed (4opts+Q) structure.
    Returns 'standard', 'reversed', or 'mixed'.
    """
    if len(items) < 5:
        return 'unknown'
    
    # Check first 5 items
    first_5_lengths = [len(items[i].get_text().strip()) for i in range(min(5, len(items)))]
    
    # Standard: first item is long (question), next 4 are short (options)
    # Reversed: first 4 are short (options), 5th is long (question)
    
    if first_5_lengths[0] > 50 and all(l < 100 for l in first_5_lengths[1:5]):
        return 'standard'
    elif all(l < 50 for l in first_5_lengths[:4]) and first_5_lengths[4] > 30:
        return 'reversed'
    else:
        # Check more items to determine
        # If item[0] is short and item[4] is long, likely reversed
        if first_5_lengths[0] < 30 and first_5_lengths[4] > 40:
            return 'reversed'
        elif first_5_lengths[0] > 40:
            return 'standard'
    
    return 'standard'  # Default


def parse_docx_smart(file_path: str, job_id: str, upload_dir: str) -> list[dict]:
    """
    Parse a DOCX file using smart pattern recognition.
    
    Handles:
    1. Large OLs (100+ items): Detects structure (standard or reversed)
    2. Small OLs (5 items each): Detects structure (standard or reversed)
    3. Captures images embedded in questions and options
    """
    with open(file_path, "rb") as f:
        result = mammoth.convert_to_html(f)
        html = result.value
    
    soup = BeautifulSoup(html, 'html.parser')
    all_ols = soup.find_all('ol')
    
    if not all_ols:
        print("Warning: No ordered lists found in document")
        return []
    
    # First, try to detect MOCK format (flattened li + p structure)
    # MOCK format has many small OLs with <p> elements between them
    # Count total <li> items and <p> items
    all_items = []
    for child in soup.body.children if soup.body else soup.children:
        if isinstance(child, NavigableString):
            continue
        if child.name == 'ol':
            for li in child.find_all('li', recursive=False):
                all_items.append(('li', li.get_text().strip(), li))
        elif child.name == 'p':
            all_items.append(('p', child.get_text().strip(), child))
    
    li_count = len([x for x in all_items if x[0] == 'li'])
    p_count = len([x for x in all_items if x[0] == 'p'])
    
    # MOCK format detection: 
    # - Has <p> elements interspersed with <li> elements (p_count >= 5)
    # - li_count should be roughly divisible by 5 (Q + 4 options)
    # - Allow for off-by-few due to page breaks causing split OLs
    # - li_count % 5 should be 0-4 (close to divisible)
    if p_count >= 5 and li_count >= 50 and (li_count % 5) <= 4:
        # Likely MOCK format - try parsing it
        mock_questions = parse_mock_format(all_items, job_id, upload_dir)
        if mock_questions:
            print(f"Parsed {len(mock_questions)} questions using MOCK format parser")
            return mock_questions
    
    # Fall back to original OL-based parsing
    # Categorize OLs by size
    ol_sizes = [(ol, len(ol.find_all('li', recursive=False))) for ol in all_ols]
    
    # All OLs with 5+ items can contain questions
    parseable_ols = [(ol, size) for ol, size in ol_sizes if size >= 5]
    
    questions = []
    q_id = 1
    
    for ol, size in parseable_ols:
        items = ol.find_all('li', recursive=False)
        
        # Detect structure based on content
        structure = detect_ol_structure(items)
        
        if structure == 'reversed':
            parsed = parse_reversed_ol(items, q_id, job_id, upload_dir)
        else:
            parsed = parse_standard_ol(items, q_id, job_id, upload_dir)
        
        questions.extend(parsed)
        q_id += len(parsed)
    
    print(f"Parsed {len(questions)} questions from {len(parseable_ols)} OLs")
    
    return questions


def parse_mock_format(all_items: List[Tuple], job_id: str, upload_dir: str) -> List[Dict]:
    """
    Parse MOCK format where structure is:
    <li>Question text</li>
    <p>Extra question text (optional, can be multiple)</p>
    <li>Option A</li>
    <li>Option B</li>
    <li>Option C</li>
    <li>Option D</li>
    <li>Next Question</li>
    ...
    
    Also handles edge case where options are split across OL blocks due to page breaks.
    """
    questions = []
    i = 0
    q_id = 1
    pending_question = None  # Store question that's waiting for options
    
    while i < len(all_items):
        tag, text, el = all_items[i]
        
        if tag == 'li':
            # Check if we have a pending question waiting for options
            if pending_question is not None:
                # This might be the start of split options
                # Try to collect 4 options
                options = []
                option_labels = ['A', 'B', 'C', 'D']
                start_i = i
                
                for j in range(4):
                    if i < len(all_items) and all_items[i][0] == 'li':
                        opt_text = all_items[i][1]
                        opt_el = all_items[i][2]
                        opt_images = extract_images(opt_el, job_id, upload_dir) if isinstance(opt_el, Tag) else []
                        needs_image = check_needs_image(opt_text)
                        
                        options.append({
                            'label': option_labels[j],
                            'english_text': opt_text,
                            'hindi_text': '',
                            'is_correct': False,
                            'images': opt_images,
                            'needs_image': needs_image
                        })
                        i += 1
                    else:
                        break
                
                if len(options) == 4:
                    # Successfully got 4 options for the pending question
                    pq = pending_question
                    needs_image = check_needs_image(pq['question_text'])
                    flags = []
                    if needs_image:
                        flags.append('needs_image')
                    if any(opt.get('needs_image') for opt in options):
                        flags.append('options_need_images')
                    
                    questions.append({
                        'id': q_id,
                        'english_text': pq['question_text'],
                        'hindi_text': '',
                        'question_type': detect_question_type(pq['question_text']),
                        'options': options,
                        'answer': '',
                        'solution_english': '',
                        'solution_hindi': '',
                        'grading': '',
                        'tables': [],
                        'images': pq['images'],
                        'confidence': 1.0,
                        'flags': flags,
                        'needs_image': needs_image
                    })
                    q_id += 1
                    pending_question = None
                    continue
                else:
                    # Not options, reset and treat as new question
                    i = start_i
                    pending_question = None
            
            # This should be a question
            question_text = text
            q_images = extract_images(el, job_id, upload_dir) if isinstance(el, Tag) else []
            i += 1
            
            # Collect ALL consecutive <p> elements as supplementary text
            while i < len(all_items) and all_items[i][0] == 'p':
                question_text += "\n" + all_items[i][1]
                # Also extract images from <p> elements
                if isinstance(all_items[i][2], Tag):
                    q_images.extend(extract_images(all_items[i][2], job_id, upload_dir))
                i += 1
            
            # Next 4 items should be options
            options = []
            option_labels = ['A', 'B', 'C', 'D']
            
            for j in range(4):
                if i < len(all_items) and all_items[i][0] == 'li':
                    opt_text = all_items[i][1]
                    opt_el = all_items[i][2]
                    opt_images = extract_images(opt_el, job_id, upload_dir) if isinstance(opt_el, Tag) else []
                    
                    # Check if option needs image
                    needs_image = check_needs_image(opt_text)
                    
                    options.append({
                        'label': option_labels[j],
                        'english_text': opt_text,
                        'hindi_text': '',
                        'is_correct': False,
                        'images': opt_images,
                        'needs_image': needs_image
                    })
                    i += 1
                else:
                    break
            
            if len(options) == 4:
                # Check if question needs image
                needs_image = check_needs_image(question_text)
                
                # Build flags list
                flags = []
                if needs_image:
                    flags.append('needs_image')
                if any(opt.get('needs_image') for opt in options):
                    flags.append('options_need_images')
                
                questions.append({
                    'id': q_id,
                    'english_text': question_text,
                    'hindi_text': '',
                    'question_type': detect_question_type(question_text),
                    'options': options,
                    'answer': '',
                    'solution_english': '',
                    'solution_hindi': '',
                    'grading': '',
                    'tables': [],
                    'images': q_images,
                    'confidence': 1.0,
                    'flags': flags,
                    'needs_image': needs_image
                })
                q_id += 1
            elif len(options) == 0:
                # No options found immediately after question
                # This might be a split case - store as pending and look for options after next <p> block
                pending_question = {
                    'question_text': question_text,
                    'images': q_images
                }
            # If 1-3 options, something is wrong - skip this malformed question
        else:
            # <p> element - check if we have a pending question
            if pending_question is not None:
                # Add this <p> text to the pending question
                pending_question['question_text'] += "\n" + text
                if isinstance(el, Tag):
                    pending_question['images'].extend(extract_images(el, job_id, upload_dir))
            i += 1
    
    return questions


def parse_document(file_path: str, job_id: str, upload_dir: str) -> list[dict]:
    """Main entry point for parsing."""
    return parse_docx_smart(file_path, job_id, upload_dir)


# Test
if __name__ == "__main__":
    import json
    
    # Test with MOCK files
    en_file = "/workspaces/QS-Formatter/files/MOCK 1 ENGLISH QUESTION.docx"
    hi_file = "/workspaces/QS-Formatter/files/MOCK 1 HINDI QUESTION.docx"
    
    print("Parsing English file...")
    en_questions = parse_docx_smart(en_file, "test", "/tmp")
    print(f"Extracted {len(en_questions)} English questions")
    
    print("\nParsing Hindi file...")
    hi_questions = parse_docx_smart(hi_file, "test", "/tmp")
    print(f"Extracted {len(hi_questions)} Hindi questions")
    
    # Show some questions with flags
    print("\nQuestions with image flags:")
    for q in en_questions:
        if q.get('needs_image') or q.get('flags'):
            print(f"\nQ{q['id']}: {q['english_text'][:60]}...")
            print(f"  Flags: {q.get('flags', [])}")
            for opt in q['options']:
                if opt.get('needs_image'):
                    print(f"  {opt['label']}) {opt['english_text'][:30]}... [NEEDS IMAGE]")
