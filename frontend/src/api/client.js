import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getImagePreviewUrl = (imagePath) => {
  if (!imagePath) return '';
  return `${API_BASE_URL}/images?path=${encodeURIComponent(imagePath)}`;
};

export const pdfPagesAPI = {
  getPages: async (path, maxPages = 15) => {
    const response = await api.get('/pdf/pages', { params: { path, max_pages: maxPages } });
    return response.data;
  },
};

// OCR API
export const ocrAPI = {
  uploadImage: async (file, engine = 'tesseract', language = 'eng', preprocess = true) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('engine', engine);
    formData.append('language', language);
    formData.append('preprocess', String(preprocess));

    const response = await api.post('/ocr/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });
    return response.data;
  },

  // image_id: UUID string (extracted from full path if needed)
  processOCR: async (imageIdOrPath, engine = 'tesseract', language = 'eng', preprocess = true) => {
    // Extract just the UUID filename if a full path was passed
    const parts = imageIdOrPath.replace(/\\/g, '/').split('/');
    const filename = parts[parts.length - 1];
    const imageId = filename.includes('.') ? filename.split('.')[0] : filename;

    const response = await api.post('/ocr/process', {
      image_id: imageId,
      engine,
      language,
      preprocess,
    });
    return response.data;
  },

  batchOCR: async (files, engine = 'tesseract', language = 'eng', preprocess = true) => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    formData.append('engine', engine);
    formData.append('language', language);
    formData.append('preprocess', String(preprocess));

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
    formData.append('searchable', String(searchable));

    const response = await api.post('/pdf/generate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  downloadPDF: (filename) => `${API_BASE_URL}/pdf/download/${filename}`,
};

// RAG API
export const ragAPI = {
  query: async (question, history = [], folderId = null) => {
    const response = await api.post('/rag/query', { question, history, folder_id: folderId }, { timeout: 60000 });
    return response.data;
  },

  reindex: async () => {
    const response = await api.post('/rag/reindex');
    return response.data;
  },

  getStats: async () => {
    const response = await api.get('/rag/stats');
    return response.data;
  },
};

// Voice API
export const voiceAPI = {
  uploadAudio: async (file, language = 'en', folderId = null) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);
    if (folderId) formData.append('folder_id', folderId);

    const response = await api.post('/voice/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return response.data;
  },

  getRecordings: async (folderId = null) => {
    const params = folderId ? { folder_id: folderId } : {};
    const response = await api.get('/voice/recordings', { params });
    return response.data;
  },

  getRecording: async (recordingId) => {
    const response = await api.get(`/voice/recordings/${recordingId}`);
    return response.data;
  },

  deleteRecording: async (recordingId) => {
    const response = await api.delete(`/voice/recordings/${recordingId}`);
    return response.data;
  },

  relinkRecording: async (recordingId, noteId) => {
    const response = await api.patch(`/voice/recordings/${recordingId}/link`, { note_id: noteId });
    return response.data;
  },
};

// Tabular Extraction API
export const extractAPI = {
  extractTable: async (query, columns = []) => {
    const response = await api.post('/extract/table', { query, columns });
    return response.data;
  },

  extractDefinitions: async () => {
    const response = await api.post('/extract/definitions');
    return response.data;
  },

  extractFormulas: async () => {
    const response = await api.post('/extract/formulas');
    return response.data;
  },

  extractKeyPoints: async () => {
    const response = await api.post('/extract/keypoints');
    return response.data;
  },

  extractDates: async () => {
    const response = await api.post('/extract/dates');
    return response.data;
  },
};

// Graph / Cluster / Progress API
export const graphAPI = {
  getGraph: async (folderId = null, maxNodes = 100) => {
    const params = { max_nodes: maxNodes };
    if (folderId) params.folder_id = folderId;
    const response = await api.get('/graph/knowledge', { params });
    return response.data;
  },

  getClusters: async (folderId = null, maxK = 8) => {
    const params = { max_k: maxK };
    if (folderId) params.folder_id = folderId;
    const response = await api.get('/graph/clusters', { params });
    return response.data;
  },

  getProgress: async (folderId = null) => {
    const params = folderId ? { folder_id: folderId } : {};
    const response = await api.get('/progress', { params });
    return response.data;
  },
};

export default api;
