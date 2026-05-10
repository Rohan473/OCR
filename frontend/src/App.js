import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from './components/ui/sonner';
import './App.css';
import 'katex/dist/katex.min.css';

// Pages
import Dashboard from './pages/Dashboard';
import Upload from './pages/Upload';
import Editor from './pages/Editor';
import Library from './pages/Library';
import NoteDetail from './pages/NoteDetail';
import Voice from './pages/Voice';
import Graph from './pages/Graph';
import { RagSidebar } from './components/RagSidebar';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry on 404s or 422s
        const status = error?.response?.status;
        if (status === 404 || status === 422) return false;
        return failureCount < 2;
      },
    },
  },
});

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
            <Route path="/voice" element={<Voice />} />
            <Route path="/graph" element={<Graph />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          <RagSidebar />
          <Toaster position="bottom-right" />
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;
