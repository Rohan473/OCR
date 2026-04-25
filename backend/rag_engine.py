import os
import logging
import numpy as np
from typing import List, Dict, Optional, Any
from groq import AsyncGroq

logger = logging.getLogger(__name__)

CHAT_MODEL = "llama-3.1-8b-instant"  # fast, free tier
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"  # local, 384-dim, ~80 MB
TOP_K = 5
MAX_CONTEXT_CHARS = 6000

# Lazy-loaded so startup stays fast
_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model {EMBED_MODEL_NAME}...")
        _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
        logger.info("Embedding model ready.")
    return _embed_model


class RAGEngine:
    def __init__(self):
        self._client: Optional[AsyncGroq] = None

    def _get_client(self) -> AsyncGroq:
        if self._client is None:
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_API_KEY is not set")
            self._client = AsyncGroq(api_key=api_key)
        return self._client

    def embed_text_sync(self, text: str) -> List[float]:
        text = text.replace("\n", " ").strip()
        if not text:
            return []
        model = _get_embed_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    async def embed_text(self, text: str) -> List[float]:
        # sentence-transformers is CPU/GPU sync — run inline (fast enough for notes)
        return self.embed_text_sync(text)

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        va, vb = np.array(a), np.array(b)
        denom = np.linalg.norm(va) * np.linalg.norm(vb)
        if denom == 0:
            return 0.0
        return float(np.dot(va, vb) / denom)

    def find_similar_notes(
        self,
        query_embedding: List[float],
        notes: List[Dict[str, Any]],
        top_k: int = TOP_K,
    ) -> List[Dict[str, Any]]:
        scored = []
        for note in notes:
            emb = note.get("embedding")
            if not emb:
                continue
            score = self._cosine_similarity(query_embedding, emb)
            scored.append((score, note))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [note for _, note in scored[:top_k]]

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
        for note in context_notes:
            snippet = f'[Note: {note["title"]}]\n{note["transcribed_text"]}'
            if total + len(snippet) > MAX_CONTEXT_CHARS:
                break
            context_parts.append(snippet)
            total += len(snippet)

        context_block = "\n\n---\n\n".join(context_parts)

        system_prompt = (
            "You are a helpful assistant that answers questions based on the user's "
            "handwritten notes. Answer using only information from the notes provided. "
            "Be concise and specific. If the notes don't contain enough information, "
            "say so clearly."
        )

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history[-6:])
        messages.append({
            "role": "user",
            "content": f"Notes:\n\n{context_block}\n\nQuestion: {question}",
        })

        client = self._get_client()
        response = await client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=512,
        )
        return response.choices[0].message.content

    async def query(
        self,
        question: str,
        db: Any,
        folder_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        history = history or []

        query_embedding = await self.embed_text(question)
        if not query_embedding:
            return {"answer": "Could not process the question.", "sources": [], "history": history}

        mongo_query: Dict[str, Any] = {"embedding": {"$exists": True, "$ne": None}}
        if folder_id:
            mongo_query["folder_id"] = folder_id

        notes = await db.notes.find(mongo_query, {"_id": 0}).to_list(500)

        top_notes = self.find_similar_notes(query_embedding, notes)

        answer = await self.generate_answer(question, top_notes, history)

        sources = [
            {
                "id": n["id"],
                "title": n["title"],
                "snippet": n["transcribed_text"][:120].strip() + "...",
            }
            for n in top_notes
        ]

        updated_history = history + [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]

        return {"answer": answer, "sources": sources, "history": updated_history}


rag_engine = RAGEngine()
