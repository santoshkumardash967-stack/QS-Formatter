import React, { useState, useEffect } from 'react';
import type { Question, PreviewResponse } from '../types';
import QuestionCard from './QuestionCard';
import AddQuestionForm from './AddQuestionForm';

// Detect API URL for Codespaces or local development
const getApiUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const origin = window.location.origin;
    
    // Running in Codespaces (e.g., didactic-capybara-77rqj4gwr443p7g4-5175.app.github.dev)
    if (hostname.includes('app.github.dev')) {
      return origin.replace(/-(\d+)\.app\.github\.dev/, '-8000.app.github.dev');
    }
    if (hostname.includes('github.dev')) {
      return origin.replace(/-(\d+)\./, '-8000.');
    }
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();
console.log('PreviewEditor API URL:', API_URL);

interface PreviewEditorProps {
  jobId: string;
  onExport: (questions: Question[]) => void;
  onBack: () => void;
}

const PreviewEditor: React.FC<PreviewEditorProps> = ({ jobId, onExport, onBack }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [filter, setFilter] = useState<'all' | 'flagged' | 'low-confidence'>('all');
  const [englishCount, setEnglishCount] = useState(0);
  const [hindiCount, setHindiCount] = useState(0);
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    fetchPreview();
  }, [jobId]);

  const fetchPreview = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_URL}/jobs/${jobId}/preview`);
      if (!response.ok) {
        throw new Error('Failed to fetch preview');
      }
      const data: PreviewResponse = await response.json();
      setQuestions(data.questions);
      setEnglishCount(data.english_count);
      setHindiCount(data.hindi_count);
      
      // Auto-expand first question
      if (data.questions.length > 0) {
        setExpandedId(data.questions[0].id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preview');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateQuestion = (updated: Question) => {
    setQuestions(prev =>
      prev.map(q => q.id === updated.id ? updated : q)
    );
  };

  const handleAddQuestion = (newQuestion: Question) => {
    setQuestions(prev => [...prev, newQuestion]);
    setShowAddForm(false);
    // Expand the newly added question
    setExpandedId(newQuestion.id);
  };

  const handleDeleteQuestion = (id: number) => {
    if (window.confirm(`Are you sure you want to delete question Q${id}?`)) {
      setQuestions(prev => prev.filter(q => q.id !== id));
      if (expandedId === id) {
        setExpandedId(null);
      }
    }
  };

  const filteredQuestions = questions.filter(q => {
    if (filter === 'flagged') return q.flags.length > 0;
    if (filter === 'low-confidence') return q.confidence < 0.7;
    return true;
  });

  const handleExport = () => {
    onExport(questions);
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner"></div>
        <p>Loading preview...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="error-container">
        <h2>❌ Error</h2>
        <p>{error}</p>
        <button onClick={onBack}>← Go Back</button>
      </div>
    );
  }

  return (
    <div className="preview-container">
      <div className="preview-header">
        <button className="back-btn" onClick={onBack}>← Back</button>
        <h1>📝 Preview & Edit Questions</h1>
        <div className="stats">
          <span>English: {englishCount}</span>
          <span>Hindi: {hindiCount}</span>
          <span>Merged: {questions.length}</span>
        </div>
      </div>

      <div className="toolbar">
        <div className="filter-group">
          <label>Filter:</label>
          <button
            className={filter === 'all' ? 'active' : ''}
            onClick={() => setFilter('all')}
          >
            All ({questions.length})
          </button>
          <button
            className={filter === 'flagged' ? 'active' : ''}
            onClick={() => setFilter('flagged')}
          >
            ⚠️ Flagged ({questions.filter(q => q.flags.length > 0).length})
          </button>
          <button
            className={filter === 'low-confidence' ? 'active' : ''}
            onClick={() => setFilter('low-confidence')}
          >
            🔴 Low Confidence ({questions.filter(q => q.confidence < 0.7).length})
          </button>
        </div>

        <div className="action-buttons">
          <button className="add-question-btn" onClick={() => setShowAddForm(true)}>
            ➕ Add Question
          </button>
          <button className="export-btn" onClick={handleExport}>
            📥 Export DOCX
          </button>
        </div>
      </div>

      {/* Add Question Modal */}
      {showAddForm && (
        <div className="modal-overlay">
          <div className="modal-content">
            <AddQuestionForm
              jobId={jobId}
              nextId={questions.length > 0 ? Math.max(...questions.map(q => q.id)) + 1 : 1}
              onAdd={handleAddQuestion}
              onCancel={() => setShowAddForm(false)}
            />
          </div>
        </div>
      )}

      <div className="questions-list">
        {filteredQuestions.length === 0 ? (
          <div className="empty-state">
            No questions match the current filter.
          </div>
        ) : (
          filteredQuestions.map(q => (
            <QuestionCard
              key={q.id}
              question={q}
              jobId={jobId}
              onUpdate={handleUpdateQuestion}
              onDelete={() => handleDeleteQuestion(q.id)}
              isExpanded={expandedId === q.id}
              onToggle={() => setExpandedId(expandedId === q.id ? null : q.id)}
            />
          ))
        )}
      </div>

      <div className="footer-actions">
        <button className="export-btn large" onClick={handleExport}>
          📥 Export Final DOCX
        </button>
      </div>
    </div>
  );
};

export default PreviewEditor;
