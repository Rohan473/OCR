import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { BrainCircuit, X, Send, Loader2, FileText, ChevronDown } from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { toast } from 'sonner';
import { ragAPI, foldersAPI } from '../api/client';
import { useQuery } from '@tanstack/react-query';

export const RagSidebar = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [showFolderMenu, setShowFolderMenu] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const { data: folders = [] } = useQuery({
    queryKey: ['folders'],
    queryFn: () => foldersAPI.getFolders(),
    enabled: open,
  });

  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, loading]);

  const handleSend = async () => {
    const q = question.trim();
    if (!q || loading) return;

    setQuestion('');
    setLoading(true);

    const optimisticHistory = [...history, { role: 'user', content: q }];
    setHistory(optimisticHistory);

    try {
      const result = await ragAPI.query(q, history, selectedFolder);
      // Attach sources to the assistant message so they render inline
      const enrichedHistory = result.history.map((msg, idx) => {
        if (msg.role === 'assistant' && idx === result.history.length - 1) {
          return { ...msg, sources: result.sources };
        }
        return msg;
      });
      setHistory(enrichedHistory);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Query failed. Check your OPENAI_API_KEY.';
      toast.error(msg);
      setHistory([...optimisticHistory, { role: 'assistant', content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const selectedFolderName = folders.find(f => f.id === selectedFolder)?.name;

  const messages = history.filter(m => m.role === 'user' || m.role === 'assistant');

  return (
    <>
      {/* Toggle button */}
      <button
        onClick={() => setOpen(v => !v)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-primary text-primary-foreground shadow-lg px-4 py-3 text-sm font-medium hover:bg-primary/90 transition-colors"
        aria-label="Toggle RAG chat"
      >
        <BrainCircuit className="w-4 h-4" />
        <span>Ask your notes</span>
      </button>

      {/* Sidebar panel */}
      <AnimatePresence>
        {open && (
          <>
            {/* Backdrop (mobile) */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-40 bg-black/20 md:hidden"
              onClick={() => setOpen(false)}
            />

            <motion.aside
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 28, stiffness: 300 }}
              className="fixed right-0 top-0 bottom-0 z-50 w-[380px] max-w-[100vw] flex flex-col bg-background border-l shadow-2xl"
            >
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-3 border-b">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="w-5 h-5 text-primary" />
                  <span className="font-semibold text-sm">Ask your notes</span>
                </div>
                <div className="flex items-center gap-2">
                  {/* Folder filter */}
                  <div className="relative">
                    <button
                      onClick={() => setShowFolderMenu(v => !v)}
                      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground border rounded px-2 py-1"
                    >
                      {selectedFolderName || 'All notes'}
                      <ChevronDown className="w-3 h-3" />
                    </button>
                    {showFolderMenu && (
                      <div className="absolute right-0 top-full mt-1 w-40 bg-background border rounded shadow-lg z-10 py-1">
                        <button
                          className="w-full text-left px-3 py-1.5 text-xs hover:bg-muted"
                          onClick={() => { setSelectedFolder(null); setShowFolderMenu(false); }}
                        >
                          All notes
                        </button>
                        {folders.map(f => (
                          <button
                            key={f.id}
                            className="w-full text-left px-3 py-1.5 text-xs hover:bg-muted"
                            onClick={() => { setSelectedFolder(f.id); setShowFolderMenu(false); }}
                          >
                            {f.name}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setOpen(false)}>
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                {messages.length === 0 && (
                  <div className="text-center text-muted-foreground text-sm py-12 space-y-2">
                    <BrainCircuit className="w-8 h-8 mx-auto opacity-30" />
                    <p>Ask anything about your notes.</p>
                    <p className="text-xs opacity-60">e.g. "What did I write about gradients?"</p>
                  </div>
                )}

                {messages.map((msg, i) => {
                  const isUser = msg.role === 'user';
                  const assistantData = !isUser && history[i + 1] === undefined
                    ? null
                    : null; // sources attached separately via result
                  return (
                    <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                      <div
                        className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                          isUser
                            ? 'bg-primary text-primary-foreground rounded-br-sm'
                            : 'bg-muted rounded-bl-sm'
                        }`}
                      >
                        {msg.content}
                        {msg.sources && msg.sources.length > 0 && (
                          <div className="mt-2 pt-2 border-t border-muted-foreground/20 space-y-1">
                            <p className="text-xs opacity-60 mb-1">Sources</p>
                            {msg.sources.map(src => (
                              <button
                                key={src.id}
                                onClick={() => navigate(`/note/${src.id}`)}
                                className="flex items-center gap-1.5 text-xs hover:underline opacity-80"
                              >
                                <FileText className="w-3 h-3 flex-shrink-0" />
                                {src.title}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}

                {loading && (
                  <div className="flex justify-start">
                    <div className="bg-muted rounded-xl rounded-bl-sm px-3 py-2 flex items-center gap-2">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span className="text-sm text-muted-foreground">Thinking...</span>
                    </div>
                  </div>
                )}

                <div ref={bottomRef} />
              </div>

              {/* Input */}
              <div className="px-4 py-3 border-t flex gap-2">
                <Input
                  ref={inputRef}
                  value={question}
                  onChange={e => setQuestion(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask a question..."
                  disabled={loading}
                  className="text-sm"
                />
                <Button
                  size="icon"
                  onClick={handleSend}
                  disabled={!question.trim() || loading}
                  className="flex-shrink-0"
                >
                  {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </Button>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
};
