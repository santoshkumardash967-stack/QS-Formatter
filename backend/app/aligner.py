"""
Aligner Module - Pairs English and Hindi questions by index.
"""
from typing import List, Dict, Any, Tuple
from .models import (
    Question, Option, TableData, ImageData, QuestionFlag, 
    QuestionType, TableRenderMode
)


class QuestionAligner:
    """
    Aligns English and Hindi questions, creating merged bilingual questions.
    """
    
    def __init__(self):
        pass
    
    def align_questions(
        self,
        english_questions: List[Dict[str, Any]],
        hindi_questions: List[Dict[str, Any]]
    ) -> Tuple[List[Question], List[QuestionFlag]]:
        """
        Align English and Hindi questions by index.
        Returns list of merged Question objects and any global flags.
        """
        global_flags = []
        merged_questions = []
        
        en_count = len(english_questions)
        hi_count = len(hindi_questions)
        
        # Check for count mismatch
        if en_count != hi_count:
            global_flags.append(QuestionFlag.COUNT_MISMATCH)
        
        max_count = max(en_count, hi_count)
        
        for i in range(max_count):
            en_q = english_questions[i] if i < en_count else None
            hi_q = hindi_questions[i] if i < hi_count else None
            
            merged = self._merge_question(i + 1, en_q, hi_q)
            merged_questions.append(merged)
        
        return merged_questions, global_flags
    
    def _merge_question(
        self,
        question_id: int,
        en_q: Dict[str, Any] = None,
        hi_q: Dict[str, Any] = None
    ) -> Question:
        """
        Merge English and Hindi question data into a single Question.
        """
        flags = []
        confidence = 1.0
        
        # Extract text - smart_parser uses 'english_text', older parser used 'text'
        english_text = ""
        hindi_text = ""
        
        if en_q:
            english_text = en_q.get('english_text', en_q.get('text', '')).strip()
        else:
            flags.append(QuestionFlag.MISSING_ENGLISH)
            confidence -= 0.3
        
        if hi_q:
            # Hindi parser stores Hindi text in 'english_text' field (since it's parsing Hindi doc)
            hindi_text = hi_q.get('english_text', hi_q.get('text', '')).strip()
        else:
            flags.append(QuestionFlag.MISSING_HINDI)
            confidence -= 0.3
        
        # Merge options - smart_parser has 'english_text' in options
        options = self._merge_options(
            en_q.get('options', []) if en_q else [],
            hi_q.get('options', []) if hi_q else [],
            flags
        )
        
        if len(options) < 2:
            flags.append(QuestionFlag.MISSING_OPTIONS)
            confidence -= 0.2
        elif len(options) < 4:
            flags.append(QuestionFlag.INCOMPLETE_OPTIONS)
            confidence -= 0.1
        
        # Merge tables
        tables = self._merge_tables(
            en_q.get('tables', []) if en_q else [],
            hi_q.get('tables', []) if hi_q else [],
            flags
        )
        
        # Merge images
        images = self._merge_images(
            en_q.get('images', []) if en_q else [],
            hi_q.get('images', []) if hi_q else [],
            flags
        )
        
        # Determine question type from en_q or detect from text
        question_type_str = en_q.get('question_type', 'single') if en_q else 'single'
        
        # Map string to enum - all map to MULTIPLE_CHOICE since model only has limited types
        type_mapping = {
            'single': QuestionType.MULTIPLE_CHOICE,
            'multiple-choice': QuestionType.MULTIPLE_CHOICE,
            'assertion-reason': QuestionType.MULTIPLE_CHOICE,
            'matching': QuestionType.MULTIPLE_CHOICE,
            'statement-based': QuestionType.MULTIPLE_CHOICE,
            'how-many': QuestionType.MULTIPLE_CHOICE,
            'integer': QuestionType.INTEGER,
            'fill-up': QuestionType.FILL_UPS,
        }
        question_type = type_mapping.get(question_type_str, QuestionType.MULTIPLE_CHOICE)
        
        confidence = max(0.0, min(1.0, confidence))
        
        if confidence < 0.7:
            flags.append(QuestionFlag.LOW_CONFIDENCE)
        
        # Check for needs_image flag from parser
        needs_image = False
        if en_q:
            if en_q.get('needs_image', False):
                needs_image = True
                if QuestionFlag.NEEDS_IMAGE not in flags:
                    flags.append(QuestionFlag.NEEDS_IMAGE)
            # Add parser flags
            parser_flags = en_q.get('flags', [])
            for pf in parser_flags:
                if pf == 'needs_image' and QuestionFlag.NEEDS_IMAGE not in flags:
                    flags.append(QuestionFlag.NEEDS_IMAGE)
                    needs_image = True
                elif pf == 'options_need_images' and QuestionFlag.OPTIONS_NEED_IMAGES not in flags:
                    flags.append(QuestionFlag.OPTIONS_NEED_IMAGES)
        
        return Question(
            id=question_id,
            english_text=english_text,
            hindi_text=hindi_text,
            question_type=question_type,
            options=options,
            tables=tables,
            images=images,
            confidence=confidence,
            flags=flags,
            needs_image=needs_image,
            raw_english="",
            raw_hindi=""
        )
    
    def _merge_options(
        self,
        en_options: List[Dict[str, str]],
        hi_options: List[Dict[str, str]],
        flags: List[QuestionFlag]
    ) -> List[Option]:
        """
        Merge English and Hindi options by label.
        """
        merged = []
        
        # Build lookup by label
        # smart_parser uses 'english_text' for option text
        en_by_label = {}
        en_needs_image = {}
        for opt in en_options:
            label = opt.get('label', '')
            text = opt.get('english_text', opt.get('text', ''))
            en_by_label[label] = text
            en_needs_image[label] = opt.get('needs_image', False)
        
        hi_by_label = {}
        for opt in hi_options:
            label = opt.get('label', '')
            text = opt.get('english_text', opt.get('text', ''))  # Hindi text stored here
            hi_by_label[label] = text
        
        # Get all labels, sorted A, B, C, D
        all_labels = sorted(set(en_by_label.keys()) | set(hi_by_label.keys()))
        
        for label in all_labels:
            en_text = en_by_label.get(label, '')
            hi_text = hi_by_label.get(label, '')
            needs_image = en_needs_image.get(label, False)
            
            merged.append(Option(
                label=label,
                english_text=en_text,
                hindi_text=hi_text,
                needs_image=needs_image
            ))
        
        return merged
    
    def _merge_tables(
        self,
        en_tables: List[Dict[str, Any]],
        hi_tables: List[Dict[str, Any]],
        flags: List[QuestionFlag]
    ) -> List[TableData]:
        """
        Merge tables from English and Hindi versions.
        For now, prefer English tables, use Hindi as fallback.
        """
        tables = []
        
        # Use English tables primarily
        for t in en_tables:
            render_mode = TableRenderMode.IMAGE if t.get('is_complex', False) else TableRenderMode.PRESERVE
            if t.get('is_complex'):
                flags.append(QuestionFlag.COMPLEX_TABLE)
            
            tables.append(TableData(
                id=t['id'],
                html=t['html'],
                is_complex=t.get('is_complex', False),
                render_mode=render_mode
            ))
        
        # If no English tables, use Hindi
        if not tables:
            for t in hi_tables:
                render_mode = TableRenderMode.IMAGE if t.get('is_complex', False) else TableRenderMode.PRESERVE
                if t.get('is_complex'):
                    flags.append(QuestionFlag.COMPLEX_TABLE)
                
                tables.append(TableData(
                    id=t['id'],
                    html=t['html'],
                    is_complex=t.get('is_complex', False),
                    render_mode=render_mode
                ))
        
        return tables
    
    def _merge_images(
        self,
        en_images: List[Dict[str, Any]],
        hi_images: List[Dict[str, Any]],
        flags: List[QuestionFlag]
    ) -> List[ImageData]:
        """
        Merge images from English and Hindi versions.
        """
        images = []
        seen_ids = set()
        
        for img in en_images + hi_images:
            if img['id'] not in seen_ids:
                seen_ids.add(img['id'])
                images.append(ImageData(
                    id=img['id'],
                    filename=img['filename'],
                    path=img['path'],
                    content_type=img.get('content_type', 'image/png')
                ))
        
        return images
