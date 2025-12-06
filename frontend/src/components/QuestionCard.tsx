import React, { useState, useRef } from 'react';
import type { Question, QuestionType, Option, ImageData } from '../types';

// Detect API URL for Codespaces or local development
const getApiUrl = () => {
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname;
    const origin = window.location.origin;
    
    // Running in Codespaces (e.g., didactic-capybara-77rqj4gwr443p7g4-5174.app.github.dev)
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

interface UploadedImage {
  file: File;
  preview: string;
  id: string;
  uploaded?: ImageData;
}

interface QuestionCardProps {
  question: Question;
  jobId: string;
  onUpdate: (updated: Question) => void;
  onDelete?: () => void;
  isExpanded: boolean;
  onToggle: () => void;
}

const QuestionCard: React.FC<QuestionCardProps> = ({
  question,
  jobId,
  onUpdate,
  onDelete,
  isExpanded,
  onToggle,
}) => {
  const [editing, setEditing] = useState(false);
  const [editData, setEditData] = useState<Question>(question);
  const [newQuestionImages, setNewQuestionImages] = useState<UploadedImage[]>([]);
  const [optionImages, setOptionImages] = useState<Record<string, UploadedImage | null>>({});
  const [uploading, setUploading] = useState(false);
  
  const questionImageRef = useRef<HTMLInputElement>(null);
  const optionImageRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const uploadImage = async (file: File): Promise<ImageData | null> => {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('job_id', jobId);

      const response = await fetch(`${API_URL}/jobs/${jobId}/upload-image`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Failed to upload image');
      }

      return await response.json();
    } catch (err) {
      console.error('Image upload failed:', err);
      return null;
    }
  };

  const handleSave = async () => {
    setUploading(true);
    
    try {
      let updatedData = { ...editData };
      
      // Upload new question images
      const uploadedQuestionImages: ImageData[] = [...(editData.images || [])];
      for (const img of newQuestionImages) {
        const uploaded = await uploadImage(img.file);
        if (uploaded) {
          uploadedQuestionImages.push(uploaded);
        }
      }
      updatedData.images = uploadedQuestionImages;
      
      // Upload option images and update options
      const updatedOptions = [...updatedData.options];
      for (let i = 0; i < updatedOptions.length; i++) {
        const opt = updatedOptions[i];
        const optImage = optionImages[opt.label];
        if (optImage) {
          const uploaded = await uploadImage(optImage.file);
          if (uploaded) {
            updatedOptions[i] = {
              ...opt,
              english_text: opt.english_text + (opt.english_text ? ' ' : '') + `[Image: ${uploaded.filename}]`,
            };
          }
        }
      }
      updatedData.options = updatedOptions;
      
      onUpdate(updatedData);
      setNewQuestionImages([]);
      setOptionImages({});
      setEditing(false);
    } finally {
      setUploading(false);
    }
  };

  const handleCancel = () => {
    setEditData(question);
    setNewQuestionImages([]);
    setOptionImages({});
    setEditing(false);
  };

  const handleQuestionImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newImages: UploadedImage[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const preview = URL.createObjectURL(file);
      newImages.push({
        file,
        preview,
        id: `img_${Date.now()}_${i}`,
      });
    }
    setNewQuestionImages([...newQuestionImages, ...newImages]);
  };

  const handleOptionImageSelect = (optionLabel: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const preview = URL.createObjectURL(file);
    setOptionImages({
      ...optionImages,
      [optionLabel]: {
        file,
        preview,
        id: `opt_img_${optionLabel}_${Date.now()}`,
      }
    });
  };

  const removeNewQuestionImage = (id: string) => {
    setNewQuestionImages(newQuestionImages.filter(img => img.id !== id));
  };

  const removeExistingImage = (imageId: string) => {
    setEditData({
      ...editData,
      images: editData.images.filter(img => img.id !== imageId)
    });
  };

  const removeOptionImage = (optionLabel: string) => {
    const newImages = { ...optionImages };
    delete newImages[optionLabel];
    setOptionImages(newImages);
  };

  const handleOptionChange = (index: number, field: 'english_text' | 'hindi_text', value: string) => {
    const newOptions = [...editData.options];
    newOptions[index] = { ...newOptions[index], [field]: value };
    setEditData({ ...editData, options: newOptions });
  };

  const handleAddOption = () => {
    const labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
    const nextLabel = labels[editData.options.length] || `O${editData.options.length + 1}`;
    const newOption: Option = {
      label: nextLabel,
      english_text: '',
      hindi_text: ''
    };
    setEditData({ ...editData, options: [...editData.options, newOption] });
  };

  const handleRemoveOption = (index: number) => {
    if (editData.options.length <= 2) return; // Keep at least 2 options
    const newOptions = editData.options.filter((_, i) => i !== index);
    // Re-label options
    const labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
    const relabeledOptions = newOptions.map((opt, i) => ({
      ...opt,
      label: labels[i] || `O${i + 1}`
    }));
    setEditData({ ...editData, options: relabeledOptions });
  };

  const confidenceColor = question.confidence >= 0.8 ? '#4caf50' : 
                          question.confidence >= 0.5 ? '#ff9800' : '#f44336';

  const getFlagDescription = (flag: string): string => {
    const descriptions: Record<string, string> = {
      'EXTRA_OPTIONS': '⚠️ This question has more than 4 options. Please verify.',
      'MISSING_OPTIONS': '⚠️ This question has fewer than 4 options. Please add more.',
      'IMAGE_OPTIONS': '🖼️ Some options contain images.',
      'NO_OPTIONS': '❌ No options found. Please add options.',
      'MISSING_ENGLISH': '⚠️ English text is missing.',
      'MISSING_HINDI': '⚠️ Hindi text is missing.',
      'COUNT_MISMATCH': '⚠️ Question count mismatch between languages.',
      'LOW_CONFIDENCE': '⚠️ Low confidence in parsing. Please review carefully.',
      'needs_image': '🖼️ Question requires image - manual upload needed.',
      'options_need_images': '🖼️ Some options require images - manual upload needed.',
    };
    return descriptions[flag] || flag.replace(/_/g, ' ');
  };

  // Check if question or options need images
  const needsImageWarning = question.needs_image || question.flags.includes('needs_image');
  const optionsNeedImages = question.flags.includes('options_need_images') || 
    question.options.some(opt => opt.needs_image);

  return (
    <div className={`question-card ${question.flags.length > 0 ? 'has-flags' : ''} ${needsImageWarning || optionsNeedImages ? 'needs-image' : ''}`}>
      <div className="question-header" onClick={onToggle}>
        <div className="question-number">Q{question.id}</div>
        <div className="question-preview">
          {question.english_text.substring(0, 80)}...
          {(needsImageWarning || optionsNeedImages) && <span className="image-warning-icon" title="Needs image upload">🖼️</span>}
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
                <div key={i} className="flag-item">
                  <span className="flag-badge">{flag.replace(/_/g, ' ')}</span>
                  <span className="flag-description">{getFlagDescription(flag)}</span>
                </div>
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

              {/* Question Images Section */}
              <div className="edit-section">
                <label>Question Images:</label>
                <div className="image-upload-area">
                  <input
                    type="file"
                    ref={questionImageRef}
                    onChange={handleQuestionImageSelect}
                    accept="image/*"
                    multiple
                    style={{ display: 'none' }}
                  />
                  <button 
                    className="btn-upload-image"
                    onClick={() => questionImageRef.current?.click()}
                  >
                    📷 Add Image
                  </button>
                  
                  {/* Existing images */}
                  {editData.images && editData.images.length > 0 && (
                    <div className="image-previews">
                      {editData.images.map(img => (
                        <div key={img.id} className="image-preview-item existing">
                          <img src={`${API_URL}/jobs/${jobId}/images/${img.id}`} alt={img.filename} />
                          <button 
                            className="btn-remove-image"
                            onClick={() => removeExistingImage(img.id)}
                            title="Remove image"
                          >
                            ✕
                          </button>
                          <span className="image-label">Existing</span>
                        </div>
                      ))}
                    </div>
                  )}
                  
                  {/* New images to upload */}
                  {newQuestionImages.length > 0 && (
                    <div className="image-previews new-images">
                      {newQuestionImages.map(img => (
                        <div key={img.id} className="image-preview-item new">
                          <img src={img.preview} alt="Preview" />
                          <button 
                            className="btn-remove-image"
                            onClick={() => removeNewQuestionImage(img.id)}
                            title="Remove image"
                          >
                            ✕
                          </button>
                          <span className="image-label">New</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
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
                <label>Options ({editData.options.length}):</label>
                {editData.options.map((opt, i) => (
                  <div key={i} className="option-edit-row">
                    <span className="option-label">({opt.label})</span>
                    <div className="option-edit-inputs">
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
                      
                      {/* Option image upload */}
                      <input
                        type="file"
                        ref={el => { optionImageRefs.current[opt.label] = el; }}
                        onChange={(e) => handleOptionImageSelect(opt.label, e)}
                        accept="image/*"
                        style={{ display: 'none' }}
                      />
                      <button 
                        className="btn-option-image"
                        onClick={() => optionImageRefs.current[opt.label]?.click()}
                        title="Add image to this option"
                      >
                        📷
                      </button>
                      
                      {optionImages[opt.label] && (
                        <div className="option-image-preview">
                          <img src={optionImages[opt.label]!.preview} alt="Option" />
                          <button onClick={() => removeOptionImage(opt.label)}>✕</button>
                        </div>
                      )}
                      
                      <button 
                        className="btn-remove-option" 
                        onClick={() => handleRemoveOption(i)}
                        title="Remove option"
                        disabled={editData.options.length <= 2}
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                ))}
                <button className="btn-add-option" onClick={handleAddOption}>
                  + Add Option
                </button>
              </div>

              <div className="edit-section">
                <label>Answer:</label>
                <select
                  value={editData.answer || ''}
                  onChange={(e) => setEditData({ ...editData, answer: e.target.value })}
                >
                  <option value="">Select Answer</option>
                  {editData.options.map((opt) => (
                    <option key={opt.label} value={opt.label}>{opt.label}</option>
                  ))}
                </select>
              </div>

              <div className="edit-section">
                <label>Solution (English):</label>
                <textarea
                  value={editData.solution_english || ''}
                  onChange={(e) => setEditData({ ...editData, solution_english: e.target.value })}
                  rows={2}
                  placeholder="Enter solution explanation in English..."
                />
              </div>

              <div className="edit-section">
                <label>Solution (Hindi - हिंदी):</label>
                <textarea
                  value={editData.solution_hindi || ''}
                  onChange={(e) => setEditData({ ...editData, solution_hindi: e.target.value })}
                  rows={2}
                  placeholder="हिंदी में समाधान लिखें..."
                />
              </div>

              <div className="edit-section">
                <label>Grading (e.g., +4/-1):</label>
                <input
                  type="text"
                  value={editData.grading || ''}
                  onChange={(e) => setEditData({ ...editData, grading: e.target.value })}
                  placeholder="+4/-1"
                />
              </div>

              <div className="edit-actions">
                <button className="btn-save" onClick={handleSave} disabled={uploading}>
                  {uploading ? '⏳ Saving...' : '💾 Save'}
                </button>
                <button className="btn-cancel" onClick={handleCancel} disabled={uploading}>
                  Cancel
                </button>
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

              {/* Display question images */}
              {question.images && question.images.length > 0 && (
                <div className="question-images-display">
                  <strong>Images:</strong>
                  <div className="images-grid">
                    {question.images.map((img, i) => (
                      <div key={img.id || i} className="question-image-item">
                        <img 
                          src={`${API_URL}/jobs/${jobId}/images/${img.id}`} 
                          alt={img.filename || `Image ${i + 1}`}
                          onClick={() => window.open(`${API_URL}/jobs/${jobId}/images/${img.id}`, '_blank')}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="question-type">
                <strong>Type:</strong> {question.question_type.replace(/_/g, ' ')}
              </div>

              <div className="options-list">
                <strong>Options:</strong>
                {question.options.map((opt, i) => (
                  <div key={i} className={`option-item ${question.answer === opt.label ? 'correct-answer' : ''} ${opt.needs_image ? 'needs-image' : ''}`}>
                    <span className="option-label">({opt.label})</span>
                    <span className="option-english">
                      {opt.english_text}
                      {opt.needs_image && <span className="option-image-warning" title="This option needs an image">🖼️</span>}
                    </span>
                    <span className="option-hindi">({opt.hindi_text})</span>
                    {question.answer === opt.label && <span className="correct-badge">✓ Correct</span>}
                  </div>
                ))}
              </div>

              {question.answer && (
                <div className="answer-section">
                  <strong>Ans.</strong> {question.answer}
                </div>
              )}

              {(question.solution_english || question.solution_hindi) && (
                <div className="solution-section">
                  <strong>Sol:</strong>
                  {question.solution_english && (
                    <div className="solution-english">{question.solution_english}</div>
                  )}
                  {question.solution_hindi && (
                    <div className="solution-hindi">({question.solution_hindi})</div>
                  )}
                </div>
              )}

              {question.grading && (
                <div className="grading-section">
                  <strong>Grading:</strong> {question.grading}
                </div>
              )}

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
              {onDelete && (
                <button className="btn-delete" onClick={onDelete}>
                  🗑️ Delete
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default QuestionCard;
