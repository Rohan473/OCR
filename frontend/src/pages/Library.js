import React, { useState, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Upload, FolderPlus, Trash2, FileText,
  Calendar, ArrowLeft, Mic, GitBranch, MoreHorizontal,
  FolderOpen, CheckCircle2,
} from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Skeleton } from '../components/ui/skeleton';
import { Badge } from '../components/ui/badge';
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../components/ui/tooltip';
import { notesAPI, foldersAPI, searchAPI, getImagePreviewUrl } from '../api/client';

export const Library = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [selectedFolder, setSelectedFolder] = useState(null);
  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [newFolderColor, setNewFolderColor] = useState('#3B82F6');
  const [pendingDeleteIds, setPendingDeleteIds] = useState(new Set());
  const pendingTimers = useRef(new Map()); // noteId → timeoutId

  const { data: notes = [], isLoading, refetch } = useQuery({
    queryKey: ['notes', selectedFolder],
    queryFn: () => notesAPI.getNotes(selectedFolder),
  });

  const { data: allNotes = [] } = useQuery({
    queryKey: ['notes-all'],
    queryFn: () => notesAPI.getNotes(null, 1000),
  });

  const { data: folders = [], refetch: refetchFolders } = useQuery({
    queryKey: ['folders'],
    queryFn: () => foldersAPI.getFolders(),
  });

  // Count notes per folder for sidebar badges
  const folderCounts = useMemo(() => {
    const counts = {};
    allNotes.forEach(note => {
      if (note.folder_id) counts[note.folder_id] = (counts[note.folder_id] || 0) + 1;
    });
    return counts;
  }, [allNotes]);

  const displayedNotes = (searchResults !== null ? searchResults : notes)
    .filter(n => !pendingDeleteIds.has(n.id));

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); refetch(); return; }
    try {
      const result = await searchAPI.searchNotes(searchQuery, selectedFolder);
      setSearchResults(result.results || []);
      if ((result.results || []).length === 0) toast.info('No results found');
      else toast.success(`Found ${result.count} result(s)`);
    } catch {
      toast.error('Search failed');
    }
  };

  // Undo-able note deletion
  const handleDeleteNote = (noteId) => {
    // Optimistically hide from UI
    setPendingDeleteIds(prev => new Set([...prev, noteId]));

    const timeoutId = setTimeout(async () => {
      pendingTimers.current.delete(noteId);
      try {
        await notesAPI.deleteNote(noteId);
        setSearchResults(null);
        refetch();
      } catch {
        // Restore if API fails
        setPendingDeleteIds(prev => { const s = new Set(prev); s.delete(noteId); return s; });
        toast.error('Failed to delete note');
      }
    }, 4500);

    pendingTimers.current.set(noteId, timeoutId);

    toast('Note removed', {
      duration: 4500,
      action: {
        label: 'Undo',
        onClick: () => {
          clearTimeout(pendingTimers.current.get(noteId));
          pendingTimers.current.delete(noteId);
          setPendingDeleteIds(prev => { const s = new Set(prev); s.delete(noteId); return s; });
        },
      },
    });
  };

  const handleMoveNote = async (noteId, folderId) => {
    try {
      await notesAPI.updateNote(noteId, { folder_id: folderId || null });
      toast.success(folderId ? 'Moved to folder' : 'Removed from folder');
      refetch();
    } catch {
      toast.error('Failed to move note');
    }
  };

  const handleDeleteFolder = async (folderId) => {
    try {
      await foldersAPI.deleteFolder(folderId);
      if (selectedFolder === folderId) setSelectedFolder(null);
      toast.success('Folder deleted');
      refetchFolders();
    } catch {
      toast.error('Failed to delete folder');
    }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      await foldersAPI.createFolder({ name: newFolderName.trim(), color: newFolderColor });
      toast.success('Folder created');
      setShowNewFolder(false);
      setNewFolderName('');
      refetchFolders();
    } catch (err) {
      const detail = err.response?.data?.detail || 'Failed to create folder';
      toast.error(detail);
    }
  };

  const handleFolderSelect = (folderId) => {
    setSelectedFolder(folderId);
    setSearchResults(null);
    setSearchQuery('');
  };

  return (
    <TooltipProvider>
      <div className="min-h-screen bg-background">
        {/* Glassmorphism header */}
        <header className="sticky top-0 z-50 w-full border-b backdrop-blur-xl bg-background/80">
          <div className="container flex h-16 items-center justify-between">
            <Button variant="ghost" size="sm" onClick={() => navigate('/')} data-testid="back-home-btn">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Home
            </Button>
            <h1 className="text-lg font-semibold">Library</h1>
            <div className="flex items-center gap-1.5">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="sm" onClick={() => navigate('/graph')} data-testid="graph-btn">
                    <GitBranch className="w-4 h-4 mr-1.5" />
                    Graph
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Knowledge Graph</TooltipContent>
              </Tooltip>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="sm" onClick={() => navigate('/voice')} data-testid="voice-btn">
                    <Mic className="w-4 h-4 mr-1.5" />
                    Voice
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Voice Notes</TooltipContent>
              </Tooltip>
              <Button size="sm" onClick={() => navigate('/upload')} data-testid="upload-new-btn">
                <Upload className="w-4 h-4 mr-1.5" />
                Upload
              </Button>
            </div>
          </div>
        </header>

        <div className="container py-6">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Sidebar — Folders */}
            <aside className="lg:col-span-3 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Folders</h2>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={() => setShowNewFolder(v => !v)}>
                      <FolderPlus className="w-4 h-4" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>New folder</TooltipContent>
                </Tooltip>
              </div>

              <AnimatePresence>
                {showNewFolder && (
                  <motion.div
                    initial={{ opacity: 0, y: -8, height: 0 }}
                    animate={{ opacity: 1, y: 0, height: 'auto' }}
                    exit={{ opacity: 0, y: -8, height: 0 }}
                    className="overflow-hidden"
                  >
                    <div className="space-y-2 p-3 border rounded-xl bg-muted/30">
                      <Input
                        placeholder="Folder name"
                        value={newFolderName}
                        onChange={(e) => setNewFolderName(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
                        autoFocus
                      />
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={newFolderColor}
                          onChange={(e) => setNewFolderColor(e.target.value)}
                          className="w-8 h-8 rounded-lg cursor-pointer border"
                          title="Choose folder colour"
                        />
                        <Button size="sm" className="flex-1" onClick={handleCreateFolder}>Create</Button>
                        <Button size="sm" variant="ghost" onClick={() => setShowNewFolder(false)}>Cancel</Button>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="space-y-0.5">
                <Button
                  variant={selectedFolder === null ? 'secondary' : 'ghost'}
                  className="w-full justify-start h-9"
                  onClick={() => handleFolderSelect(null)}
                >
                  <FileText className="w-4 h-4 mr-2 flex-shrink-0" />
                  All Notes
                  <Badge variant="secondary" className="ml-auto text-xs px-1.5 py-0 h-5">
                    {allNotes.length}
                  </Badge>
                </Button>

                {folders.map((folder) => (
                  <FolderItem
                    key={folder.id}
                    folder={folder}
                    isSelected={selectedFolder === folder.id}
                    count={folderCounts[folder.id] || 0}
                    onSelect={() => handleFolderSelect(folder.id)}
                    onDelete={() => handleDeleteFolder(folder.id)}
                  />
                ))}

                {folders.length === 0 && (
                  <p className="text-xs text-muted-foreground px-2 py-3 text-center">
                    No folders yet — create one above
                  </p>
                )}
              </div>
            </aside>

            {/* Main Content */}
            <main className="lg:col-span-9 space-y-5">
              {/* Search */}
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    value={searchQuery}
                    onChange={(e) => { setSearchQuery(e.target.value); if (!e.target.value.trim()) setSearchResults(null); }}
                    onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                    placeholder="Search notes… (Enter to search)"
                    className="pl-9"
                    data-testid="search-input"
                  />
                </div>
                <Button onClick={handleSearch} disabled={!searchQuery.trim()}>Search</Button>
              </div>

              {searchResults !== null && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                  <span>{searchResults.length} result(s) for &ldquo;{searchQuery}&rdquo;</span>
                  <Button size="sm" variant="ghost" className="h-6 px-2" onClick={() => { setSearchResults(null); setSearchQuery(''); }}>
                    Clear
                  </Button>
                </div>
              )}

              {/* Notes Grid */}
              {isLoading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {Array.from({ length: 8 }).map((_, i) => (
                    <div key={i} className="rounded-xl border overflow-hidden">
                      <Skeleton className="aspect-[4/3] w-full rounded-none" />
                      <div className="p-4 space-y-2">
                        <Skeleton className="h-4 w-3/4" />
                        <Skeleton className="h-3 w-full" />
                        <Skeleton className="h-3 w-2/3" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : displayedNotes.length === 0 ? (
                <motion.div
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-center py-16 space-y-4 border border-dashed rounded-2xl"
                >
                  <div className="inline-flex p-4 rounded-2xl bg-muted">
                    {searchResults !== null ? (
                      <Search className="w-10 h-10 text-muted-foreground" />
                    ) : (
                      <FolderOpen className="w-10 h-10 text-muted-foreground" />
                    )}
                  </div>
                  <div>
                    <p className="text-base font-medium">
                      {searchResults !== null ? 'No results found' : selectedFolder ? 'No notes in this folder' : 'No notes yet'}
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {searchResults !== null
                        ? 'Try a different search term'
                        : 'Upload your first handwritten note to get started'}
                    </p>
                  </div>
                  {searchResults === null && (
                    <Button onClick={() => navigate('/upload')}>
                      <Upload className="w-4 h-4 mr-2" />
                      Upload Notes
                    </Button>
                  )}
                </motion.div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                  {displayedNotes.map((note, index) => (
                    <NoteCard
                      key={note.id}
                      note={note}
                      index={index}
                      folders={folders}
                      onClick={() => navigate(`/note/${note.id}`)}
                      onDelete={() => handleDeleteNote(note.id)}
                      onMove={(folderId) => handleMoveNote(note.id, folderId)}
                    />
                  ))}
                </div>
              )}
            </main>
          </div>
        </div>
      </div>
    </TooltipProvider>
  );
};

// ── Folder sidebar item with AlertDialog ────────────────────────────────────
const FolderItem = ({ folder, isSelected, count, onSelect, onDelete }) => (
  <div className="group relative">
    <Button
      variant={isSelected ? 'secondary' : 'ghost'}
      className="w-full justify-start h-9 pr-8"
      onClick={onSelect}
    >
      <div className="w-2.5 h-2.5 rounded-full mr-2 flex-shrink-0" style={{ backgroundColor: folder.color }} />
      <span className="truncate">{folder.name}</span>
      {count > 0 && (
        <Badge variant="secondary" className="ml-auto text-xs px-1.5 py-0 h-5">{count}</Badge>
      )}
    </Button>

    <AlertDialog>
      <AlertDialogTrigger asChild>
        <button
          onClick={(e) => e.stopPropagation()}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 hover:text-destructive hover:bg-destructive/10 transition-all"
          title="Delete folder"
          aria-label={`Delete folder ${folder.name}`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete &ldquo;{folder.name}&rdquo;?</AlertDialogTitle>
          <AlertDialogDescription>
            This folder will be permanently deleted. All notes inside will be kept and moved to &ldquo;All Notes&rdquo;.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            onClick={onDelete}
          >
            Delete folder
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  </div>
);

// ── Note card with dropdown ──────────────────────────────────────────────────
const NoteCard = ({ note, index, folders, onClick, onDelete, onMove }) => {
  const imageUrl = getImagePreviewUrl(note.original_image_path);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, delay: index * 0.04 }}
      className="group bg-card rounded-xl border border-border/50 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-300 cursor-pointer overflow-hidden"
      onClick={onClick}
      data-testid={`note-card-${note.id}`}
    >
      {/* Thumbnail */}
      <div className="aspect-[4/3] bg-muted overflow-hidden relative">
        {imageUrl ? (
          <img src={imageUrl} alt={note.title} className="w-full h-full object-cover" onError={(e) => { e.target.style.display = 'none'; }} />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center bg-gradient-to-br from-zinc-100 to-zinc-200">
            <FileText className="w-10 h-10 text-zinc-400" />
          </div>
        )}

        {/* Engine badge */}
        <span className="absolute top-2 left-2 text-xs bg-black/40 text-white px-1.5 py-0.5 rounded-full backdrop-blur-sm">
          {note.engine}
        </span>

        {/* Actions dropdown — appears on hover */}
        <div
          className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity"
          onClick={(e) => e.stopPropagation()}
        >
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                className="w-7 h-7 rounded-full bg-black/50 backdrop-blur-sm flex items-center justify-center text-white hover:bg-black/70 transition-colors"
                aria-label="Note actions"
              >
                <MoreHorizontal className="w-4 h-4" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={onClick}>
                <FileText className="w-4 h-4 mr-2" />
                Open note
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuSub>
                <DropdownMenuSubTrigger>
                  <FolderOpen className="w-4 h-4 mr-2" />
                  Move to folder
                </DropdownMenuSubTrigger>
                <DropdownMenuSubContent>
                  <DropdownMenuItem onClick={() => onMove(null)} className="text-muted-foreground">
                    No folder
                  </DropdownMenuItem>
                  {folders.map(f => (
                    <DropdownMenuItem key={f.id} onClick={() => onMove(f.id)}>
                      <div className="w-2 h-2 rounded-full mr-2 flex-shrink-0" style={{ backgroundColor: f.color }} />
                      {f.name}
                    </DropdownMenuItem>
                  ))}
                  {folders.length === 0 && (
                    <DropdownMenuItem disabled className="text-xs text-muted-foreground">
                      No folders yet
                    </DropdownMenuItem>
                  )}
                </DropdownMenuSubContent>
              </DropdownMenuSub>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={onDelete}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-1.5">
        <h3 className="font-medium text-sm leading-snug truncate">{note.title}</h3>
        <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
          {note.transcribed_text}
        </p>

        <div className="flex items-center justify-between pt-2 text-xs text-muted-foreground">
          <div className="flex items-center gap-1">
            <Calendar className="w-3 h-3" />
            {new Date(note.created_at).toLocaleDateString()}
          </div>
          <span className={`font-medium ${(note.confidence || 0) >= 0.8 ? 'text-green-600' : (note.confidence || 0) >= 0.5 ? 'text-yellow-600' : 'text-red-500'}`}>
            {((note.confidence || 0) * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </motion.div>
  );
};

export default Library;
