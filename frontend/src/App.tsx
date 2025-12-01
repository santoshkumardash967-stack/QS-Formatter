import { useState } from 'react';
import FileUpload from './components/FileUpload';
import PreviewEditor from './components/PreviewEditor';
import type { Question, ExportResponse } from './types';
import './App.css';

// Detect API URL for Codespaces or local development
const getApiUrl = () => {
  if (typeof window !== 'undefined' && window.location.hostname.includes('github.dev')) {
    // Running in Codespaces - use the forwarded port URL
    return window.location.origin.replace('5173', '8000');
  }
  if (typeof window !== 'undefined' && window.location.hostname.includes('app.github.dev')) {
    return window.location.origin.replace('5173', '8000');
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

type AppState = 'upload' | 'preview' | 'exported';

function App() {
  const [state, setState] = useState<AppState>('upload');
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exportResult, setExportResult] = useState<ExportResponse | null>(null);

  const handleUploadComplete = (newJobId: string) => {
    setJobId(newJobId);
    setState('preview');
    setError(null);
  };

  const handleError = (errorMessage: string) => {
    setError(errorMessage);
  };

  const handleExport = async (questions: Question[]) => {
    if (!jobId) return;

    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}/finalize`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ questions }),
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      const result: ExportResponse = await response.json();
      setExportResult(result);
      setState('exported');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    }
  };

  const handleBack = () => {
    setState('upload');
    setJobId(null);
    setExportResult(null);
    setError(null);
  };

  const handleDownload = () => {
    if (exportResult) {
      window.open(`${API_URL}${exportResult.download_url}`, '_blank');
    }
  };

  return (
    <div className="app">
      {error && (
        <div className="error-banner">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {state === 'upload' && (
        <FileUpload
          onUploadComplete={handleUploadComplete}
          onError={handleError}
        />
      )}

      {state === 'preview' && jobId && (
        <PreviewEditor
          jobId={jobId}
          onExport={handleExport}
          onBack={handleBack}
        />
      )}

      {state === 'exported' && exportResult && (
        <div className="export-success">
          <div className="success-icon">✅</div>
          <h1>Export Complete!</h1>
          <p>Your formatted document is ready for download.</p>
          <p className="filename">{exportResult.filename}</p>
          
          <div className="button-group">
            <button className="download-btn" onClick={handleDownload}>
              📥 Download DOCX
            </button>
            <button className="new-btn" onClick={handleBack}>
              📄 Format Another Document
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App
