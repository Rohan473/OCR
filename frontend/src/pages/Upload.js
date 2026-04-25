import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { motion } from 'framer-motion';
import { Upload as UploadIcon, Image as ImageIcon, FileText, ArrowLeft, CheckCircle2, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Progress } from '../components/ui/progress';
import { toast } from 'sonner';
import { ocrAPI } from '../api/client';

export const Upload = () => {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedImages, setUploadedImages] = useState([]);

  const onDrop = useCallback((acceptedFiles) => {
    setFiles(acceptedFiles);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif'],
      'application/pdf': ['.pdf'],
    },
    multiple: true,
  });

  const handleUpload = async () => {
    if (files.length === 0) {
      toast.error('Please select files to upload');
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    const uploaded = [];

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        toast.info(`Uploading ${file.name}...`);
        
        const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
        const result = await ocrAPI.uploadImage(file, true);

        uploaded.push({ file, result, isPdf });
        
        setUploadProgress(((i + 1) / files.length) * 100);
      }

      setUploadedImages(uploaded);
      toast.success(`Successfully uploaded ${files.length} image(s)`);
      
      if (uploaded.length > 0) {
        const first = uploaded[0];
        setTimeout(() => {
          navigate(`/editor/${first.result.image_id}`, {
            state: {
              imagePath: first.result.processed_path,
              originalPath: first.result.original_path,
              ...(first.result.is_pdf && {
                prefillText: first.result.ocr_text,
                prefillConfidence: first.result.confidence,
                prefillEngine: first.result.engine,
                pageCount: first.result.page_count,
              }),
            },
          });
        }, 1000);
      }

    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Upload failed: ' + (error.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
    }
  };

  const handleClear = () => {
    setFiles([]);
    setUploadedImages([]);
    setUploadProgress(0);
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur">
        <div className="container flex h-16 items-center justify-between">
          <Button
            variant="ghost"
            onClick={() => navigate('/')}
            data-testid="back-to-home-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          <h1 className="text-xl font-semibold">Upload Notes</h1>
          <div className="w-20" />
        </div>
      </header>

      {/* Main Content */}
      <main className="container py-8 md:py-12 max-w-4xl mx-auto">
        <div className="space-y-8">
          {/* Upload Zone */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div
              {...getRootProps()}
              className={
                `border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors duration-200 ${
                  isDragActive
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50 hover:bg-accent/50'
                }`
              }
              data-testid="upload-dropzone"
            >
              <input {...getInputProps()} />
              <div className="flex flex-col items-center gap-4">
                <div className="p-4 rounded-full bg-primary/10">
                  <UploadIcon className="w-8 h-8 text-primary" />
                </div>
                <div>
                  <p className="text-lg font-medium mb-2">
                    {isDragActive
                      ? 'Drop your files here'
                      : 'Drag and drop images or PDFs here'}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    or click to browse • Supports JPG, PNG, WebP, PDF
                  </p>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Selected Files */}
          {files.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
              className="space-y-4"
            >
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium">
                  Selected Files ({files.length})
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClear}
                  disabled={uploading}
                >
                  Clear All
                </Button>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
                {files.map((file, index) => {
                  const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
                  return (
                    <div
                      key={index}
                      className="relative aspect-square rounded-lg border bg-card overflow-hidden group"
                    >
                      {isPdf ? (
                        <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-muted/40 px-2">
                          <FileText className="w-10 h-10 text-primary/60" />
                          <p className="text-xs text-muted-foreground text-center truncate w-full px-1">
                            {file.name}
                          </p>
                        </div>
                      ) : (
                        <img
                          src={URL.createObjectURL(file)}
                          alt={file.name}
                          className="w-full h-full object-cover"
                        />
                      )}
                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                        <p className="text-white text-xs text-center px-2">{file.name}</p>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Upload Progress */}
              {uploading && (
                <div className="space-y-2">
                  <Progress value={uploadProgress} className="h-2" />
                  <p className="text-sm text-center text-muted-foreground">
                    Uploading and preprocessing... {Math.round(uploadProgress)}%
                  </p>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-4">
                <Button
                  onClick={handleUpload}
                  disabled={uploading}
                  className="flex-1"
                  size="lg"
                  data-testid="process-upload-btn"
                >
                  {uploading ? (
                    <>
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      Processing...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-5 h-5 mr-2" />
                      Upload & Process
                    </>
                  )}
                </Button>
              </div>
            </motion.div>
          )}

          {/* Info Section */}
          <div className="bg-muted/30 rounded-lg p-6 space-y-3">
            <h4 className="font-medium">Tips for Best Results:</h4>
            <ul className="text-sm text-muted-foreground space-y-2 list-disc list-inside">
              <li>Use good lighting when capturing images</li>
              <li>Keep the camera parallel to the paper (avoid tilt)</li>
              <li>Ensure handwriting is clear and not too small</li>
              <li>Images will be automatically enhanced for better OCR</li>
            </ul>
          </div>
        </div>
      </main>
    </div>
  );
};

export default Upload;
