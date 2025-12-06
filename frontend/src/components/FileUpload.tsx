import React, { useState, useCallback } from 'react';

// Detect API URL for Codespaces or local development
const getApiUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const origin = window.location.origin;
    
    // Running in Codespaces (e.g., didactic-capybara-77rqj4gwr443p7g4-5174.app.github.dev)
    if (hostname.includes('app.github.dev')) {
      // Replace the port number (e.g., -5174. -> -8000.)
      return origin.replace(/-(\d+)\.app\.github\.dev/, '-8000.app.github.dev');
    }
    // Old style Codespaces URL
    if (hostname.includes('github.dev')) {
      return origin.replace(/-(\d+)\./, '-8000.');
    }
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();
console.log('Frontend origin:', window.location.origin);
console.log('Backend API URL:', API_URL);

interface FileUploadProps {
  onUploadComplete: (jobId: string) => void;
  onError: (error: string) => void;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadComplete, onError }) => {
  const [englishFile, setEnglishFile] = useState<File | null>(null);
  const [hindiFile, setHindiFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState<'english' | 'hindi' | null>(null);

  const handleDrop = useCallback((e: React.DragEvent, type: 'english' | 'hindi') => {
    e.preventDefault();
    setDragOver(null);
    
    const file = e.dataTransfer.files[0];
    if (file && file.name.endsWith('.docx')) {
      if (type === 'english') {
        setEnglishFile(file);
      } else {
        setHindiFile(file);
      }
    } else {
      onError('Please upload a .docx file');
    }
  }, [onError]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, type: 'english' | 'hindi') => {
    const file = e.target.files?.[0];
    if (file) {
      if (type === 'english') {
        setEnglishFile(file);
      } else {
        setHindiFile(file);
      }
    }
  };

  const handleUpload = async () => {
    if (!englishFile || !hindiFile) {
      onError('Please select both English and Hindi files');
      return;
    }

    setUploading(true);

    try {
      const formData = new FormData();
      formData.append('english_file', englishFile);
      formData.append('hindi_file', hindiFile);

      const response = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Upload failed');
      }

      const data = await response.json();
      onUploadComplete(data.job_id);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDemo = async () => {
    setUploading(true);
    try {
      const response = await fetch('http://localhost:8000/demo', {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Demo failed');
      }

      const data = await response.json();
      onUploadComplete(data.job_id);
    } catch (err) {
      onError(err instanceof Error ? err.message : 'Demo failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-container">
      <h1>📄 QS-Formatter</h1>
      <p className="subtitle">Upload English and Hindi MCQ documents for formatting</p>

      <div className="upload-boxes">
        <div
          className={`upload-box ${dragOver === 'english' ? 'drag-over' : ''} ${englishFile ? 'has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver('english'); }}
          onDragLeave={() => setDragOver(null)}
          onDrop={(e) => handleDrop(e, 'english')}
        >
          <div className="upload-icon">🇬🇧</div>
          <h3>English Document</h3>
          {englishFile ? (
            <div className="file-info">
              <span className="file-name">{englishFile.name}</span>
              <button className="remove-btn" onClick={() => setEnglishFile(null)}>×</button>
            </div>
          ) : (
            <>
              <p>Drag & drop or click to select</p>
              <input
                type="file"
                accept=".docx"
                onChange={(e) => handleFileChange(e, 'english')}
              />
            </>
          )}
        </div>

        <div
          className={`upload-box ${dragOver === 'hindi' ? 'drag-over' : ''} ${hindiFile ? 'has-file' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver('hindi'); }}
          onDragLeave={() => setDragOver(null)}
          onDrop={(e) => handleDrop(e, 'hindi')}
        >
          <div className="upload-icon">🇮🇳</div>
          <h3>Hindi Document</h3>
          {hindiFile ? (
            <div className="file-info">
              <span className="file-name">{hindiFile.name}</span>
              <button className="remove-btn" onClick={() => setHindiFile(null)}>×</button>
            </div>
          ) : (
            <>
              <p>Drag & drop or click to select</p>
              <input
                type="file"
                accept=".docx"
                onChange={(e) => handleFileChange(e, 'hindi')}
              />
            </>
          )}
        </div>
      </div>

      <div className="button-group">
        <button
          className="upload-btn primary"
          onClick={handleUpload}
          disabled={!englishFile || !hindiFile || uploading}
        >
          {uploading ? 'Processing...' : '🚀 Upload & Process'}
        </button>
        
        <button
          className="upload-btn secondary"
          onClick={handleDemo}
          disabled={uploading}
        >
          {uploading ? 'Loading...' : '🎯 Try Demo Files'}
        </button>
      </div>
    </div>
  );
};

export default FileUpload;
