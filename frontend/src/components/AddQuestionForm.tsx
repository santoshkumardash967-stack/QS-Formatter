import React, { useState, useRef } from 'react';
import type { Question, QuestionType, Option, ImageData } from '../types';

// Detect API URL for Codespaces or local development
const getApiUrl = () => {
  if (typeof window !== 'undefined' && window.location.hostname.includes('github.dev')) {
    return window.location.origin.replace('5173', '8000');
  }
  if (typeof window !== 'undefined' && window.location.hostname.includes('app.github.dev')) {
    return window.location.origin.replace('5173', '8000');
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

interface AddQuestionFormProps {
  jobId: string;
  nextId: number;
  onAdd: (question: Question) => void;
  onCancel: () => void;
}

interface UploadedImage {
  file: File;
  preview: string;
  id: string;
  uploaded?: ImageData;
}

const AddQuestionForm: React.FC<AddQuestionFormProps> = ({
  jobId,
  nextId,
  onAdd,
  onCancel,
}) => {
  const [formData, setFormData] = useState({
    english_text: '',
    hindi_text: '',
    question_type: 'multiple_choice' as QuestionType,
    answer: '',
    solution_english: '',
    solution_hindi: '',
    grading: '+4/-1',
  });

  const [options, setOptions] = useState<Option[]>([
    { label: 'A', english_text: '', hindi_text: '' },
    { label: 'B', english_text: '', hindi_text: '' },
    { label: 'C', english_text: '', hindi_text: '' },
    { label: 'D', english_text: '', hindi_text: '' },
  ]);

  const [questionImages, setQuestionImages] = useState<UploadedImage[]>([]);
  const [optionImages, setOptionImages] = useState<Record<string, UploadedImage | null>>({});
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const questionImageRef = useRef<HTMLInputElement>(null);
  const optionImageRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const handleOptionChange = (index: number, field: 'english_text' | 'hindi_text', value: string) => {
    const newOptions = [...options];
    newOptions[index] = { ...newOptions[index], [field]: value };
    setOptions(newOptions);
  };

  const handleAddOption = () => {
    const labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
    const nextLabel = labels[options.length] || `O${options.length + 1}`;
    setOptions([...options, { label: nextLabel, english_text: '', hindi_text: '' }]);
  };

  const handleRemoveOption = (index: number) => {
    if (options.length <= 2) return;
    const newOptions = options.filter((_, i) => i !== index);
    const labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'];
    const relabeledOptions = newOptions.map((opt, i) => ({
      ...opt,
      label: labels[i] || `O${i + 1}`
    }));
    setOptions(relabeledOptions);
    
    // Clear any answer selection if removed option was selected
    if (formData.answer && !relabeledOptions.find(o => o.label === formData.answer)) {
      setFormData({ ...formData, answer: '' });
    }
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
    setQuestionImages([...questionImages, ...newImages]);
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

  const removeQuestionImage = (id: string) => {
    setQuestionImages(questionImages.filter(img => img.id !== id));
  };

  const removeOptionImage = (optionLabel: string) => {
    const newImages = { ...optionImages };
    delete newImages[optionLabel];
    setOptionImages(newImages);
  };

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

  const handleSubmit = async () => {
    // Validate
    if (!formData.english_text.trim() && !formData.hindi_text.trim()) {
      setError('Please enter question text (English or Hindi)');
      return;
    }

    if (formData.question_type === 'multiple_choice' && options.filter(o => o.english_text || o.hindi_text).length < 2) {
      setError('Please enter at least 2 options for multiple choice questions');
      return;
    }

    setUploading(true);
    setError(null);

    try {
      // Upload question images
      const uploadedQuestionImages: ImageData[] = [];
      for (const img of questionImages) {
        const uploaded = await uploadImage(img.file);
        if (uploaded) {
          uploadedQuestionImages.push(uploaded);
        }
      }

      // Upload option images and update options
      const updatedOptions = [...options];
      for (let i = 0; i < updatedOptions.length; i++) {
        const opt = updatedOptions[i];
        const optImage = optionImages[opt.label];
        if (optImage) {
          const uploaded = await uploadImage(optImage.file);
          if (uploaded) {
            // Add image reference to option text
            updatedOptions[i] = {
              ...opt,
              english_text: opt.english_text + (opt.english_text ? ' ' : '') + `[Image: ${uploaded.filename}]`,
            };
          }
        }
      }

      // Create the question object
      const newQuestion: Question = {
        id: nextId,
        english_text: formData.english_text,
        hindi_text: formData.hindi_text,
        question_type: formData.question_type,
        options: updatedOptions.filter(o => o.english_text || o.hindi_text),
        tables: [],
        images: uploadedQuestionImages,
        answer: formData.answer || undefined,
        solution_english: formData.solution_english || undefined,
        solution_hindi: formData.solution_hindi || undefined,
        grading: formData.grading || undefined,
        confidence: 1.0,
        flags: [],
      };

      onAdd(newQuestion);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add question');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="add-question-form">
      <div className="form-header">
        <h2>➕ Add New Question (Q{nextId})</h2>
        <button className="btn-close" onClick={onCancel}>✕</button>
      </div>

      {error && (
        <div className="form-error">
          ⚠️ {error}
        </div>
      )}

      <div className="form-body">
        {/* Question Text */}
        <div className="form-section">
          <label>English Question:</label>
          <textarea
            value={formData.english_text}
            onChange={(e) => setFormData({ ...formData, english_text: e.target.value })}
            rows={3}
            placeholder="Enter question in English..."
          />
        </div>

        <div className="form-section">
          <label>Hindi Question (हिंदी):</label>
          <textarea
            value={formData.hindi_text}
            onChange={(e) => setFormData({ ...formData, hindi_text: e.target.value })}
            rows={3}
            placeholder="हिंदी में प्रश्न लिखें..."
          />
        </div>

        {/* Question Images */}
        <div className="form-section">
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
            
            {questionImages.length > 0 && (
              <div className="image-previews">
                {questionImages.map(img => (
                  <div key={img.id} className="image-preview-item">
                    <img src={img.preview} alt="Preview" />
                    <button 
                      className="btn-remove-image"
                      onClick={() => removeQuestionImage(img.id)}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Question Type */}
        <div className="form-section">
          <label>Question Type:</label>
          <select
            value={formData.question_type}
            onChange={(e) => setFormData({ ...formData, question_type: e.target.value as QuestionType })}
          >
            <option value="multiple_choice">Multiple Choice</option>
            <option value="integer">Integer</option>
            <option value="fill_ups">Fill in the Blanks</option>
            <option value="true_false">True/False</option>
          </select>
        </div>

        {/* Options */}
        {formData.question_type === 'multiple_choice' && (
          <div className="form-section">
            <label>Options ({options.length}):</label>
            {options.map((opt, i) => (
              <div key={i} className="option-input-row">
                <span className="option-label">({opt.label})</span>
                <div className="option-inputs">
                  <input
                    type="text"
                    placeholder="English option"
                    value={opt.english_text}
                    onChange={(e) => handleOptionChange(i, 'english_text', e.target.value)}
                  />
                  <input
                    type="text"
                    placeholder="हिंदी विकल्प"
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
                    disabled={options.length <= 2}
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
        )}

        {/* Answer */}
        <div className="form-section">
          <label>Correct Answer:</label>
          {formData.question_type === 'multiple_choice' ? (
            <select
              value={formData.answer}
              onChange={(e) => setFormData({ ...formData, answer: e.target.value })}
            >
              <option value="">Select Answer</option>
              {options.map((opt) => (
                <option key={opt.label} value={opt.label}>{opt.label}</option>
              ))}
            </select>
          ) : (
            <input
              type="text"
              value={formData.answer}
              onChange={(e) => setFormData({ ...formData, answer: e.target.value })}
              placeholder="Enter answer..."
            />
          )}
        </div>

        {/* Solution */}
        <div className="form-section">
          <label>Solution (English):</label>
          <textarea
            value={formData.solution_english}
            onChange={(e) => setFormData({ ...formData, solution_english: e.target.value })}
            rows={3}
            placeholder="Enter solution explanation in English..."
          />
        </div>

        <div className="form-section">
          <label>Solution (Hindi - हिंदी):</label>
          <textarea
            value={formData.solution_hindi}
            onChange={(e) => setFormData({ ...formData, solution_hindi: e.target.value })}
            rows={3}
            placeholder="हिंदी में समाधान लिखें..."
          />
        </div>

        {/* Grading */}
        <div className="form-section">
          <label>Grading (e.g., +4/-1):</label>
          <input
            type="text"
            value={formData.grading}
            onChange={(e) => setFormData({ ...formData, grading: e.target.value })}
            placeholder="+4/-1"
          />
        </div>
      </div>

      <div className="form-actions">
        <button 
          className="btn-add-question" 
          onClick={handleSubmit}
          disabled={uploading}
        >
          {uploading ? '⏳ Adding...' : '✅ Add Question'}
        </button>
        <button className="btn-cancel" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
};

export default AddQuestionForm;
