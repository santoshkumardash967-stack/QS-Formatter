// API Types for QS-Formatter

export type QuestionType = 'multiple_choice' | 'integer' | 'fill_ups' | 'true_false';
export type TableRenderMode = 'preserve' | 'image';
export type JobStatus = 'pending' | 'processing' | 'ready' | 'exported' | 'failed';

export interface Option {
  label: string;
  english_text: string;
  hindi_text: string;
  needs_image?: boolean;
  images?: ImageData[];
}

export interface TableData {
  id: string;
  html: string;
  is_complex: boolean;
  render_mode: TableRenderMode;
  image_path?: string;
}

export interface ImageData {
  id: string;
  filename: string;
  path: string;
  content_type: string;
}

export type QuestionFlag =
  | 'missing_english'
  | 'missing_hindi'
  | 'missing_options'
  | 'incomplete_options'
  | 'ambiguous_numbering'
  | 'complex_table'
  | 'unmatched_images'
  | 'low_confidence'
  | 'count_mismatch'
  | 'needs_image'
  | 'options_need_images';

export interface Question {
  id: number;
  english_text: string;
  hindi_text: string;
  question_type: QuestionType;
  options: Option[];
  tables: TableData[];
  images: ImageData[];
  answer?: string;
  solution_english?: string;
  solution_hindi?: string;
  grading?: string;
  confidence: number;
  flags: QuestionFlag[];
  needs_image?: boolean;
  raw_english?: string;
  raw_hindi?: string;
}

export interface UploadResponse {
  job_id: string;
  message: string;
}

export interface PreviewResponse {
  job_id: string;
  status: JobStatus;
  questions: Question[];
  english_count: number;
  hindi_count: number;
  error?: string;
}

export interface ExportResponse {
  job_id: string;
  download_url: string;
  filename: string;
}

export interface FinalizeRequest {
  questions: Question[];
}
