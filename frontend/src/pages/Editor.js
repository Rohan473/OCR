import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Save, Download, Loader2, FileText, Sparkles } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Textarea } from '../components/ui/textarea';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { ocrAPI, notesAPI, pdfAPI } from '../api/client';

export const Editor = () => {
  const { imageId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  
  const [imagePath, setImagePath] = useState(location.state?.imagePath || '');
  const [processing, setProcessing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const [title, setTitle] = useState('');
  const [transcribedText, setTranscribedText] = useState('');
  const [engine, setEngine] = useState('trocr');

  useEffect(() => {
    if (imagePath) {
      processOCR();
    }
  }, [imagePath]);

  const processOCR = async () => {
    setProcessing(true);
    
    try {
      toast.info('Processing image with OCR...');
      
      const result = await ocrAPI.processOCR(imagePath, engine, 'eng+hin');
      
      setOcrResult(result);
      setTranscribedText(result.text);
      setTitle(`Note ${new Date().toLocaleDateString()}`);
      
      toast.success(
        `OCR completed with ${(result.confidence * 100).toFixed(1)}% confidence`,
        { duration: 3000 }
      );
    } catch (error) {
      console.error('OCR error:', error);
      toast.error('OCR processing failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setProcessing(false);
    }
  };

  const handleSaveNote = async () => {
    if (!title.trim() || !transcribedText.trim()) {
      toast.error('Please provide a title and transcribed text');
      return;
    }

    setSaving(true);
    
    try {
      const noteData = {
        title: title.trim(),
        transcribed_text: transcribedText,
        original_image_path: imagePath,
        confidence: ocrResult?.confidence || 0,
        engine: ocrResult?.engine || engine,
        language: 'eng+hin',
        tags: [],
      };
      
      const savedNote = await notesAPI.createNote(noteData);
      
      toast.success('Note saved successfully!');
      
      // Navigate to note detail after short delay
      setTimeout(() => {
        navigate(`/note/${savedNote.id}`);
      }, 1000);
      
    } catch (error) {
      console.error('Save error:', error);
      toast.error('Failed to save note: ' + (error.response?.data?.detail || error.message));
    } finally {
      setSaving(false);
    }
  };

  const handleGeneratePDF = async () => {
    if (!transcribedText.trim()) {
      toast.error('No text to generate PDF');
      return;
    }

    try {
      toast.info('Generating PDF...');
      
      const result = await pdfAPI.generatePDF(imagePath, transcribedText, true);
      
      // Download PDF
      const downloadUrl = pdfAPI.downloadPDF(result.filename);
      window.open(downloadUrl, '_blank');
      
      toast.success('PDF generated successfully!');
    } catch (error) {
      console.error('PDF error:', error);
      toast.error('PDF generation failed: ' + (error.response?.data?.detail || error.message));
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => navigate('/upload')}
            data-testid="back-to-upload-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <h1 className="text-xl font-semibold">Edit Transcription</h1>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleGeneratePDF}
              disabled={processing || !transcribedText}
              data-testid="generate-pdf-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              PDF
            </Button>
            <Button
              onClick={handleSaveNote}
              disabled={processing || saving}
              data-testid="save-note-btn"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              Save
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content - Split Pane */}
      <main className="container py-6">
        {processing ? (
          <div className="flex flex-col items-center justify-center py-20 space-y-4">
            <Loader2 className="w-12 h-12 animate-spin text-primary" />
            <p className="text-lg font-medium">Processing with {engine.toUpperCase()}...</p>
            <p className="text-sm text-muted-foreground">This may take a few moments</p>
          </div>
        ) : (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          >
            {/* Left Pane - Image Preview */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <Label className="text-base font-medium">Original Image</Label>
                {ocrResult && (
                  <div className="text-sm text-muted-foreground">
                    Confidence: {(ocrResult.confidence * 100).toFixed(1)}%
                  </div>
                )}
              </div>
              <div className="rounded-xl border bg-card overflow-hidden shadow-sm">
                {imagePath ? (
                  <img
                    src={`file://${imagePath}`}
                    alt="Uploaded note"
                    className="w-full h-auto"
                    onError={(e) => {
                      e.target.onerror = null;
                      e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgZmlsbD0iI2Y0ZjRmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0ic2Fucy1zZXJpZiIgZm9udC1zaXplPSIxOCIgZmlsbD0iIzk5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiPkltYWdlIFByZXZpZXc8L3RleHQ+PC9zdmc+';
                    }}
                  />
                ) : (
                  <div className="flex items-center justify-center h-96 bg-muted">
                    <FileText className="w-16 h-16 text-muted-foreground" />
                  </div>
                )}
              </div>
              
              {/* Engine Toggle */}
              <div className="flex items-center gap-4 p-4 bg-muted/30 rounded-lg">
                <Label className="text-sm">OCR Engine:</Label>
                <Button
                  size="sm"
                  variant={engine === 'trocr' ? 'default' : 'outline'}
                  onClick={() => setEngine('trocr')}
                >
                  <Sparkles className="w-4 h-4 mr-2" />
                  TrOCR
                </Button>
                <Button
                  size="sm"
                  variant={engine === 'tesseract' ? 'default' : 'outline'}
                  onClick={() => setEngine('tesseract')}
                >
                  Tesseract
                </Button>
                <Button
                  size="sm"
                  onClick={processOCR}
                  disabled={processing}
                >
                  Re-process
                </Button>
              </div>
            </div>

            {/* Right Pane - Text Editor */}
            <div className="space-y-4">
              <div>
                <Label htmlFor="title" className="text-base font-medium">Title</Label>
                <Input
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Enter note title..."
                  className="mt-2"
                  data-testid="note-title-input"
                />
              </div>

              <div className="flex-1">
                <Label htmlFor="transcription" className="text-base font-medium">
                  Transcribed Text
                </Label>
                <Textarea
                  id="transcription"
                  value={transcribedText}
                  onChange={(e) => setTranscribedText(e.target.value)}
                  placeholder="Transcribed text will appear here..."
                  className="mt-2 min-h-[500px] font-mono text-sm leading-relaxed"
                  data-testid="transcription-textarea"
                />
                <p className="mt-2 text-sm text-muted-foreground">
                  {transcribedText.length} characters • {transcribedText.split(/\s+/).filter(Boolean).length} words
                </p>
              </div>
            </div>
          </motion.div>
        )}
      </main>
    </div>
  );
};

export default Editor;
