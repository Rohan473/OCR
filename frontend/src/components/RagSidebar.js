import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BrainCircuit, X, Send, Loader2, FileText,
  Mic, RefreshCw, Sparkles, ChevronDown, Check,
} from 'lucide-react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import { ragAPI, foldersAPI } from '../api/client';
import { useQuery } from '@tanstack/react-query';

const STARTER_QUESTIONS = [
  'Summarise my recent notes',
  'What are the key topics I\'ve studied?',
  'Explain the main concepts in my notes',
  'What should I review for an exam?',
];

export const RagSidebar = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [question, setQuestion] = useState('');
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [reindexing, setReindexing] = useState(false);
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  const { data: folders = [] } = useQuery({
    queryKey: ['folders'],
    queryFn: () => foldersAPI.getFolders(),
    enabled: open,
  });

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, loading]);

  const handleSend = async (q = question.trim()) => {
    if (!q || loading) return;

    setQuestion('');
    setLoading(true);
    const optimisticHistory = [...history, { role: 'user', content: q }];
    setHistory(optimisticHistory);

    try {
      const cleanHistory = history.map(({ role, content }) => ({ role, content }));
      const result = await ragAPI.query(q, cleanHistory, selectedFolder);
      const enrichedHistory = result.history.map((msg, idx) => {
        if (msg.role === 'assistant' && idx === result.history.length - 1) {
          return { ...msg, sources: result.sources };
        }
        return msg;
      });
      setHistory(enrichedHistory);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Query failed. Check your API key.';
      toast.error(msg);
      setHistory([...optimisticHistory, { role: 'assistant', content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  const handleReindex = async () => {
    setReindexing(true);
    try {
      await ragAPI.reindex();
      toast.success('Notes reindexed — ask away!');
    } catch {
      toast.error('Reindex failed');
    } finally {
      setReindexing(false);
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
    <TooltipProvider>
      <>
        {/* Toggle button */}
        <motion.button
          initial={false}
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => setOpen(v => !v)}
          className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/25 px-4 py-3 text-sm font-medium hover:bg-primary/90 transition-colors"
          aria-label="Toggle AI chat"
        >
          <BrainCircuit className="w-4 h-4" />
          <span>Ask your notes</span>
        </motion.button>

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
                <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/20">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-lg bg-primary/10">
                      <BrainCircuit className="w-4 h-4 text-primary" />
                    </div>
                    <span className="font-semibold text-sm">Ask your notes</span>
                  </div>
                  <div className="flex items-center gap-1">
                    {/* Folder filter dropdown */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <button className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground border rounded-full px-2.5 py-1 transition-colors hover:bg-muted">
                          {selectedFolderName || 'All notes'}
                          <ChevronDown className="w-3 h-3" />
                        </button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-40">
                        <DropdownMenuItem onClick={() => setSelectedFolder(null)} className="gap-2">
                          {!selectedFolder && <Check className="w-3.5 h-3.5 text-primary" />}
                          <span className={!selectedFolder ? 'ml-0' : 'ml-5'}>All notes</span>
                        </DropdownMenuItem>
                        {folders.length > 0 && <DropdownMenuSeparator />}
                        {folders.map(f => (
                          <DropdownMenuItem key={f.id} onClick={() => setSelectedFolder(f.id)} className="gap-2">
                            {selectedFolder === f.id && <Check className="w-3.5 h-3.5 text-primary" />}
                            <div className={`flex items-center gap-1.5 ${selectedFolder === f.id ? '' : 'ml-5'}`}>
                              <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: f.color }} />
                              <span className="truncate">{f.name}</span>
                            </div>
                          </DropdownMenuItem>
                        ))}
                      </DropdownMenuContent>
                    </DropdownMenu>

                    {/* Reindex button */}
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={handleReindex}
                          disabled={reindexing}
                          aria-label="Reindex notes"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${reindexing ? 'animate-spin' : ''}`} />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent side="bottom">Reindex notes</TooltipContent>
                    </Tooltip>

                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setOpen(false)} aria-label="Close">
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                {/* Messages */}
                <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                  {messages.length === 0 ? (
                    <div className="space-y-5 pt-4">
                      <div className="text-center space-y-2">
                        <div className="inline-flex p-3 rounded-2xl bg-primary/10">
                          <Sparkles className="w-6 h-6 text-primary" />
                        </div>
                        <p className="text-sm font-medium">Ask anything about your notes</p>
                        <p className="text-xs text-muted-foreground">AI will search your notes and cite sources</p>
                      </div>
                      <div className="space-y-2">
                        <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide px-1">Try asking</p>
                        {STARTER_QUESTIONS.map((q, i) => (
                          <button
                            key={i}
                            onClick={() => handleSend(q)}
                            className="w-full text-left text-sm px-3 py-2.5 rounded-xl border border-border/60 bg-card hover:bg-muted hover:border-primary/30 transition-all duration-200 text-muted-foreground hover:text-foreground"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  ) : (
                    messages.map((msg, i) => {
                      const isUser = msg.role === 'user';
                      return (
                        <div key={i} className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[88%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                            isUser
                              ? 'bg-primary text-primary-foreground rounded-br-sm'
                              : 'bg-muted rounded-bl-sm'
                          }`}>
                            {msg.content}

                            {/* Source citations */}
                            {msg.sources && msg.sources.length > 0 && (
                              <div className="mt-2.5 pt-2.5 border-t border-muted-foreground/20 space-y-1.5">
                                <p className="text-xs text-muted-foreground font-medium">Sources</p>
                                <div className="flex flex-wrap gap-1.5">
                                  {msg.sources.map(src => (
                                    <button
                                      key={src.id}
                                      onClick={() =>
                                        src.source_type === 'recording'
                                          ? navigate('/voice')
                                          : navigate(`/note/${src.id}`)
                                      }
                                      className="flex items-center gap-1 text-xs bg-background/70 border border-border/60 rounded-full px-2 py-0.5 hover:bg-primary/10 hover:border-primary/30 hover:text-primary transition-all duration-150"
                                    >
                                      {src.source_type === 'recording'
                                        ? <Mic className="w-2.5 h-2.5 flex-shrink-0" />
                                        : <FileText className="w-2.5 h-2.5 flex-shrink-0" />
                                      }
                                      <span className="max-w-[120px] truncate">{src.title}</span>
                                    </button>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}

                  {loading && (
                    <div className="flex justify-start">
                      <div className="bg-muted rounded-2xl rounded-bl-sm px-4 py-2.5 flex items-center gap-2">
                        <div className="flex gap-1">
                          {[0, 1, 2].map(i => (
                            <span
                              key={i}
                              className="w-1.5 h-1.5 rounded-full bg-muted-foreground/60 animate-bounce"
                              style={{ animationDelay: `${i * 150}ms` }}
                            />
                          ))}
                        </div>
                        <span className="text-xs text-muted-foreground">Thinking…</span>
                      </div>
                    </div>
                  )}

                  {messages.length > 0 && !loading && (
                    <div className="flex justify-center pt-1">
                      <button
                        onClick={() => setHistory([])}
                        className="text-xs text-muted-foreground hover:text-foreground transition-colors px-3 py-1 rounded-full border hover:bg-muted"
                      >
                        Clear chat
                      </button>
                    </div>
                  )}

                  <div ref={bottomRef} />
                </div>

                {/* Input */}
                <div className="px-4 py-3 border-t bg-muted/10 flex gap-2 items-center">
                  <Input
                    ref={inputRef}
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about your notes…"
                    disabled={loading}
                    className="text-sm rounded-xl flex-1"
                  />
                  <Button
                    size="icon"
                    onClick={() => handleSend()}
                    disabled={!question.trim() || loading}
                    className="flex-shrink-0 rounded-xl"
                    aria-label="Send message"
                  >
                    {loading
                      ? <Loader2 className="w-4 h-4 animate-spin" />
                      : <Send className="w-4 h-4" />
                    }
                  </Button>
                </div>
              </motion.aside>
            </>
          )}
        </AnimatePresence>
      </>
    </TooltipProvider>
  );
};
