import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Search, Upload, FolderPlus, Trash2, FileText, Calendar, ArrowLeft } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { toast } from 'sonner';
import { notesAPI, foldersAPI, searchAPI } from '../api/client';

export const Library = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFolder, setSelectedFolder] = useState(null);

  // Fetch notes
  const { data: notes = [], isLoading, refetch } = useQuery({
    queryKey: ['notes', selectedFolder],
    queryFn: () => notesAPI.getNotes(selectedFolder),
  });

  // Fetch folders
  const { data: folders = [] } = useQuery({
    queryKey: ['folders'],
    queryFn: () => foldersAPI.getFolders(),
  });

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      refetch();
      return;
    }

    try {
      const result = await searchAPI.searchNotes(searchQuery, selectedFolder);
      // Update notes with search results
      // Note: This is a simplified version; in production, you'd use proper state management
      toast.success(`Found ${result.count} result(s)`);
    } catch (error) {
      toast.error('Search failed');
    }
  };

  const handleDeleteNote = async (noteId) => {
    try {
      await notesAPI.deleteNote(noteId);
      toast.success('Note deleted');
      refetch();
    } catch (error) {
      toast.error('Failed to delete note');
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => navigate('/')}
            data-testid="back-home-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Home
          </Button>
          <h1 className="text-xl font-semibold">Library</h1>
          <Button
            onClick={() => navigate('/upload')}
            data-testid="upload-new-btn"
          >
            <Upload className="w-4 h-4 mr-2" />
            Upload
          </Button>
        </div>
      </header>

      <div className="container py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Sidebar - Folders */}
          <aside className="lg:col-span-3 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Folders</h2>
              <Button size="sm" variant="ghost">
                <FolderPlus className="w-4 h-4" />
              </Button>
            </div>
            
            <div className="space-y-2">
              <Button
                variant={selectedFolder === null ? 'secondary' : 'ghost'}
                className="w-full justify-start"
                onClick={() => setSelectedFolder(null)}
              >
                <FileText className="w-4 h-4 mr-2" />
                All Notes
              </Button>
              
              {folders.map((folder) => (
                <Button
                  key={folder.id}
                  variant={selectedFolder === folder.id ? 'secondary' : 'ghost'}
                  className="w-full justify-start"
                  onClick={() => setSelectedFolder(folder.id)}
                >
                  <div
                    className="w-3 h-3 rounded-full mr-2"
                    style={{ backgroundColor: folder.color }}
                  />
                  {folder.name}
                </Button>
              ))}
            </div>
          </aside>

          {/* Main Content */}
          <main className="lg:col-span-9 space-y-6">
            {/* Search Bar */}
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Search notes..."
                  className="pl-10"
                  data-testid="search-input"
                />
              </div>
              <Button onClick={handleSearch}>Search</Button>
            </div>

            {/* Notes Grid */}
            {isLoading ? (
              <div className="text-center py-12 text-muted-foreground">
                Loading notes...
              </div>
            ) : notes.length === 0 ? (
              <div className="text-center py-12 space-y-4">
                <FileText className="w-16 h-16 mx-auto text-muted-foreground" />
                <div>
                  <p className="text-lg font-medium">No notes yet</p>
                  <p className="text-sm text-muted-foreground">
                    Upload your first handwritten note to get started
                  </p>
                </div>
                <Button onClick={() => navigate('/upload')}>
                  <Upload className="w-4 h-4 mr-2" />
                  Upload Notes
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                {notes.map((note, index) => (
                  <NoteCard
                    key={note.id}
                    note={note}
                    index={index}
                    onClick={() => navigate(`/note/${note.id}`)}
                    onDelete={() => handleDeleteNote(note.id)}
                  />
                ))}
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

const NoteCard = ({ note, index, onClick, onDelete }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className="group bg-card rounded-xl border shadow-sm hover:shadow-md transition-shadow cursor-pointer"
      onClick={onClick}
      data-testid={`note-card-${note.id}`}
    >
      <div className="aspect-[4/3] bg-muted rounded-t-xl overflow-hidden">
        {note.original_image_path ? (
          <div className="w-full h-full bg-gradient-to-br from-zinc-100 to-zinc-200 flex items-center justify-center">
            <FileText className="w-12 h-12 text-zinc-400" />
          </div>
        ) : (
          <div className="w-full h-full bg-muted" />
        )}
      </div>
      
      <div className="p-4 space-y-2">
        <h3 className="font-medium truncate">{note.title}</h3>
        <p className="text-sm text-muted-foreground line-clamp-2">
          {note.transcribed_text}
        </p>
        
        <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            {new Date(note.created_at).toLocaleDateString()}
          </div>
          <div className="flex items-center gap-2">
            <span>{(note.confidence * 100).toFixed(0)}%</span>
            <Button
              size="sm"
              variant="ghost"
              className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
            >
              <Trash2 className="w-3 h-3" />
            </Button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default Library;
