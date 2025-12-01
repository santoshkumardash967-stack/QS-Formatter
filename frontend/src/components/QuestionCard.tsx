import React, { useState } from 'react';
import type { Question, QuestionType } from '../types';

interface QuestionCardProps {
  question: Question;
  onUpdate: (updated: Question) => void;
  isExpanded: boolean;
  onToggle: () => void;
}

const QuestionCard: React.FC<QuestionCardProps> = ({
  question,
  onUpdate,
  isExpanded,
  onToggle,
}) => {
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<Question>(question);

  const handleSave = () => {
    onUpdate(editData);
    setEditing(false);
  };

  const handleCancel = () => {
    setEditData(question);
    setEditing(false);
  };

  const handleOptionChange = (index: number, field: 'english_text' | 'hindi_text', value: string) => {
    const newOptions = [...editData.options];
    newOptions[index] = { ...newOptions[index], [field]: value };
    setEditData({ ...editData, options: newOptions });
  };

  const confidenceColor = question.confidence >= 0.8 ? '#4caf50' : 
                          question.confidence >= 0.5 ? '#ff9800' : '#f44336';

  return (
    <div className={`question-card ${question.flags.length > 0 ? 'has-flags' : ''}`}>
      <div className="question-header" onClick={onToggle}>
        <div className="question-number">Q{question.id}</div>
        <div className="question-preview">
          {question.english_text.substring(0, 80)}...
        </div>
        <div className="question-meta">
          <span 
            className="confidence-badge"
            style={{ backgroundColor: confidenceColor }}
          >
            {Math.round(question.confidence * 100)}%
          </span>
          <span className="option-count">{question.options.length} options</span>
          <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
        </div>
      </div>

      {isExpanded && (
        <div className="question-body">
          {question.flags.length > 0 && (
            <div className="flags">
              {question.flags.map((flag, i) => (
                <span key={i} className="flag-badge">{flag.replace(/_/g, ' ')}</span>
              ))}
            </div>
          )}

          {editing ? (
            <div className="edit-mode">
              <div className="edit-section">
                <label>English Question:</label>
                <textarea
                  value={editData.english_text}
                  onChange={(e) => setEditData({ ...editData, english_text: e.target.value })}
                  rows={3}
                />
              </div>

              <div className="edit-section">
                <label>Hindi Question (हिंदी):</label>
                <textarea
                  value={editData.hindi_text}
                  onChange={(e) => setEditData({ ...editData, hindi_text: e.target.value })}
                  rows={3}
                />
              </div>

              <div className="edit-section">
                <label>Question Type:</label>
                <select
                  value={editData.question_type}
                  onChange={(e) => setEditData({ ...editData, question_type: e.target.value as QuestionType })}
                >
                  <option value="multiple_choice">Multiple Choice</option>
                  <option value="integer">Integer</option>
                  <option value="fill_ups">Fill in the Blanks</option>
                  <option value="true_false">True/False</option>
                </select>
              </div>

              <div className="edit-section">
                <label>Options:</label>
                {editData.options.map((opt, i) => (
                  <div key={i} className="option-edit">
                    <span className="option-label">({opt.label})</span>
                    <input
                      type="text"
                      placeholder="English"
                      value={opt.english_text}
                      onChange={(e) => handleOptionChange(i, 'english_text', e.target.value)}
                    />
                    <input
                      type="text"
                      placeholder="Hindi"
                      value={opt.hindi_text}
                      onChange={(e) => handleOptionChange(i, 'hindi_text', e.target.value)}
                    />
                  </div>
                ))}
              </div>

              <div className="edit-section">
                <label>Answer:</label>
                <input
                  type="text"
                  value={editData.answer || ''}
                  onChange={(e) => setEditData({ ...editData, answer: e.target.value })}
                  placeholder="e.g., A, B, C, D"
                />
              </div>

              <div className="edit-actions">
                <button className="btn-save" onClick={handleSave}>💾 Save</button>
                <button className="btn-cancel" onClick={handleCancel}>Cancel</button>
              </div>
            </div>
          ) : (
            <div className="view-mode">
              <div className="question-text">
                <div className="english">
                  <strong>English:</strong> {question.english_text}
                </div>
                <div className="hindi">
                  <strong>Hindi:</strong> {question.hindi_text}
                </div>
              </div>

              <div className="question-type">
                <strong>Type:</strong> {question.question_type.replace(/_/g, ' ')}
              </div>

              <div className="options-list">
                <strong>Options:</strong>
                {question.options.map((opt, i) => (
                  <div key={i} className="option-item">
                    <span className="option-label">({opt.label})</span>
                    <span className="option-english">{opt.english_text}</span>
                    <span className="option-hindi">({opt.hindi_text})</span>
                  </div>
                ))}
              </div>

              {question.tables.length > 0 && (
                <div className="tables-section">
                  <strong>Tables:</strong> {question.tables.length} table(s)
                  {question.tables.map((table, i) => (
                    <div 
                      key={i} 
                      className="table-preview"
                      dangerouslySetInnerHTML={{ __html: table.html }}
                    />
                  ))}
                </div>
              )}

              <button className="btn-edit" onClick={() => setEditing(true)}>
                ✏️ Edit
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default QuestionCard;
