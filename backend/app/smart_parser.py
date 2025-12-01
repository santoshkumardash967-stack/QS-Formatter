"""
Smart DOCX Parser for QS-Formatter.

Uses the fact that DOCX structure has questions in <li> tags with a consistent pattern:
- Each question = 1 question text + 4 options = 5 consecutive <li> elements
"""
import os
import re
import uuid
from typing import Optional
from bs4 import BeautifulSoup, Tag
import mammoth


def extract_text_and_html(element: Tag) -> tuple[str, str]:
    """Extract plain text and inner HTML from an element."""
    text = element.get_text(strip=True)
    html = ''.join(str(c) for c in element.children)
    return text, html


def has_table_before(li_element: Tag, soup: BeautifulSoup) -> Optional[str]:
    """Check if there's a table between the previous li and this one that belongs to the question."""
    # This is complex in the current structure, we'll handle tables separately
    return None


def parse_docx_smart(file_path: str, job_id: str, upload_dir: str) -> list[dict]:
    """
    Parse a DOCX file using the smart pattern recognition.
    
    Assumes: Each question is 5 consecutive <li> elements:
    - li[0]: Question text
    - li[1]: Option A
    - li[2]: Option B
    - li[3]: Option C
    - li[4]: Option D
    """
    with open(file_path, "rb") as f:
        result = mammoth.convert_to_html(f)
        html = result.value
    
    soup = BeautifulSoup(html, 'html.parser')
    all_lis = soup.find_all('li')
    
    questions = []
    num_items = len(all_lis)
    
    # Process in groups of 5
    q_id = 1
    i = 0
    
    while i + 4 < num_items:  # Need at least 5 items for a complete question
        # Get the question text
        q_li = all_lis[i]
        q_text, q_html = extract_text_and_html(q_li)
        
        # Get the 4 options
        options = []
        option_labels = ['A', 'B', 'C', 'D']
        
        for j in range(4):
            opt_li = all_lis[i + 1 + j]
            opt_text, opt_html = extract_text_and_html(opt_li)
            options.append({
                'label': option_labels[j],
                'english_text': opt_text,
                'hindi_text': '',
                'is_correct': False
            })
        
        # Check for tables between question li and next elements
        # Tables in the original doc appear between the question stem and "Which of the pairs..."
        # We need to look at the HTML structure more carefully
        
        # Look for tables that might be part of this question
        tables = []
        
        # Find any table elements that come after this li in the DOM
        # For now, we'll capture tables embedded in the question text
        table_elements = q_li.find_all('table')
        for table in table_elements:
            tables.append({
                'id': str(uuid.uuid4())[:8],
                'html': str(table),
                'rows': len(table.find_all('tr')),
                'cols': len(table.find('tr').find_all(['td', 'th'])) if table.find('tr') else 0
            })
        
        # Detect question type from text patterns
        question_type = 'single'
        text_lower = q_text.lower()
        if 'assertion' in text_lower or 'reason' in text_lower:
            question_type = 'assertion-reason'
        elif 'match' in text_lower or 'matching' in text_lower:
            question_type = 'matching'
        elif 'how many' in text_lower or 'कितने' in q_text:
            question_type = 'how-many'
        elif any(x in text_lower for x in ['statement', 'statements', 'कथन', 'कथनों']):
            question_type = 'statement-based'
        
        question = {
            'id': q_id,
            'english_text': q_text,
            'hindi_text': '',
            'question_type': question_type,
            'options': options,
            'answer': '',
            'solution_english': '',
            'solution_hindi': '',
            'tables': tables,
            'images': [],
            'confidence': 1.0,
            'flags': []
        }
        
        questions.append(question)
        q_id += 1
        i += 5  # Move to next question (skip question + 4 options)
    
    # Handle any remaining items (incomplete question at the end)
    remaining = num_items - i
    if remaining > 0:
        print(f"Warning: {remaining} items remaining after parsing (incomplete question)")
    
    return questions


def parse_document(file_path: str, job_id: str, upload_dir: str) -> list[dict]:
    """Main entry point for parsing."""
    return parse_docx_smart(file_path, job_id, upload_dir)


# Test
if __name__ == "__main__":
    import json
    
    en_file = "/workspaces/QS-Formatter/files/Mock-English-Question.docx"
    hi_file = "/workspaces/QS-Formatter/files/Mock-Hindi-Question.docx"
    
    print("Parsing English file...")
    en_questions = parse_docx_smart(en_file, "test", "/tmp")
    print(f"Extracted {len(en_questions)} English questions")
    
    print("\nFirst 3 questions:")
    for q in en_questions[:3]:
        print(f"\nQ{q['id']}: {q['english_text'][:80]}...")
        print(f"  Type: {q['question_type']}")
        for opt in q['options']:
            print(f"  {opt['label']}) {opt['english_text'][:60]}...")
    
    print("\n" + "="*50)
    print("Parsing Hindi file...")
    hi_questions = parse_docx_smart(hi_file, "test", "/tmp")
    print(f"Extracted {len(hi_questions)} Hindi questions")
    
    print("\nFirst 3 Hindi questions:")
    for q in hi_questions[:3]:
        print(f"\nQ{q['id']}: {q['english_text'][:80]}...")
        for opt in q['options']:
            print(f"  {opt['label']}) {opt['english_text'][:60]}...")
