import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload as UploadIcon, FileText, ArrowLeft,
  CheckCircle2, Loader2, Sparkles, FolderOpen, ChevronDown, Check,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { toast } from 'sonner';
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { ocrAPI, notesAPI, foldersAPI } from '../api/client';

const STEPS = [
  { id: 'upload',  label: 'Uploading',   sub: 'Sending files to server…' },
  { id: 'scan',    label: 'Scanning',    sub: 'Preprocessing image for OCR…' },
  { id: 'extract', label: 'Extracting',  sub: 'Running AI text extraction…' },
  { id: 'done',    label: 'Done',        sub: '' },
];

const fileTitle = (filename) =>
  filename.replace(/\.[^/.]+$/, '').replace(/[-_]+/g, ' ').trim() ||
  `Note ${new Date().toLocaleDateString()}`;

export const Upload = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [currentStep, setCurrentStep] = useState(-1);
  const [fileProgress, setFileProgress] = useState('');
  const [selectedFolder, setSelectedFolder] = useState(null);

  const { data: folders = [] } = useQuery({
    queryKey: ['folders'],
    queryFn: () => foldersAPI.getFolders(),
  });

  const onDrop = useCallback((accepted) => setFiles(accepted), []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif'],
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  });

  const handleUpload = async () => {
    if (files.length === 0) { toast.error('Please select files to upload'); return; }

    setUploading(true);
    setCurrentStep(0);
    const uploaded = [];

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        setFileProgress(files.length > 1 ? `File ${i + 1} of ${files.length}` : '');
        setCurrentStep(1);
        await new Promise(r => setTimeout(r, 300));
        setCurrentStep(2);
        const result = await ocrAPI.uploadImage(file, 'mistral', 'eng', true);
        uploaded.push({ file, result });
      }

      setCurrentStep(3);

      if (uploaded.length === 1) {
        // Single file: go to editor for review
        const { file, result } = uploaded[0];
        toast.success('File processed — review and save below');
        setTimeout(() => {
          navigate(`/editor/${result.image_id}`, {
            state: {
              imagePath: result.processed_path,
              originalPath: result.original_path,
              prefillText: result.text,
              prefillConfidence: result.confidence,
              prefillEngine: result.engine,
              pageCount: result.total_pages,
              folder_id: selectedFolder,
              // pre-fill title from filename
              prefillTitle: fileTitle(file.name),
            },
          });
        }, 600);
      } else {
        // Multiple files: auto-save all notes, then go to library
        setFileProgress('Saving notes…');
        let saved = 0;
        for (const { file, result } of uploaded) {
          try {
            await notesAPI.createNote({
              title: fileTitle(file.name),
              transcribed_text: result.text || '',
              original_image_path: result.original_path,
              processed_image_path: result.processed_path || result.original_path,
              confidence: result.confidence || 0,
              engine: result.engine || 'gemini',
              language: 'eng',
              folder_id: selectedFolder,
              tags: [],
            });
            saved++;
          } catch (e) {
            toast.error(`Failed to save "${file.name}"`);
          }
        }
        toast.success(`${saved} note${saved !== 1 ? 's' : ''} saved successfully`);
        setTimeout(() => navigate('/library'), 800);
      }
    } catch (error) {
      toast.error('Upload failed: ' + (error.response?.data?.detail || error.message));
      setCurrentStep(-1);
    } finally {
      setUploading(false);
      setFileProgress('');
    }
  };

  const handleClear = () => { setFiles([]); setCurrentStep(-1); };

  const selectedFolderObj = folders.find(f => f.id === selectedFolder);
  const stepSub = currentStep === 3
    ? (files.length > 1 ? 'Saving notes to library…' : 'Opening editor…')
    : STEPS[currentStep]?.sub;

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b backdrop-blur-xl bg-background/80">
        <div className="container flex h-16 items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => navigate('/')} data-testid="back-to-home-btn">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <h1 className="text-lg font-semibold">Upload Notes</h1>
          <div className="w-16" />
        </div>
      </header>

      <main className="container py-10 md:py-14 max-w-2xl mx-auto space-y-8 px-4">

        {/* Drop zone */}
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}>
          <div
            {...getRootProps()}
            data-testid="upload-dropzone"
            className={`
              relative border-2 border-dashed rounded-2xl p-14 text-center cursor-pointer
              transition-colors duration-200
              ${isDragActive
                ? 'border-primary bg-primary/5'
                : 'border-border hover:border-primary/60 hover:bg-accent/40'}
            `}
          >
            <input {...getInputProps()} />
            <div className="flex flex-col items-center gap-4">
              <motion.div
                animate={!isDragActive && !uploading ? { scale: [1, 1.06, 1] } : {}}
                transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                className="p-4 rounded-2xl bg-primary/10"
              >
                <UploadIcon className="w-8 h-8 text-primary" strokeWidth={1.5} />
              </motion.div>
              <div>
                <p className="text-base font-medium mb-1">
                  {isDragActive ? 'Drop files here' : 'Drag & drop images or PDFs'}
                </p>
                <p className="text-sm text-muted-foreground">
                  or click to browse · JPG, PNG, WebP, PDF · max 20 MB
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Selected files */}
        <AnimatePresence>
          {files.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="space-y-4"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-medium text-muted-foreground">
                  {files.length} file{files.length > 1 ? 's' : ''} selected
                </h3>
                <Button variant="ghost" size="sm" onClick={handleClear} disabled={uploading}>
                  Clear
                </Button>
              </div>

              <div className="grid grid-cols-3 sm:grid-cols-4 gap-3">
                {files.map((file, i) => {
                  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
                  return (
                    <div key={i} className="relative aspect-square rounded-xl border bg-card overflow-hidden group">
                      {isPdf ? (
                        <div className="w-full h-full flex flex-col items-center justify-center gap-1.5 bg-muted/40 px-2">
                          <FileText className="w-8 h-8 text-primary/60" strokeWidth={1.5} />
                          <p className="text-xs text-muted-foreground text-center truncate w-full px-1">{file.name}</p>
                        </div>
                      ) : (
                        <img src={URL.createObjectURL(file)} alt={file.name} className="w-full h-full object-cover" />
                      )}
                      <div className="absolute inset-0 bg-black/55 opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-2">
                        <p className="text-white text-xs truncate">{file.name}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Folder selector */}
              <div className="flex items-center gap-3 p-3 rounded-xl border bg-muted/20">
                <FolderOpen className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <span className="text-sm text-muted-foreground flex-1">Save to folder</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="gap-1.5 min-w-[120px] justify-between">
                      <span className="flex items-center gap-1.5 truncate">
                        {selectedFolderObj ? (
                          <>
                            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: selectedFolderObj.color }} />
                            <span className="truncate">{selectedFolderObj.name}</span>
                          </>
                        ) : (
                          <span className="text-muted-foreground">All Notes</span>
                        )}
                      </span>
                      <ChevronDown className="w-3.5 h-3.5 text-muted-foreground flex-shrink-0" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-44">
                    <DropdownMenuItem onClick={() => setSelectedFolder(null)} className="gap-2">
                      {!selectedFolder && <Check className="w-3.5 h-3.5 text-primary" />}
                      <span className={!selectedFolder ? '' : 'ml-[22px]'}>All Notes</span>
                    </DropdownMenuItem>
                    {folders.length > 0 && <DropdownMenuSeparator />}
                    {folders.map(f => (
                      <DropdownMenuItem key={f.id} onClick={() => setSelectedFolder(f.id)} className="gap-2">
                        {selectedFolder === f.id && <Check className="w-3.5 h-3.5 text-primary" />}
                        <div className={`flex items-center gap-1.5 ${selectedFolder === f.id ? '' : 'ml-[22px]'}`}>
                          <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: f.color }} />
                          <span className="truncate">{f.name}</span>
                        </div>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

              {/* Step progress */}
              {uploading && currentStep >= 0 && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="space-y-3 pt-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    {STEPS.map((step, i) => (
                      <React.Fragment key={step.id}>
                        <div className="flex flex-col items-center gap-1 flex-1">
                          <div className={`
                            w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium
                            transition-all duration-300
                            ${i < currentStep
                              ? 'bg-primary text-primary-foreground'
                              : i === currentStep
                                ? 'bg-primary/20 text-primary ring-2 ring-primary/40'
                                : 'bg-muted text-muted-foreground'}
                          `}>
                            {i < currentStep
                              ? <CheckCircle2 className="w-4 h-4" />
                              : i === currentStep
                                ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                : i + 1}
                          </div>
                          <span className={`text-xs ${i === currentStep ? 'text-foreground font-medium' : 'text-muted-foreground'}`}>
                            {step.label}
                          </span>
                        </div>
                        {i < STEPS.length - 1 && (
                          <div className={`h-px flex-1 -mt-5 transition-colors duration-300 ${i < currentStep ? 'bg-primary' : 'bg-border'}`} />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                  <p className="text-xs text-center text-muted-foreground">
                    {fileProgress ? `${fileProgress} — ` : ''}{stepSub}
                  </p>
                </motion.div>
              )}

              <Button
                onClick={handleUpload}
                disabled={uploading}
                className="w-full"
                size="lg"
                data-testid="process-upload-btn"
              >
                {uploading ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" />Processing…</>
                ) : (
                  <><Sparkles className="w-4 h-4 mr-2" />Upload & Extract Text</>
                )}
              </Button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Tips */}
        <div className="rounded-xl border bg-muted/20 p-5 space-y-2.5">
          <h4 className="text-sm font-medium">Tips for best results</h4>
          <ul className="text-sm text-muted-foreground space-y-1.5">
            {[
              'Use good lighting — avoid harsh shadows across the page',
              'Hold the camera parallel to the paper to avoid distortion',
              'Keep handwriting clear and avoid very small text',
              'Images are automatically enhanced before OCR runs',
            ].map((tip, i) => (
              <li key={i} className="flex items-start gap-2">
                <CheckCircle2 className="w-3.5 h-3.5 text-green-500 mt-0.5 flex-shrink-0" />
                {tip}
              </li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  );
};

export default Upload;
