"""RAG Engine with FAISS vector database and Groq LLM for note-based Q&A"""
import os
import re
import json
import logging
import asyncio
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Any
from concurrent.futures import ThreadPoolExecutor

_embed_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed")

# faiss and groq are deferred — loading them at import time adds 30-90 s on Windows.
_faiss_module = None

def _get_faiss():
    global _faiss_module
    if _faiss_module is None:
        import faiss
        _faiss_module = faiss
    return _faiss_module

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
CHAT_MODEL = "llama-3.1-8b-instant"  # fast, free tier on Groq
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"  # local, 384-dim, ~80 MB
EMBED_DIM = 384
TOP_K = 5
MAX_CONTEXT_CHARS = 6000

# Separator used to construct chunk IDs
CHUNK_SEP      = "__chunk__"       # recordings (legacy + new)
NOTE_CHUNK_SEP = "__note_chunk__"  # per-page note chunks

# ── Page splitter for PDF notes ────────────────────────────────────────────
_PAGE_RE = re.compile(r'\s*---\s*Page\s+\d+\s*---\s*', re.IGNORECASE)
_NOTE_CHUNK_WORDS    = 250   # words per chunk when no page markers exist
_NOTE_CHUNK_OVERLAP  = 30

def _split_note_chunks(text: str) -> List[str]:
    """Split a note into embeddable chunks.

    Tries page markers first (--- Page N ---), falls back to word-window
    chunking for plain text or single-page images.
    """
    pages = [p.strip() for p in _PAGE_RE.split(text) if p.strip()]
    if len(pages) > 1:
        return pages

    words = text.split()
    if len(words) <= _NOTE_CHUNK_WORDS:
        return [text]

    chunks, pos = [], 0
    while pos < len(words):
        chunks.append(" ".join(words[pos: pos + _NOTE_CHUNK_WORDS]))
        pos += _NOTE_CHUNK_WORDS - _NOTE_CHUNK_OVERLAP
    return chunks

# Persist FAISS index to disk so it survives server restarts
ROOT_DIR = Path(__file__).parent
FAISS_DIR = ROOT_DIR / "faiss_store"
FAISS_INDEX_PATH = FAISS_DIR / "notes.index"
FAISS_META_PATH = FAISS_DIR / "notes_meta.json"

# ── Lazy-loaded embedding model ───────────────────────────────────────────
_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {EMBED_MODEL_NAME} ...")
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        logger.info("Embedding model ready.")
    return _embed_model


class FAISSStore:
    """Manages a FAISS index with a parallel metadata list.

    Each vector position *i* in the FAISS index corresponds to
    ``self.metadata[i]`` which stores the note ``id`` and ``title``
    so we can trace results back to MongoDB documents.
    """

    def __init__(self):
        FAISS_DIR.mkdir(exist_ok=True)
        self.index: Optional[Any] = None  # faiss.IndexFlatIP (loaded lazily)
        self.metadata: List[Dict[str, str]] = []  # [{id, title}, ...]
        self._load_or_create()

    # ── Persistence ────────────────────────────────────────────────────

    def _load_or_create(self):
        if FAISS_INDEX_PATH.exists() and FAISS_META_PATH.exists():
            try:
                self.index = _get_faiss().read_index(str(FAISS_INDEX_PATH))
                with open(FAISS_META_PATH, "r") as f:
                    self.metadata = json.load(f)
                logger.info(
                    f"FAISS index loaded: {self.index.ntotal} vectors, "
                    f"{len(self.metadata)} metadata entries"
                )
                if self.index.ntotal != len(self.metadata):
                    logger.warning("Index/metadata count mismatch — rebuilding")
                    self._create_fresh()
                return
            except Exception as e:
                logger.warning(f"Failed to load FAISS index, creating fresh: {e}")

        self._create_fresh()

    def _create_fresh(self):
        self.index = _get_faiss().IndexFlatIP(EMBED_DIM)
        self.metadata = []
        logger.info(f"Created new FAISS index (dim={EMBED_DIM})")

    def save(self):
        try:
            _get_faiss().write_index(self.index, str(FAISS_INDEX_PATH))
            with open(FAISS_META_PATH, "w") as f:
                json.dump(self.metadata, f)
            logger.info(f"FAISS index saved: {self.index.ntotal} vectors")
        except Exception as e:
            logger.error(f"Failed to save FAISS index: {e}")

    # ── Core operations ────────────────────────────────────────────────

    def add(self, note_id: str, title: str, embedding: List[float]):
        vec = np.array([embedding], dtype=np.float32)
        _get_faiss().normalize_L2(vec)
        self.index.add(vec)
        self.metadata.append({"id": note_id, "title": title})

    def remove(self, note_id: str):
        """Remove a note by rebuilding the index without it.

        FAISS IndexFlatIP doesn't support direct deletion, so we rebuild.
        Fine for <10k notes — takes milliseconds.
        """
        if self.index.ntotal == 0:
            return

        positions_to_keep = [
            i for i, m in enumerate(self.metadata) if m["id"] != note_id
        ]

        if len(positions_to_keep) == len(self.metadata):
            return  # not found

        if not positions_to_keep:
            self._create_fresh()
            self.save()
            return

        vectors = np.array(
            [self.index.reconstruct(i) for i in positions_to_keep],
            dtype=np.float32,
        )
        new_meta = [self.metadata[i] for i in positions_to_keep]

        self._create_fresh()
        self.index.add(vectors)
        self.metadata = new_meta
        logger.info(f"Removed note {note_id} from FAISS index, {self.index.ntotal} remaining")

    def remove_by_prefix(self, id_prefix: str):
        """Remove all entries whose id starts with id_prefix (used for recording chunks)."""
        if self.index.ntotal == 0:
            return

        positions_to_keep = [
            i for i, m in enumerate(self.metadata) if not m["id"].startswith(id_prefix)
        ]
        removed = len(self.metadata) - len(positions_to_keep)
        if removed == 0:
            return

        if not positions_to_keep:
            self._create_fresh()
            self.save()
            return

        vectors = np.array(
            [self.index.reconstruct(i) for i in positions_to_keep], dtype=np.float32
        )
        new_meta = [self.metadata[i] for i in positions_to_keep]
        self._create_fresh()
        self.index.add(vectors)
        self.metadata = new_meta
        logger.info(f"Removed {removed} FAISS entries with prefix '{id_prefix}'")

    def search(self, query_embedding: List[float], top_k: int = TOP_K) -> List[Dict]:
        if self.index.ntotal == 0:
            return []

        vec = np.array([query_embedding], dtype=np.float32)
        _get_faiss().normalize_L2(vec)

        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(vec, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.metadata):
                continue
            entry = self.metadata[idx].copy()
            entry["score"] = float(score)
            results.append(entry)

        return results

    def clear(self):
        self._create_fresh()
        self.save()

    @property
    def count(self) -> int:
        return self.index.ntotal if self.index else 0


class RAGEngine:
    """Retrieval-Augmented Generation engine.

    - Embeddings: sentence-transformers (local, free)
    - Vector store: FAISS (local, free, fast)
    - LLM: Groq (free tier, Llama 3.1 8B)
    """

    def __init__(self):
        self._client: Optional[Any] = None
        self._store: Optional[Any] = None

    @property
    def store(self) -> "FAISSStore":
        if self._store is None:
            self._store = FAISSStore()
        return self._store

    def _get_client(self):
        if self._client is None:
            from groq import AsyncGroq
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "GROQ_API_KEY is not set. Get a free key at https://console.groq.com"
                )
            self._client = AsyncGroq(api_key=api_key)
        return self._client

    # ── Embedding ──────────────────────────────────────────────────────

    def embed_text_sync(self, text: str) -> List[float]:
        text = text.replace("\n", " ").strip()
        if not text:
            return []
        model = _get_embed_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    async def embed_text(self, text: str) -> List[float]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_embed_executor, self.embed_text_sync, text)

    # ── Index management ───────────────────────────────────────────────

    async def index_note(self, note_id: str, title: str, text: str) -> bool:
        """Embed a note page-by-page and add each chunk to FAISS."""
        try:
            # Drop any previously indexed chunks for this note
            self.store.remove(note_id)
            self.store.remove_by_prefix(f"{note_id}{NOTE_CHUNK_SEP}")

            chunks = _split_note_chunks(text)
            added = 0
            for i, chunk in enumerate(chunks):
                embedding = await self.embed_text(chunk)
                if not embedding:
                    continue
                entry_id = note_id if len(chunks) == 1 else f"{note_id}{NOTE_CHUNK_SEP}{i}"
                self.store.add(entry_id, title, embedding)
                added += 1

            if added == 0:
                logger.warning(f"No embeddings produced for note {note_id}")
                return False

            self.store.save()
            logger.info(f"Indexed note {note_id} as {added} chunk(s)")
            return True
        except Exception as e:
            logger.error(f"Failed to index note {note_id}: {e}")
            return False

    async def remove_note(self, note_id: str):
        """Remove a note and all its page chunks from the FAISS index."""
        self.store.remove(note_id)
        self.store.remove_by_prefix(f"{note_id}{NOTE_CHUNK_SEP}")
        self.store.save()

    async def remove_recording(self, recording_id: str):
        """Remove a recording and all its chunks from the FAISS index."""
        self.store.remove(recording_id)  # handles old un-chunked recordings
        self.store.remove_by_prefix(f"{recording_id}{CHUNK_SEP}")
        self.store.save()

    async def reindex_all(self, db: Any) -> Dict[str, int]:
        """Rebuild the entire FAISS index from all notes and recordings in MongoDB."""
        self.store.clear()

        notes = await db.notes.find(
            {}, {"_id": 0, "id": 1, "title": 1, "transcribed_text": 1}
        ).to_list(10000)

        indexed = 0
        skipped = 0
        for note in notes:
            text = note.get("transcribed_text", "").strip()
            if not text:
                skipped += 1
                logger.info(f"  note {note['id'][:8]} '{note.get('title','')}' — skipped (empty text)")
                continue
            try:
                chunks = _split_note_chunks(text)
                nid = note["id"]
                title = note.get("title", "Untitled")
                logger.info(
                    f"  note {nid[:8]} '{title}' -- {len(text)} chars, "
                    f"{len(text.split())} words -> {len(chunks)} chunk(s)"
                )
                note_added = 0
                for i, chunk in enumerate(chunks):
                    emb = self.embed_text_sync(chunk)
                    if emb:
                        entry_id = nid if len(chunks) == 1 else f"{nid}{NOTE_CHUNK_SEP}{i}"
                        self.store.add(entry_id, title, emb)
                        note_added += 1
                if note_added:
                    indexed += note_added
                else:
                    skipped += 1
            except Exception as e:
                logger.warning(f"Failed to embed note {note['id']}: {e}")
                skipped += 1

        # Also index recordings in chunks
        recordings = await db.recordings.find(
            {}, {"_id": 0, "id": 1, "filename": 1, "transcript": 1}
        ).to_list(10000)

        CHUNK_WORDS = 300
        CHUNK_OVERLAP = 50
        for rec in recordings:
            transcript = rec.get("transcript", "").strip()
            if not transcript:
                skipped += 1
                continue
            try:
                words = transcript.split()
                chunk_title = f"Recording: {rec.get('filename', 'audio')}"
                rid = rec["id"]
                if len(words) <= CHUNK_WORDS:
                    emb = self.embed_text_sync(transcript)
                    if emb:
                        self.store.add(rid, chunk_title, emb)
                        indexed += 1
                else:
                    pos, chunk_idx = 0, 0
                    while pos < len(words):
                        chunk_text = " ".join(words[pos: pos + CHUNK_WORDS])
                        emb = self.embed_text_sync(chunk_text)
                        if emb:
                            self.store.add(f"{rid}{CHUNK_SEP}{chunk_idx}", chunk_title, emb)
                            indexed += 1
                        pos += CHUNK_WORDS - CHUNK_OVERLAP
                        chunk_idx += 1
            except Exception as e:
                logger.warning(f"Failed to embed recording {rec['id']}: {e}")
                skipped += 1

        self.store.save()
        logger.info(f"Reindex complete: {indexed} indexed, {skipped} skipped")
        return {"indexed": indexed, "skipped": skipped, "total": len(notes) + len(recordings)}

    # ── Retrieval ──────────────────────────────────────────────────────

    async def find_relevant_notes(
        self,
        question: str,
        db: Any,
        folder_id: Optional[str] = None,
        top_k: int = TOP_K,
    ) -> List[Dict[str, Any]]:
        query_embedding = await self.embed_text(question)
        if not query_embedding:
            return []

        search_k = top_k * 8 if folder_id else top_k * 6
        candidates = self.store.search(query_embedding, top_k=search_k)

        if not candidates:
            return []

        score_map = {c["id"]: c["score"] for c in candidates}

        # Classify each candidate ID:
        #   note_chunk_to_base : {chunk_id -> note_id}  (NOTE_CHUNK_SEP)
        #   rec_chunk_to_base  : {chunk_id -> rec_id}   (CHUNK_SEP)
        #   plain_ids          : no separator → look up notes first, then recordings
        plain_ids: List[str] = []
        note_chunk_to_base: Dict[str, str] = {}
        rec_chunk_to_base:  Dict[str, str] = {}

        for cid in score_map:
            if NOTE_CHUNK_SEP in cid:
                note_chunk_to_base[cid] = cid.split(NOTE_CHUNK_SEP)[0]
            elif CHUNK_SEP in cid:
                rec_chunk_to_base[cid] = cid.split(CHUNK_SEP)[0]
            else:
                plain_ids.append(cid)

        results: List[Dict[str, Any]] = []

        # ── Fetch notes (plain IDs + note-chunk base IDs) ────────────────
        note_base_ids = list(set(note_chunk_to_base.values()) | set(plain_ids))
        if note_base_ids:
            note_query: Dict[str, Any] = {"id": {"$in": note_base_ids}}
            if folder_id:
                note_query["folder_id"] = folder_id
            notes_found = await db.notes.find(note_query, {"_id": 0, "embedding": 0}).to_list(search_k)
            for note in notes_found:
                nid = note["id"]

                # Find best-matching chunk index and score
                best_score = score_map.get(nid, 0.0)
                best_chunk_idx: Optional[int] = None
                for cid, base in note_chunk_to_base.items():
                    if base == nid and score_map[cid] > best_score:
                        best_score = score_map[cid]
                        best_chunk_idx = int(cid.split(NOTE_CHUNK_SEP)[-1])

                # Narrow the context to the best matching chunk + neighbors
                # so the LLM receives the relevant page, not a 20-page PDF preamble.
                full_text = note.get("transcribed_text", "")
                if best_chunk_idx is not None:
                    all_chunks = _split_note_chunks(full_text)
                    start = max(0, best_chunk_idx - 1)
                    end   = min(len(all_chunks), best_chunk_idx + 2)
                    note["transcribed_text"] = "\n\n".join(all_chunks[start:end])

                note["similarity_score"] = best_score
                results.append(note)

        # Any plain IDs not found in notes may be old un-chunked recording IDs
        found_note_ids = {r["id"] for r in results}
        orphan_ids = [cid for cid in plain_ids if cid not in found_note_ids]

        # ── Fetch recordings (rec chunks + orphan plain IDs) ─────────────
        recording_base_ids = list(set(rec_chunk_to_base.values()) | set(orphan_ids))
        seen_rec_ids: set = set()

        if recording_base_ids:
            rec_query: Dict[str, Any] = {"id": {"$in": recording_base_ids}}
            if folder_id:
                rec_query["folder_id"] = folder_id
            recordings = await db.recordings.find(rec_query, {"_id": 0}).to_list(search_k)

            for rec in recordings:
                rid = rec["id"]
                if rid in seen_rec_ids:
                    continue
                seen_rec_ids.add(rid)

                # Best score = max across all chunk matches for this recording
                best = max(
                    (score_map[cid] for cid, base in rec_chunk_to_base.items() if base == rid),
                    default=score_map.get(rid, 0.0),
                )
                results.append({
                    "id": rid,
                    "title": rec.get("title") or f"Lecture: {rec.get('filename', 'Recording')}",
                    "transcribed_text": rec.get("transcript", ""),
                    "source_type": "recording",
                    "created_at": rec.get("created_at", ""),
                    "confidence": 1.0,
                    "similarity_score": best,
                })

        results.sort(key=lambda n: n["similarity_score"], reverse=True)

        # Drop sources with near-zero similarity (unrelated noise).
        # Keep threshold low — the LLM is instructed to say "I don't have notes on that"
        # when the retrieved content doesn't answer the question.
        MIN_SIMILARITY = 0.22
        results = [r for r in results if r["similarity_score"] >= MIN_SIMILARITY]

        return results[:top_k]

    # ── Generation ─────────────────────────────────────────────────────

    async def generate_answer(
        self,
        question: str,
        context_notes: List[Dict[str, Any]],
        history: List[Dict[str, str]],
    ) -> str:
        if not context_notes:
            return "I couldn't find any relevant notes to answer that question."

        context_parts = []
        total = 0
        for i, note in enumerate(context_notes):
            source_type = note.get("source_type", "note")
            label = "Lecture transcript" if source_type == "recording" else "Note"
            header = f'[SOURCE {i+1} — {label}: {note.get("title", "Untitled")}]'
            snippet = f'{header}\n{note.get("transcribed_text", "")}'
            if total + len(snippet) > MAX_CONTEXT_CHARS:
                break
            context_parts.append(snippet)
            total += len(snippet)

        context_block = "\n\n---\n\n".join(context_parts)

        system_prompt = (
            "You are ScribeAI's assistant. Answer the user's question using ONLY the "
            "sources provided below. Each source is labelled [SOURCE N — type: title].\n\n"
            "Rules:\n"
            "1. Only cite a source if the answer text was directly taken from it.\n"
            "2. If the information is not in any source, say 'I don't have notes on that.'\n"
            "3. Be concise and specific.\n"
            "4. When you cite, use the exact source label, e.g. (Source 1 — Note: Introduction)."
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-6:])
        messages.append({
            "role": "user",
            "content": f"My Notes:\n\n{context_block}\n\nQuestion: {question}",
        })

        client = self._get_client()
        response = await client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )
        return response.choices[0].message.content

    # ── Main query endpoint ────────────────────────────────────────────

    async def query(
        self,
        question: str,
        db: Any,
        folder_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        history = history or []

        relevant_notes = await self.find_relevant_notes(
            question, db, folder_id=folder_id
        )

        if not relevant_notes:
            return {
                "answer": (
                    "I don't have any notes indexed yet to answer your question. "
                    "Try uploading and saving some notes first, then use "
                    "the reindex endpoint to build the search index."
                ),
                "sources": [],
                "history": history,
                "index_stats": {"total_vectors": self.store.count},
            }

        answer = await self.generate_answer(question, relevant_notes, history)

        sources = [
            {
                "id": n["id"],
                "title": n.get("title", "Untitled"),
                "snippet": n.get("transcribed_text", "")[:150].strip() + "...",
                "similarity": round(n.get("similarity_score", 0.0), 3),
                "source_type": n.get("source_type", "note"),
            }
            for n in relevant_notes
        ]

        updated_history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]

        return {
            "answer": answer,
            "sources": sources,
            "history": updated_history,
            "index_stats": {"total_vectors": self.store.count},
        }


# Global instance
rag_engine = RAGEngine()
