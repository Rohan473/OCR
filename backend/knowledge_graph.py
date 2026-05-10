"""Knowledge Graph Generator

Extracts topics/concepts from note AND recording content using LLM, then builds
a co-occurrence graph and topic clusters from both content types.
"""
import math
import logging
import numpy as np
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

NOTE_TO_NOTE_THRESHOLD = 0.60
CHUNK_SEP      = "__chunk__"       # recording chunks
NOTE_CHUNK_SEP = "__note_chunk__"  # note page chunks (mirrors rag_engine)


def _normalize_recording(rec: Dict) -> Dict:
    """Give a recording the same fields generate_graph/clusters expect from a note."""
    return {
        "id": rec["id"],
        "title": rec.get("filename", "Recording"),
        "transcribed_text": rec.get("transcript", ""),
        "_type": "recording",
    }


class KnowledgeGraphGenerator:

    # ── Concept graph ──────────────────────────────────────────────────────

    async def generate_graph(
        self,
        rag_engine: Any,
        db: Any,
        folder_id: Optional[str] = None,
        max_nodes: int = 80,
    ) -> Dict[str, Any]:
        """
        Build a concept-level knowledge graph from notes AND recordings.
        Nodes  = topics/concepts extracted from content.
        Edges  = concepts that co-occur in the same document.
        """
        query: Dict[str, Any] = {}
        if folder_id:
            query["folder_id"] = folder_id

        notes = await db.notes.find(
            query,
            {"_id": 0, "id": 1, "title": 1, "transcribed_text": 1},
        ).limit(30).to_list(30)

        recordings = await db.recordings.find(
            query,
            {"_id": 0, "id": 1, "filename": 1, "transcript": 1},
        ).limit(20).to_list(20)

        # Normalize recordings to share field names with notes
        all_items = list(notes) + [_normalize_recording(r) for r in recordings]

        if not all_items:
            return _empty_graph()

        # ── Extract topics per item ────────────────────────────────────────
        item_to_topics: Dict[str, List[str]] = {}
        for item in all_items:
            try:
                topics = await self._extract_topics(item, rag_engine)
                if topics:
                    item_to_topics[item["id"]] = topics
            except Exception as exc:
                logger.warning("Topic extraction failed for %s: %s", item["id"], exc)

        if not item_to_topics:
            return _empty_graph()

        # ── Deduplicate topics by lowercased key ───────────────────────────
        topic_info: Dict[str, Dict] = {}
        for item_id, topics in item_to_topics.items():
            for topic in topics:
                key = topic.lower().strip()
                if not key:
                    continue
                if key not in topic_info:
                    topic_info[key] = {"display": topic, "item_ids": set()}
                topic_info[key]["item_ids"].add(item_id)

        # ── Build nodes (sorted by frequency, capped) ─────────────────────
        sorted_topics = sorted(
            topic_info.items(),
            key=lambda x: -len(x[1]["item_ids"]),
        )[:max_nodes]

        topic_to_nid: Dict[str, str] = {
            key: f"c{i}" for i, (key, _) in enumerate(sorted_topics)
        }
        nodes = []
        for i, (key, info) in enumerate(sorted_topics):
            count = len(info["item_ids"])
            nodes.append({
                "id": f"c{i}",
                "type": "concept",
                "title": info["display"],
                "note_count": count,
                "size": 10 + count * 4,
            })

        # ── Build edges: co-occurrence within same document ────────────────
        co_occur: Dict[Tuple[str, str], int] = {}
        for item_id, topics in item_to_topics.items():
            nids = []
            seen = set()
            for topic in topics:
                key = topic.lower().strip()
                nid = topic_to_nid.get(key)
                if nid and nid not in seen:
                    nids.append(nid)
                    seen.add(nid)
            for a in range(len(nids)):
                for b in range(a + 1, len(nids)):
                    pair = (min(nids[a], nids[b]), max(nids[a], nids[b]))
                    co_occur[pair] = co_occur.get(pair, 0) + 1

        total = max(len(all_items), 1)
        edges = [
            {
                "source": src,
                "target": tgt,
                "weight": round(min(1.0, count / total * 1.5), 2),
                "type": "co-occurrence",
                "count": count,
            }
            for (src, tgt), count in co_occur.items()
        ]

        stats = {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "note_count": len(notes),
            "recording_count": len(recordings),
        }
        logger.info(
            "Concept graph: %d concepts, %d edges from %d notes + %d recordings",
            len(nodes), len(edges), len(notes), len(recordings),
        )
        return {"nodes": nodes, "edges": edges, "stats": stats}

    async def _extract_topics(self, item: Dict, rag_engine: Any) -> List[str]:
        """Ask the LLM to extract 5-8 key topics/concepts from a note or recording."""
        title = item.get("title", "Untitled")
        text = item.get("transcribed_text", "")[:1200].strip()
        if not text:
            return [title]

        prompt = (
            f"Note title: {title}\n"
            f"Content:\n{text}\n\n"
            "Extract 5-8 key topics or concepts from this note. "
            "Each topic must be 1-4 words (e.g. 'Patent Law', 'SQL Joins', 'Newton Laws'). "
            "Reply with ONLY a comma-separated list — no bullets, no numbering, no extra text."
        )

        client = rag_engine._get_client()
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100,
        )
        raw = response.choices[0].message.content.strip()
        topics = [
            t.strip().strip(".-*1234567890)")
            for t in raw.split(",")
            if t.strip()
        ]
        return [t for t in topics if 2 <= len(t) <= 60][:8]

    # ── Topic Cluster methods ──────────────────────────────────────────────

    async def generate_clusters(
        self,
        rag_engine: Any,
        db: Any,
        folder_id: Optional[str] = None,
        max_k: int = 8,
    ) -> Dict[str, Any]:
        """Cluster notes AND recordings by topic using K-means on FAISS embedding vectors."""
        query: Dict[str, Any] = {}
        if folder_id:
            query["folder_id"] = folder_id

        db_notes = await db.notes.find(
            query,
            {"_id": 0, "id": 1, "title": 1, "transcribed_text": 1},
        ).to_list(1000)

        db_recordings = await db.recordings.find(
            query,
            {"_id": 0, "id": 1, "filename": 1, "transcript": 1},
        ).to_list(500)

        if not db_notes and not db_recordings:
            return {"clusters": [], "total_notes": 0, "total_recordings": 0, "indexed_items": 0, "k": 0}

        # Build unified lookup maps (recordings normalized to share field names)
        note_lookup = {n["id"]: n for n in db_notes}
        recording_lookup = {r["id"]: _normalize_recording(r) for r in db_recordings}
        item_ids_set = set(note_lookup) | set(recording_lookup)

        store = rag_engine.store
        indexed_ids: List[str] = []
        indexed_vectors: List = []
        seen_base_ids: set = set()

        for i, meta in enumerate(store.metadata):
            nid = meta["id"]
            # Resolve base ID from any chunk format
            if NOTE_CHUNK_SEP in nid:
                base = nid.split(NOTE_CHUNK_SEP)[0]
            elif CHUNK_SEP in nid:
                base = nid.split(CHUNK_SEP)[0]
            else:
                base = nid

            if base in item_ids_set and base not in seen_base_ids:
                seen_base_ids.add(base)
                indexed_ids.append(base)
                indexed_vectors.append(store.index.reconstruct(i))

        n = len(indexed_ids)

        if n == 0:
            return {
                "clusters": [],
                "total_notes": len(db_notes),
                "total_recordings": len(db_recordings),
                "indexed_items": 0,
                "k": 0,
            }

        if n == 1:
            item_id = indexed_ids[0]
            item = note_lookup.get(item_id) or recording_lookup.get(item_id, {})
            tw = len(item.get("transcribed_text", "").split())
            is_note = item_id in note_lookup
            return {
                "clusters": [{
                    "label": item.get("title", "Notes")[:40],
                    "note_count": 1 if is_note else 0,
                    "recording_count": 0 if is_note else 1,
                    "total_words": tw,
                    "coverage_score": round(min(1.0, tw / 1000), 2),
                    "member_ids": [item_id],
                    "member_titles": [item.get("title", "Untitled")],
                }],
                "total_notes": len(db_notes),
                "total_recordings": len(db_recordings),
                "indexed_items": 1,
                "k": 1,
            }

        k = max(2, min(max_k, int(math.sqrt(n / 2)) + 1))
        k = min(k, n)

        vectors = np.array(indexed_vectors, dtype=np.float32)
        raw_labels = self._kmeans(vectors, k)

        cluster_groups: Dict[int, List[str]] = {}
        for item_id, cl in zip(indexed_ids, raw_labels):
            cluster_groups.setdefault(cl, []).append(item_id)

        result_clusters = []
        for item_ids in cluster_groups.values():
            notes_here = [note_lookup[nid] for nid in item_ids if nid in note_lookup]
            recs_here = [recording_lookup[nid] for nid in item_ids if nid in recording_lookup]
            members = notes_here + recs_here
            if not members:
                continue

            total_words = sum(len(m.get("transcribed_text", "").split()) for m in members)
            coverage = min(1.0, (
                min(len(members), 3) / 3 * 0.4
                + min(total_words, 2000) / 2000 * 0.6
            ))

            topic_label = await self._label_cluster(rag_engine, members)

            result_clusters.append({
                "label": topic_label,
                "note_count": len(notes_here),
                "recording_count": len(recs_here),
                "total_words": total_words,
                "coverage_score": round(coverage, 2),
                "member_ids": [m["id"] for m in members],
                "member_titles": [m.get("title", "Untitled") for m in members],
            })

        result_clusters.sort(key=lambda c: c["coverage_score"])

        return {
            "clusters": result_clusters,
            "total_notes": len(db_notes),
            "total_recordings": len(db_recordings),
            "indexed_items": n,
            "k": k,
        }

    @staticmethod
    def _kmeans(vectors: np.ndarray, k: int, n_iter: int = 25) -> List[int]:
        n = len(vectors)
        rng = np.random.default_rng(42)
        centroid_idx = rng.choice(n, k, replace=False)
        centroids = vectors[centroid_idx].copy()
        labels = np.zeros(n, dtype=int)

        for _ in range(n_iter):
            sims = vectors @ centroids.T
            new_labels = np.argmax(sims, axis=1)
            if np.array_equal(new_labels, labels):
                break
            labels = new_labels
            for c in range(k):
                member_vecs = vectors[labels == c]
                if len(member_vecs) > 0:
                    centroid = member_vecs.mean(axis=0)
                    norm = np.linalg.norm(centroid)
                    centroids[c] = centroid / norm if norm > 1e-10 else centroid

        return labels.tolist()

    async def _label_cluster(self, rag_engine: Any, members: List[Dict]) -> str:
        lines = []
        for item in members[:5]:
            title = item.get("title", "Untitled")
            preview = item.get("transcribed_text", "")[:200]
            lines.append(f"- {title}: {preview}")

        prompt = (
            "These are notes and recordings from a student's knowledge base:\n\n"
            + "\n".join(lines)
            + "\n\nGive a 2-3 word topic label for this cluster. "
            "Reply with ONLY the label, no punctuation, no quotes."
        )

        try:
            client = rag_engine._get_client()
            response = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=15,
            )
            raw = response.choices[0].message.content.strip().strip("\"'").strip()
            return raw[:50] if raw else "General Notes"
        except Exception as e:
            logger.warning("Cluster label generation failed: %s", e)
            return members[0].get("title", "Topic")[:30] if members else "Topic"


def _empty_graph() -> Dict[str, Any]:
    return {
        "nodes": [],
        "edges": [],
        "stats": {
            "total_nodes": 0,
            "total_edges": 0,
            "note_count": 0,
            "recording_count": 0,
        },
    }


knowledge_graph_generator = KnowledgeGraphGenerator()
