"""
Pydantic models for the QS-Formatter API.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    INTEGER = "integer"
    FILL_UPS = "fill_ups"
    TRUE_FALSE = "true_false"


class TableRenderMode(str, Enum):
    PRESERVE = "preserve"  # Rebuild table in DOCX
    IMAGE = "image"  # Render as PNG


class Option(BaseModel):
    """A single option for an MCQ question."""
    label: str = Field(..., description="Option label (A, B, C, D, etc.)")
    english_text: str = Field(default="", description="English option text")
    hindi_text: str = Field(default="", description="Hindi option text")
    needs_image: bool = Field(default=False, description="Whether option needs manual image upload")


class TableData(BaseModel):
    """Table extracted from a question."""
    id: str
    html: str
    is_complex: bool = False
    render_mode: TableRenderMode = TableRenderMode.PRESERVE
    image_path: Optional[str] = None


class ImageData(BaseModel):
    """Image extracted from a question."""
    id: str
    filename: str
    path: str
    content_type: str = "image/png"


class QuestionFlag(str, Enum):
    MISSING_ENGLISH = "missing_english"
    MISSING_HINDI = "missing_hindi"
    MISSING_OPTIONS = "missing_options"
    INCOMPLETE_OPTIONS = "incomplete_options"
    AMBIGUOUS_NUMBERING = "ambiguous_numbering"
    COMPLEX_TABLE = "complex_table"
    UNMATCHED_IMAGES = "unmatched_images"
    LOW_CONFIDENCE = "low_confidence"
    COUNT_MISMATCH = "count_mismatch"
    NEEDS_IMAGE = "needs_image"
    OPTIONS_NEED_IMAGES = "options_need_images"


class Question(BaseModel):
    """A parsed and merged bilingual question."""
    id: int = Field(..., description="Question number")
    english_text: str = Field(default="", description="English question text")
    hindi_text: str = Field(default="", description="Hindi question text")
    question_type: QuestionType = Field(default=QuestionType.MULTIPLE_CHOICE)
    options: List[Option] = Field(default_factory=list)
    tables: List[TableData] = Field(default_factory=list)
    images: List[ImageData] = Field(default_factory=list)
    answer: Optional[str] = None
    solution_english: Optional[str] = None
    solution_hindi: Optional[str] = None
    grading: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    flags: List[QuestionFlag] = Field(default_factory=list)
    needs_image: bool = Field(default=False, description="Whether question needs manual image upload")
    raw_english: Optional[str] = None
    raw_hindi: Optional[str] = None


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    EXPORTED = "exported"
    FAILED = "failed"


class Job(BaseModel):
    """A processing job for uploaded documents."""
    id: str
    status: JobStatus = JobStatus.PENDING
    english_file: Optional[str] = None
    hindi_file: Optional[str] = None
    questions: List[Question] = Field(default_factory=list)
    english_count: int = 0
    hindi_count: int = 0
    error: Optional[str] = None
    output_file: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


class UploadResponse(BaseModel):
    """Response after uploading files."""
    job_id: str
    message: str


class PreviewResponse(BaseModel):
    """Response for preview endpoint."""
    job_id: str
    status: JobStatus
    questions: List[Question]
    english_count: int
    hindi_count: int
    error: Optional[str] = None


class QuestionUpdate(BaseModel):
    """Update data for a single question."""
    english_text: Optional[str] = None
    hindi_text: Optional[str] = None
    question_type: Optional[QuestionType] = None
    options: Optional[List[Option]] = None
    answer: Optional[str] = None
    solution_english: Optional[str] = None
    solution_hindi: Optional[str] = None
    grading: Optional[str] = None


class FinalizeRequest(BaseModel):
    """Request to finalize and export a job."""
    questions: List[Question]


class ExportResponse(BaseModel):
    """Response after exporting."""
    job_id: str
    download_url: str
    filename: str
