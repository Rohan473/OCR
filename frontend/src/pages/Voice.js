import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft, Mic, Trash2, Link, FileText, Clock, Loader2,
  FolderOpen, ChevronDown, Check,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { Button } from '../components/ui/button';
import { Skeleton } from '../components/ui/skeleton';
import { toast } from 'sonner';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { voiceAPI, foldersAPI } from '../api/client';

export const Voice = () => {
  const navigate = useNavigate();
  const [uploading, setUploading] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState(null);

  const { data: foldersData } = useQuery({
    queryKey: ['folders'],
    queryFn: foldersAPI.getFolders,
  });
  const folders = foldersData || [];

  const { data: recordingsData, isLoading, refetch } = useQuery({
    queryKey: ['recordings', selectedFolder],
    queryFn: () => voiceAPI.getRecordings(selectedFolder),
  });

  const recordings = recordingsData?.recordings || [];

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setUploading(true);
    try {
      toast.info(`Transcribing ${file.name}…`);
      const result = await voiceAPI.uploadAudio(file, 'en', selectedFolder);
      if (result.success) {
        toast.success(`Transcribed: ${result.word_count} words`);
        refetch();
      }
    } catch (error) {
      toast.error('Transcription failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
    }
  }, [refetch, selectedFolder]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'audio/*': ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm'] },
    multiple: false,
    disabled: uploading,
  });

  const handleDelete = async (recordingId) => {
    try {
      await voiceAPI.deleteRecording(recordingId);
      toast.success('Recording deleted');
      refetch();
    } catch {
      toast.error('Failed to delete recording');
    }
  };

  const selectedFolderObj = folders.find(f => f.id === selectedFolder);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b backdrop-blur-xl bg-background/80">
        <div className="container flex h-16 items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => navigate('/library')} data-testid="back-library-btn">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Library
          </Button>
          <h1 className="text-lg font-semibold">Voice Notes</h1>
          <div className="w-20" />
        </div>
      </header>

      <main className="container py-10 md:py-14 max-w-3xl mx-auto space-y-8 px-4">

        {/* Folder selector */}
        <div className="flex items-center gap-3">
          <FolderOpen className="w-4 h-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Folder:</span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm" className="gap-2">
                {selectedFolderObj ? (
                  <>
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: selectedFolderObj.color }}
                    />
                    {selectedFolderObj.name}
                  </>
                ) : (
                  'All Recordings'
                )}
                <ChevronDown className="w-3 h-3 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" className="w-52">
              <DropdownMenuItem onClick={() => setSelectedFolder(null)}>
                <span className="flex-1">All Recordings</span>
                {!selectedFolder && <Check className="w-4 h-4 ml-2" />}
              </DropdownMenuItem>
              {folders.length > 0 && <DropdownMenuSeparator />}
              {folders.map(f => (
                <DropdownMenuItem key={f.id} onClick={() => setSelectedFolder(f.id)}>
                  <span
                    className="w-2.5 h-2.5 rounded-full mr-2 flex-shrink-0"
                    style={{ backgroundColor: f.color }}
                  />
                  <span className="flex-1 truncate">{f.name}</span>
                  {selectedFolder === f.id && <Check className="w-4 h-4 ml-2" />}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          {selectedFolder && (
            <span className="text-xs text-muted-foreground">
              Upload will be saved to this folder
            </span>
          )}
        </div>

        {/* Drop zone */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div
            {...getRootProps()}
            data-testid="voice-dropzone"
            className={`
              relative border-2 border-dashed rounded-2xl p-12 text-center transition-colors duration-200
              ${uploading
                ? 'border-border opacity-60 cursor-not-allowed'
                : isDragActive
                  ? 'border-orange-400 bg-orange-500/5 cursor-copy'
                  : 'border-border hover:border-orange-400/60 hover:bg-orange-500/5 cursor-pointer'}
            `}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-4">
              <motion.div
                animate={!isDragActive && !uploading ? { scale: [1, 1.06, 1] } : {}}
                transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
                className="p-4 rounded-2xl bg-orange-50"
              >
                {uploading ? (
                  <Loader2 className="w-8 h-8 text-orange-500 animate-spin" />
                ) : (
                  <Mic className="w-8 h-8 text-orange-500" strokeWidth={1.5} />
                )}
              </motion.div>
              <div>
                <p className="text-base font-medium mb-1">
                  {uploading
                    ? 'Transcribing audio…'
                    : isDragActive
                      ? 'Drop your audio file here'
                      : 'Drag & drop an audio recording'}
                </p>
                <p className="text-sm text-muted-foreground">
                  or click to browse · MP3, WAV, M4A, OGG, FLAC · max 50 MB
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Recordings list */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
              Recordings {recordings.length > 0 && `(${recordings.length})`}
            </h2>
          </div>

          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="rounded-xl border bg-card p-4 space-y-3">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 space-y-2">
                      <Skeleton className="h-4 w-1/2" />
                      <Skeleton className="h-3 w-1/3" />
                    </div>
                    <Skeleton className="h-8 w-16 rounded-lg" />
                  </div>
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-4/5" />
                </div>
              ))}
            </div>
          ) : recordings.length === 0 ? (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="text-center py-16 space-y-4 border border-dashed rounded-2xl"
            >
              <div className="inline-flex p-4 rounded-2xl bg-orange-50">
                <Mic className="w-10 h-10 text-orange-400" strokeWidth={1.5} />
              </div>
              <div>
                <p className="text-base font-medium">No recordings yet</p>
                <p className="text-sm text-muted-foreground mt-1">
                  {selectedFolder
                    ? 'No recordings in this folder. Upload one above or switch folders.'
                    : 'Upload an audio file above to transcribe and link it to your notes'}
                </p>
              </div>
            </motion.div>
          ) : (
            <AnimatePresence>
              <div className="space-y-3">
                {recordings.map((rec, index) => (
                  <RecordingCard
                    key={rec.id}
                    recording={rec}
                    index={index}
                    onDelete={() => handleDelete(rec.id)}
                    onViewNote={rec.note_id ? () => navigate(`/note/${rec.note_id}`) : null}
                  />
                ))}
              </div>
            </AnimatePresence>
          )}
        </div>
      </main>
    </div>
  );
};

const RecordingCard = ({ recording, index, onDelete, onViewNote }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.28, delay: index * 0.05 }}
      className="group bg-card rounded-xl border border-border/50 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 p-4 space-y-3"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="mt-1 w-2 h-2 rounded-full bg-orange-400 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate text-sm">{recording.filename || 'Audio Recording'}</p>
            <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground flex-wrap">
              <span className="flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {new Date(recording.created_at).toLocaleString()}
              </span>
              {recording.word_count != null && (
                <span className="bg-orange-50 text-orange-600 px-1.5 py-0.5 rounded-full">
                  {recording.word_count} words
                </span>
              )}
              {recording.language && (
                <span className="uppercase bg-muted px-1.5 py-0.5 rounded-full">
                  {recording.language}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 flex-shrink-0">
          {onViewNote && (
            <Button size="sm" variant="ghost" onClick={onViewNote} title="View linked note">
              <FileText className="w-4 h-4" />
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={onDelete}
            className="opacity-0 group-hover:opacity-100 text-destructive hover:text-destructive transition-opacity"
            title="Delete recording"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {recording.transcript && (
        <>
          <p className={`text-sm text-muted-foreground leading-relaxed ${expanded ? '' : 'line-clamp-3'}`}>
            {recording.transcript}
          </p>
          {recording.transcript.length > 200 && (
            <Button size="sm" variant="ghost" className="h-6 px-2 text-xs" onClick={() => setExpanded(v => !v)}>
              {expanded ? 'Show less' : 'Show more'}
            </Button>
          )}
        </>
      )}

      {recording.linked_notes && recording.linked_notes.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-1">
          {recording.linked_notes.map((note) => (
            <span
              key={note.id}
              className="flex items-center gap-1 text-xs bg-primary/10 text-primary px-2 py-1 rounded-full"
            >
              <Link className="w-3 h-3" />
              {note.title}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  );
};

export default Voice;
