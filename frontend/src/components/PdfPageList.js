import React, { useEffect, useState } from 'react';
import { Loader2, FileText } from 'lucide-react';
import { getImagePreviewUrl, pdfPagesAPI } from '../api/client';

export const PdfPageList = ({ sourcePath, fallbackPath, maxPages = 0 }) => {
  const [pages, setPages] = useState(null);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const isPdf = (sourcePath || '').toLowerCase().endsWith('.pdf');

  useEffect(() => {
    if (!isPdf || !sourcePath) {
      setPages(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    pdfPagesAPI
      .getPages(sourcePath, maxPages)
      .then((data) => {
        if (cancelled) return;
        setPages(data.pages || []);
        setTotalPages(data.total_pages || 0);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err.response?.data?.detail || err.message || 'Failed to load pages');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sourcePath, isPdf, maxPages]);

  const singlePath = !isPdf ? (sourcePath || fallbackPath) : null;
  const singleUrl = singlePath ? getImagePreviewUrl(singlePath) : '';

  if (!isPdf) {
    if (!singleUrl) {
      return (
        <div className="flex items-center justify-center h-96 bg-muted">
          <FileText className="w-16 h-16 text-muted-foreground" />
        </div>
      );
    }
    return (
      <img
        src={singleUrl}
        alt="Note preview"
        className="w-full h-auto"
        onError={(e) => {
          e.target.onerror = null;
          e.target.style.display = 'none';
        }}
      />
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        <p className="text-xs text-muted-foreground">Rendering PDF pages…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-destructive">
        Failed to render PDF: {error}
      </div>
    );
  }

  if (!pages || pages.length === 0) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        No pages to display.
      </div>
    );
  }

  return (
    <div className="flex flex-col">
      {pages.map((p, i) => (
        <div key={p} className="relative">
          <img
            src={getImagePreviewUrl(p)}
            alt={`Page ${i + 1}`}
            className="w-full h-auto block"
            loading="lazy"
            onError={(e) => {
              e.target.onerror = null;
              e.target.style.display = 'none';
            }}
          />
          <div className="absolute top-2 right-2 px-2 py-0.5 bg-background/80 backdrop-blur rounded-md text-xs text-muted-foreground border">
            {i + 1} / {totalPages}
          </div>
          {i < pages.length - 1 && <div className="border-b" />}
        </div>
      ))}
      {totalPages > pages.length && (
        <div className="p-3 text-center text-xs text-muted-foreground bg-muted/30 border-t">
          Showing first {pages.length} of {totalPages} pages
        </div>
      )}
    </div>
  );
};

export default PdfPageList;
