"""
Main FastAPI Application for QS-Formatter.
"""
import os
import uuid
import json
import shutil
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import (
    Job, JobStatus, Question, UploadResponse, PreviewResponse,
    FinalizeRequest, ExportResponse, QuestionUpdate
)
from .smart_parser import parse_document
from .aligner import QuestionAligner
from .exporter import SimpleExporter
from .assets import ImageProcessor, TableProcessor

# Configuration
UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/tmp/qs-formatter")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory job storage (in production, use Redis or database)
jobs: dict[str, Job] = {}

# Initialize components
aligner = QuestionAligner()
exporter = SimpleExporter(UPLOAD_DIR)
image_processor = ImageProcessor(UPLOAD_DIR)
table_processor = TableProcessor(UPLOAD_DIR)

# Create FastAPI app
app = FastAPI(
    title="QS-Formatter API",
    description="API for formatting bilingual MCQ documents",
    version="1.0.0"
)

# CORS configuration - Allow all origins for Codespaces compatibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def get_job(job_id: str) -> Job:
    """Get job by ID or raise 404."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return jobs[job_id]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "message": "QS-Formatter API is running"}


@app.post("/upload", response_model=UploadResponse)
async def upload_files(
    english_file: UploadFile = File(...),
    hindi_file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Upload English and Hindi DOCX files for processing.
    """
    # Validate file types
    for file, name in [(english_file, "English"), (hindi_file, "Hindi")]:
        if not file.filename.endswith('.docx'):
            raise HTTPException(
                status_code=400,
                detail=f"{name} file must be a .docx file"
            )
    
    # Create job
    job_id = str(uuid.uuid4())[:12]
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    # Save uploaded files
    en_path = os.path.join(job_dir, "english.docx")
    hi_path = os.path.join(job_dir, "hindi.docx")
    
    with open(en_path, "wb") as f:
        content = await english_file.read()
        f.write(content)
    
    with open(hi_path, "wb") as f:
        content = await hindi_file.read()
        f.write(content)
    
    # Create job record
    now = datetime.utcnow().isoformat()
    job = Job(
        id=job_id,
        status=JobStatus.PROCESSING,
        english_file=en_path,
        hindi_file=hi_path,
        created_at=now,
        updated_at=now
    )
    jobs[job_id] = job
    
    # Process files
    try:
        process_job(job_id)
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        raise HTTPException(status_code=500, detail=str(e))
    
    return UploadResponse(
        job_id=job_id,
        message="Files uploaded and processing complete"
    )


def process_job(job_id: str):
    """Process uploaded files and extract questions."""
    job = jobs[job_id]
    
    try:
        # Parse English file using robust parser
        en_questions = parse_document(job.english_file, job_id, UPLOAD_DIR)
        
        # Parse Hindi file
        hi_questions = parse_document(job.hindi_file, job_id, UPLOAD_DIR)
        
        job.english_count = len(en_questions)
        job.hindi_count = len(hi_questions)
        
        # Align and merge
        merged_questions, global_flags = aligner.align_questions(en_questions, hi_questions)
        
        job.questions = merged_questions
        job.status = JobStatus.READY
        job.updated_at = datetime.utcnow().isoformat()
        
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        raise


@app.get("/jobs/{job_id}/preview", response_model=PreviewResponse)
async def get_preview(job_id: str):
    """
    Get preview of parsed and merged questions.
    """
    job = get_job(job_id)
    
    return PreviewResponse(
        job_id=job_id,
        status=job.status,
        questions=job.questions,
        english_count=job.english_count,
        hindi_count=job.hindi_count,
        error=job.error
    )


@app.put("/jobs/{job_id}/questions/{question_id}")
async def update_question(job_id: str, question_id: int, update: QuestionUpdate):
    """
    Update a single question.
    """
    job = get_job(job_id)
    
    # Find question
    for i, q in enumerate(job.questions):
        if q.id == question_id:
            # Update fields
            if update.english_text is not None:
                job.questions[i].english_text = update.english_text
            if update.hindi_text is not None:
                job.questions[i].hindi_text = update.hindi_text
            if update.question_type is not None:
                job.questions[i].question_type = update.question_type
            if update.options is not None:
                job.questions[i].options = update.options
            if update.answer is not None:
                job.questions[i].answer = update.answer
            if update.solution_english is not None:
                job.questions[i].solution_english = update.solution_english
            if update.solution_hindi is not None:
                job.questions[i].solution_hindi = update.solution_hindi
            if update.grading is not None:
                job.questions[i].grading = update.grading
            
            job.updated_at = datetime.utcnow().isoformat()
            return {"status": "updated", "question_id": question_id}
    
    raise HTTPException(status_code=404, detail=f"Question {question_id} not found")


@app.post("/jobs/{job_id}/finalize", response_model=ExportResponse)
async def finalize_job(job_id: str, request: FinalizeRequest):
    """
    Finalize and export the document.
    """
    job = get_job(job_id)
    
    # Update questions from request
    job.questions = request.questions
    
    try:
        # Export to DOCX
        output_path = exporter.export(job.questions, job_id)
        
        job.output_file = output_path
        job.status = JobStatus.EXPORTED
        job.updated_at = datetime.utcnow().isoformat()
        
        filename = os.path.basename(output_path)
        
        return ExportResponse(
            job_id=job_id,
            download_url=f"/download/{job_id}/{filename}",
            filename=filename
        )
    
    except Exception as e:
        job.status = JobStatus.FAILED
        job.error = str(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/download/{job_id}/{filename}")
async def download_file(job_id: str, filename: str):
    """
    Download the exported file.
    """
    job = get_job(job_id)
    
    if not job.output_file or not os.path.exists(job.output_file):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        job.output_file,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename
    )


@app.get("/jobs/{job_id}/images/{image_id}")
async def get_image(job_id: str, image_id: str):
    """
    Get an image by ID.
    """
    job = get_job(job_id)
    
    # Find image in questions
    for q in job.questions:
        for img in q.images:
            if img.id == image_id:
                if os.path.exists(img.path):
                    return FileResponse(img.path, media_type=img.content_type)
    
    raise HTTPException(status_code=404, detail="Image not found")


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a job and its files.
    """
    job = get_job(job_id)
    
    # Delete files
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    if os.path.exists(job_dir):
        shutil.rmtree(job_dir)
    
    # Remove from memory
    del jobs[job_id]
    
    return {"status": "deleted", "job_id": job_id}


@app.get("/jobs")
async def list_jobs():
    """
    List all jobs.
    """
    return {
        "jobs": [
            {
                "id": j.id,
                "status": j.status,
                "english_count": j.english_count,
                "hindi_count": j.hindi_count,
                "created_at": j.created_at
            }
            for j in jobs.values()
        ]
    }


# Demo endpoint using test files
@app.post("/demo")
async def demo_parse():
    """
    Demo endpoint using the test files in /files directory.
    """
    files_dir = "/workspaces/QS-Formatter/files"
    en_file = os.path.join(files_dir, "Mock-English-Question.docx")
    hi_file = os.path.join(files_dir, "Mock-Hindi-Question.docx")
    
    if not os.path.exists(en_file) or not os.path.exists(hi_file):
        raise HTTPException(status_code=404, detail="Demo files not found")
    
    # Create job
    job_id = f"demo_{uuid.uuid4().hex[:8]}"
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    # Copy files
    en_path = os.path.join(job_dir, "english.docx")
    hi_path = os.path.join(job_dir, "hindi.docx")
    shutil.copy(en_file, en_path)
    shutil.copy(hi_file, hi_path)
    
    now = datetime.utcnow().isoformat()
    job = Job(
        id=job_id,
        status=JobStatus.PROCESSING,
        english_file=en_path,
        hindi_file=hi_path,
        created_at=now,
        updated_at=now
    )
    jobs[job_id] = job
    
    # Process
    process_job(job_id)
    
    return {
        "job_id": job_id,
        "status": job.status,
        "english_count": job.english_count,
        "hindi_count": job.hindi_count,
        "preview_url": f"/jobs/{job_id}/preview"
    }
