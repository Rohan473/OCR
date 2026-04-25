import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getImagePreviewUrl = (imagePath) => {
  if (!imagePath) {
    return '';
  }

  const encodedPath = encodeURIComponent(imagePath);
  return `${API_BASE_URL}/images?image_path=${encodedPath}`;
};

// OCR API
export const ocrAPI = {
  uploadImage: async (file, preprocess = true) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('preprocess', preprocess);

    const response = await api.post('/ocr/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000, // 5 min — large PDFs take time
    });
    return response.data;
  },

  processOCR: async (imagePath, engine = 'trocr', language = 'eng', preprocess = true) => {
    const formData = new FormData();
    formData.append('image_path', imagePath);
    formData.append('engine', engine);
    formData.append('language', language);
    formData.append('preprocess', preprocess);
    
    const response = await api.post('/ocr/process', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  batchOCR: async (files, engine = 'trocr', language = 'eng', preprocess = true) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('engine', engine);
    formData.append('language', language);
    formData.append('preprocess', preprocess);
    
    const response = await api.post('/ocr/batch', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },
};

// Notes API
export const notesAPI = {
  createNote: async (noteData) => {
    const response = await api.post('/notes', noteData);
    return response.data;
  },

  getNotes: async (folderId = null, limit = 100) => {
    const params = { limit };
    if (folderId) params.folder_id = folderId;
    
    const response = await api.get('/notes', { params });
    return response.data;
  },

  getNote: async (noteId) => {
    const response = await api.get(`/notes/${noteId}`);
    return response.data;
  },

  updateNote: async (noteId, updateData) => {
    const response = await api.patch(`/notes/${noteId}`, updateData);
    return response.data;
  },

  deleteNote: async (noteId) => {
    const response = await api.delete(`/notes/${noteId}`);
    return response.data;
  },
};

// Folders API
export const foldersAPI = {
  createFolder: async (folderData) => {
    const response = await api.post('/folders', folderData);
    return response.data;
  },

  getFolders: async () => {
    const response = await api.get('/folders');
    return response.data;
  },

  deleteFolder: async (folderId) => {
    const response = await api.delete(`/folders/${folderId}`);
    return response.data;
  },
};

// Search API
export const searchAPI = {
  searchNotes: async (query, folderId = null) => {
    const response = await api.post('/search', { query, folder_id: folderId });
    return response.data;
  },
};

// PDF API
export const pdfAPI = {
  generatePDF: async (imagePath, text, searchable = true) => {
    const formData = new FormData();
    formData.append('image_path', imagePath);
    formData.append('text', text);
    formData.append('searchable', searchable);
    
    const response = await api.post('/pdf/generate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  downloadPDF: (filename) => {
    return `${API_BASE_URL}/pdf/download/${filename}`;
  },
};

// RAG API
export const ragAPI = {
  query: async (question, history = [], folderId = null) => {
    const response = await api.post('/rag/query', {
      question,
      history,
      folder_id: folderId,
    });
    return response.data;
  },

  reindex: async () => {
    const response = await api.post('/rag/reindex');
    return response.data;
  },
};

export default api;
