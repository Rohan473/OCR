import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  ArrowLeft, Download, Edit, Trash2, FileText,
  Calendar, Sparkles, Copy, Check, BookOpen, Hash,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../components/ui/alert-dialog';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { notesAPI, pdfAPI } from '../api/client';
import { MarkdownView } from '../components/MarkdownView';
import { PdfPageList } from '../components/PdfPageList';

export const NoteDetail = () => {
  const { noteId } = useParams();
  const navigate = useNavigate();
  const [copied, setCopied] = useState(false);

  const { data: note, isLoading } = useQuery({
    queryKey: ['note', noteId],
    queryFn: () => notesAPI.getNote(noteId),
  });

  const handleDownloadPDF = async () => {
    if (!note) return;
    try {
      toast.info('Generating PDF…');
      const result = await pdfAPI.generatePDF(note.original_image_path, note.transcribed_text, true);
      window.open(pdfAPI.downloadPDF(result.filename), '_blank');
      toast.success('PDF ready');
    } catch {
      toast.error('PDF generation failed');
    }
  };

  const handleDelete = async () => {
    try {
      await notesAPI.deleteNote(noteId);
      toast.success('Note deleted');
      navigate('/library');
    } catch {
      toast.error('Failed to delete note');
    }
  };

  const handleCopy = () => {
    if (!note?.transcribed_text) return;
    navigator.clipboard.writeText(note.transcribed_text);
    setCopied(true);
    toast.success('Copied to clipboard');
    setTimeout(() => setCopied(false), 2000);
  };

  const wordCount = note?.transcribed_text?.split(/\s+/).filter(Boolean).length ?? 0;
  const charCount = note?.transcribed_text?.length ?? 0;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background">
        <header className="sticky top-0 z-50 w-full border-b backdrop-blur-xl bg-background/80">
          <div className="container flex h-16 items-center justify-between">
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-8 w-32" />
          </div>
        </header>
        <main className="container py-8 max-w-4xl mx-auto space-y-6">
          <div className="space-y-4">
            <Skeleton className="h-10 w-3/4" />
            <div className="flex gap-3">
              <Skeleton className="h-6 w-28" />
              <Skeleton className="h-6 w-36" />
            </div>
          </div>
          <Skeleton className="h-64 w-full rounded-xl" />
          <div className="grid grid-cols-3 gap-4">
            {[1,2,3].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
          </div>
        </main>
      </div>
    );
  }

  if (!note) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="inline-flex p-4 rounded-2xl bg-muted">
            <FileText className="w-12 h-12 text-muted-foreground" />
          </div>
          <p className="text-lg font-medium">Note not found</p>
          <Button onClick={() => navigate('/library')}>Back to Library</Button>
        </div>
      </div>
    );
  }

  const confidencePct = Math.round((note.confidence || 0) * 100);
  const confidenceColor = confidencePct >= 80 ? 'bg-green-100 text-green-700' : confidencePct >= 50 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700';

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        {/* Glassmorphism header */}
        <header className="sticky top-0 z-50 w-full border-b backdrop-blur-xl bg-background/80">
          <div className="container flex h-16 items-center justify-between">
            <Button variant="ghost" size="sm" onClick={() => navigate('/library')} data-testid="back-to-library-btn">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Library
            </Button>
            <h1 className="text-lg font-semibold truncate max-w-xs">{note.title}</h1>
            <div className="flex items-center gap-1.5">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="outline" size="sm" onClick={handleDownloadPDF} data-testid="download-pdf-btn">
                    <Download className="w-4 h-4" />
                    <span className="sr-only">Download PDF</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Download as PDF</TooltipContent>
              </Tooltip>
              <Button variant="outline" size="sm" onClick={() => navigate(`/editor/${noteId}`, { state: { note } })}>
                <Edit className="w-4 h-4 mr-1.5" />
                Edit
              </Button>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button variant="destructive" size="sm" data-testid="delete-note-btn">
                    <Trash2 className="w-4 h-4" />
                    <span className="sr-only">Delete note</span>
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Delete &ldquo;{note.title}&rdquo;?</AlertDialogTitle>
                    <AlertDialogDescription>
                      This note will be permanently deleted and cannot be recovered.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Cancel</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      onClick={handleDelete}
                    >
                      Delete note
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </div>
        </header>

        <main className="container py-8 max-w-4xl mx-auto px-4">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="space-y-6"
          >
            {/* Note title + meta pills */}
            <div className="space-y-3">
              <h1 className="text-3xl font-semibold tracking-tight">{note.title}</h1>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="outline" className="gap-1.5 text-xs font-normal">
                  <Calendar className="w-3 h-3" />
                  {new Date(note.created_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}
                </Badge>
                <Badge variant="outline" className="gap-1.5 text-xs font-normal">
                  <Sparkles className="w-3 h-3" />
                  {note.engine}
                </Badge>
                <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${confidenceColor}`}>
                  {confidencePct}% confidence
                </span>
                {note.language && (
                  <Badge variant="secondary" className="text-xs font-normal uppercase">{note.language}</Badge>
                )}
              </div>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              <StatCard icon={Hash} label="Words" value={wordCount.toLocaleString()} />
              <StatCard icon={FileText} label="Characters" value={charCount.toLocaleString()} />
              <StatCard icon={BookOpen} label="Reading time" value={`~${Math.max(1, Math.ceil(wordCount / 200))} min`} />
            </div>

            {/* Transcribed text */}
            <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b bg-muted/30">
                <h2 className="text-sm font-medium">Transcribed Text</h2>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="ghost" className="h-7 px-2" onClick={handleCopy}>
                      {copied ? <Check className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                      <span className="ml-1.5 text-xs">{copied ? 'Copied' : 'Copy'}</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Copy to clipboard</TooltipContent>
                </Tooltip>
              </div>
              <div className="p-5">
                <MarkdownView className="text-foreground/90">
                  {note.transcribed_text}
                </MarkdownView>
              </div>
            </div>

            {/* Original source (image or all PDF pages) */}
            {note.original_image_path && (
              <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
                <div className="px-5 py-3 border-b bg-muted/30">
                  <h2 className="text-sm font-medium">
                    {note.original_image_path.toLowerCase().endsWith('.pdf')
                      ? 'Original PDF'
                      : 'Original Image'}
                  </h2>
                </div>
                <div className="max-h-[80vh] overflow-y-auto">
                  <PdfPageList
                    sourcePath={note.original_image_path}
                    fallbackPath={note.processed_image_path}
                  />
                </div>
              </div>
            )}
          </motion.div>
        </main>
      </div>
    </TooltipProvider>
  );
};

const StatCard = ({ icon: Icon, label, value }) => (
  <div className="rounded-xl border bg-card p-4 shadow-sm flex items-center gap-3">
    <div className="p-2 rounded-lg bg-primary/10 flex-shrink-0">
      <Icon className="w-4 h-4 text-primary" />
    </div>
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-lg font-semibold leading-tight">{value}</p>
    </div>
  </div>
);

export default NoteDetail;
