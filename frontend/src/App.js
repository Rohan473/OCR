import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from './components/ui/sonner';
import './App.css';

// Pages
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Editor from './pages/Editor';
import Library from './pages/Library';
import NoteDetail from './pages/NoteDetail';

const queryClient = new QueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="App min-h-screen bg-background">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<Upload />} />
            <Route path="/editor/:imageId" element={<Editor />} />
            <Route path="/library" element={<Library />} />
            <Route path="/note/:noteId" element={<NoteDetail />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <Toaster position="bottom-right" />
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
