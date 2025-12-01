import axios from 'axios';
import type { UploadResponse, PreviewResponse, ExportResponse, FinalizeRequest, Question } from './types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadFiles = async (
  englishFile: File,
  hindiFile: File
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('english_file', englishFile);
  formData.append('hindi_file', hindiFile);

  const response = await api.post<UploadResponse>('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const getPreview = async (jobId: string): Promise<PreviewResponse> => {
  const response = await api.get<PreviewResponse>(`/jobs/${jobId}/preview`);
  return response.data;
};

export const updateQuestion = async (
  jobId: string,
  questionId: number,
  update: Partial<Question>
): Promise<void> => {
  await api.put(`/jobs/${jobId}/questions/${questionId}`, update);
};

export const finalizeJob = async (
  jobId: string,
  request: FinalizeRequest
): Promise<ExportResponse> => {
  const response = await api.post<ExportResponse>(`/jobs/${jobId}/finalize`, request);
  return response.data;
};

export const downloadFile = (jobId: string, filename: string): string => {
  return `${API_BASE}/download/${jobId}/${filename}`;
};

export const runDemo = async (): Promise<{ job_id: string; preview_url: string }> => {
  const response = await api.post('/demo');
  return response.data;
};

export default api;
