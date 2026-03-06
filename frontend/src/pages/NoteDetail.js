import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { ArrowLeft, Download, Edit, Trash2, FileText, Calendar, Sparkles } from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import { notesAPI, pdfAPI } from '../api/client';

export const NoteDetail = () => {
  const { noteId } = useParams();
  const navigate = useNavigate();

  const { data: note, isLoading } = useQuery({
    queryKey: ['note', noteId],
    queryFn: () => notesAPI.getNote(noteId),
  });

  const handleDownloadPDF = async () => {
    if (!note) return;

    try {
      toast.info('Generating PDF...');
      const result = await pdfAPI.generatePDF(
        note.original_image_path,
        note.transcribed_text,
        true
      );
      
      const downloadUrl = pdfAPI.downloadPDF(result.filename);
      window.open(downloadUrl, '_blank');
      
      toast.success('PDF generated successfully!');
    } catch (error) {
      toast.error('PDF generation failed');
    }
  };

  const handleDelete = async () => {
    try {
      await notesAPI.deleteNote(noteId);
      toast.success('Note deleted');
      navigate('/library');
    } catch (error) {
      toast.error('Failed to delete note');
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <p className="text-muted-foreground">Loading note...</p>
      </div>
    );
  }

  if (!note) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <FileText className="w-16 h-16 mx-auto text-muted-foreground" />
          <p className="text-lg font-medium">Note not found</p>
          <Button onClick={() => navigate('/library')}>Back to Library</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => navigate('/library')}
            data-testid="back-to-library-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Library
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleDownloadPDF}
              data-testid="download-pdf-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              PDF
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(`/editor/${noteId}`, { state: { note } })}
            >
              <Edit className="w-4 h-4 mr-2" />
              Edit
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              data-testid="delete-note-btn"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container py-8 max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="space-y-8"
        >
          {/* Note Header */}
          <div className="space-y-4">
            <h1 className="text-4xl font-semibold tracking-tight">{note.title}</h1>
            
            <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4" />
                {new Date(note.created_at).toLocaleDateString('en-US', {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}
              </div>
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4" />
                {note.engine} • {(note.confidence * 100).toFixed(1)}% confidence
              </div>
            </div>
          </div>

          {/* Transcribed Text */}
          <div className="rounded-xl border bg-card p-8 shadow-sm">
            <h2 className="text-xl font-medium mb-4">Transcribed Text</h2>
            <div className="prose prose-zinc max-w-none">
              <p className="whitespace-pre-wrap font-mono text-sm leading-relaxed">
                {note.transcribed_text}
              </p>
            </div>
          </div>

          {/* Metadata */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <MetadataCard
              label="Characters"
              value={note.transcribed_text.length}
            />
            <MetadataCard
              label="Words"
              value={note.transcribed_text.split(/\s+/).filter(Boolean).length}
            />
            <MetadataCard
              label="Language"
              value={note.language}
            />
          </div>
        </motion.div>
      </main>
    </div>
  );
};

const MetadataCard = ({ label, value }) => {
  return (
    <div className="rounded-lg border bg-card p-4 shadow-sm">
      <p className="text-sm text-muted-foreground mb-1">{label}</p>
      <p className="text-2xl font-semibold">{value}</p>
    </div>
  );
};

export default NoteDetail;
