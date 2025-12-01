You are an expert full-stack engineer and document-processing specialist (FastAPI, Python, React, DOCX parsing, HTML/Markdown normalization, image/table handling).
Your task is to build a robust, fault-tolerant webapp that accepts English + Hindi MCQ Word files in ANY format, allows human validation/editing, and exports the final DOCX in the strict lean format defined below.

🎯 GOAL OF THE SYSTEM

Users will upload two DOCX files (one English, one Hindi).
These files may be:

incorrectly formatted

inconsistent spacing

mixed Hindi/English in paragraphs

inline/anchored images

simple or complex tables

different option styles

noisy formatting

You must produce a clean, consistent final DOCX in the format below.

Before exporting, users must get a human review/edit window showing each merged question.

📄 STRICT REQUIRED OUTPUT FORMAT

Every exported question must follow this exact structure:

Q1. English question text?
    (Hindi question text?)
Type: multiple_choice
(A) English option (Hindi option)
(B) ...
(C) ...
(D) ...

[blank line]
[blank line]


Rules:

English first, Hindi next (indented 4 spaces).

Options on single bilingual lines: (A) English (Hindi)

Required line: Type:

Exactly two blank lines after each question.

Images copied inline (preserve format).

Simple tables recreated, complex tables → PNG inserted inline.

No header/footer/page breaks, no extra spacing.

📁 FILES IN THE REPO (IMPORTANT)

Inside /files there are real user source files:

/files/Mock-English-Question.docx

/files/Mock-Hindi-Question.docx

/files/required-format.docx

These MUST be used for:

Parser testing

Realistic alignment

Realistic table/image extraction validation

Do NOT modify these originals

EN & HI versions are in same order → use index-based pairing by default.

🧠 REAL-WORLD PROBLEMS YOU MUST HANDLE

Expect any of these from user DOCX files:

Inconsistent numbering (1. 1) Q1: or none)

Mixed Hindi/English within the same paragraph

Options inline in a single line (A. x B. y)

Options as bullet lists or tables

Anchored images, floating images, inline images

Tables with merged cells, nested tables

Multi-paragraph questions

Blank lines, page numbers, headers/footers

Missing Hindi or missing English text

Different fonts and broken Unicode

Images inside tables

Duplicate numbering or reset numbering

Your system must normalize everything and still produce clean output.

🔧 PIPELINE YOU MUST IMPLEMENT
1. Normalize

Convert each uploaded DOCX → HTML using Mammoth (primary)
Fallback: DOCX → Markdown (Pandoc or Mammoth) for ultra-messy cases.

Normalize:

trim extraneous whitespace

remove headers/footers

wrap <img> with stable IDs

convert lists into usable option blocks

2. Chunking / Question Detection

Detect question start using these rules:

Primary: regex ^\s*(?:Q\.?\s*)?(\d{1,3})[\.\)]

Secondary: headings <h1/h2/h3> that contain numbers

Fallback: blocks containing ≥2 option labels

3. Extract Question Content

For each question block extract:

English text

Hindi text

Options (normalize labels to A,B,C,D…)

Inline images

Tables (classify simple/complex)

4. Pairing (EN ↔ HI)

Since user versions are same order, pair by index:
english_questions[i] ↔ hindi_questions[i].

If counts mismatch → flag for user review.

5. Option Building

Build bilingual option lines as:
(A) EnglishOption (HindiOption)

If one side is missing → (A) text () and flag.

6. Asset Handling

Images: always extract blob + local filename. Insert inline in final DOCX.

Tables:

Simple → rebuild using python-docx

Complex → render as PNG (wkhtmltoimage / headless browser)

7. Confidence & Flags

Each question must have:

confidence score

flags: missing options, ambiguous numbering, complex table, unmatched images, etc.

Sorting in UI: low → high confidence.

8. Human Review Window (UI)

Preview every merged question using exact final layout.
Editable fields:

English text

Hindi text

Each option

Type

Table toggle (preserve / image)

Image placement toggle

Actions:

Save

Next / Previous

Bulk apply defaults

9. Export

Use python-docx to construct final DOCX:

Insert lines exactly in required format

Insert inline images

Insert tables according to fallback choice

Add two blank paragraphs per question

Use Unicode-safe fonts (Noto Sans Devanagari)

🧱 ARCHITECTURE (Simplified for Codespaces)
Backend: /backend/

FastAPI

python-docx

mammoth

BeautifulSoup4

Pillow

Optional wkhtmltoimage

Key modules:

parser.py — DOCX → HTML/MD → question blocks

aligner.py — pair EN/HI

exporter.py — build final DOCX

assets.py — extract images/tables

Endpoints:

POST /upload

GET /jobs/{id}/preview

POST /jobs/{id}/finalize

GET /download/{file}

Frontend: /frontend/

React + Vite + TypeScript

Pages: Upload → Preview (edit) → Export

Components: QuestionCard, OptionEditor, TablePreview, ImagePreview

🧪 TESTING TARGETS

Backend:

question chunking

option parsing

bilingual merge

image extraction & reinsertion

table classification

export formatting consistency

Frontend:

upload flow

preview rendering

editing

export

🧭 DEVELOPMENT REQUIREMENTS

Must run in GitHub Codespaces with:

uvicorn backend.app.main:app --reload

npm run dev

No Docker needed

No external services required except wkhtmltoimage binary if used

🔥 START NOW

Begin by generating:

The repository folder structure

The backend parser/service stubs

Basic job flow (upload → parse → preview JSON)

A sample preview JSON using the real files in /files

Then continue implementing full functionality.


