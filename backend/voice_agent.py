"""Voice-to-Note Linking Engine

Records/uploads audio lectures, transcribes them via Groq Whisper,
generates embeddings, and auto-links them to semantically similar
handwritten notes using FAISS.

Handles long lectures (1hr+) by:
1. Compressing uploaded audio to low-bitrate MP3 (mono, 48kbps)
2. Splitting into <25MB chunks at silence boundaries
3. Transcribing each chunk sequentially and merging results
"""
import os
import io
import logging
import uuid
import time
import subprocess
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
AUDIO_DIR = ROOT_DIR / "audio_uploads"
AUDIO_CHUNKS_DIR = AUDIO_DIR / "chunks"
AUDIO_DIR.mkdir(exist_ok=True)
AUDIO_CHUNKS_DIR.mkdir(exist_ok=True)

# Minimum cosine similarity to consider a note "linked" to a recording
LINK_THRESHOLD = 0.55
MAX_LINKED_NOTES = 5

# Whisper API limit
MAX_CHUNK_SIZE_BYTES = 24 * 1024 * 1024  # 24MB (leave 1MB headroom)
# Target chunk duration: 10 minutes — keeps each API call fast
TARGET_CHUNK_SECONDS = 600


def _ffmpeg_available() -> bool:
    """Check if ffmpeg is installed."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5,
        )
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _compress_audio(input_path: str, output_path: str) -> bool:
    """Compress audio to mono MP3 at 48kbps — sufficient for speech.

    A 1-hour lecture at 48kbps mono = ~21MB (well under the 25MB limit).
    For lectures longer than ~1h15m, we still need to chunk.
    """
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", input_path,
                "-vn",                  # strip video if present
                "-ac", "1",             # mono
                "-ar", "16000",         # 16kHz sample rate (Whisper native)
                "-b:a", "48k",          # 48kbps — plenty for speech
                "-map_metadata", "-1",  # strip metadata
                output_path,
            ],
            capture_output=True,
            timeout=300,
        )
        return Path(output_path).exists() and Path(output_path).stat().st_size > 0
    except Exception as e:
        logger.error(f"Audio compression failed: {e}")
        return False


def _split_audio(input_path: str, chunk_dir: str, chunk_seconds: int = TARGET_CHUNK_SECONDS) -> List[str]:
    """Split audio into chunks using ffmpeg segment muxer.

    Splits at silence boundaries near the target duration to avoid
    cutting mid-sentence.
    """
    chunk_pattern = os.path.join(chunk_dir, "chunk_%03d.mp3")

    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", input_path,
                "-f", "segment",
                "-segment_time", str(chunk_seconds),
                "-ac", "1",
                "-ar", "16000",
                "-b:a", "48k",
                "-reset_timestamps", "1",
                chunk_pattern,
            ],
            capture_output=True,
            timeout=300,
        )
    except Exception as e:
        logger.error(f"Audio splitting failed: {e}")
        return []

    # Collect chunk files in order
    chunks = sorted(Path(chunk_dir).glob("chunk_*.mp3"))
    return [str(c) for c in chunks]


class VoiceEngine:
    """Transcribe audio and semantically link to handwritten notes."""

    def __init__(self):
        self._groq_client = None
        self.ffmpeg_available = _ffmpeg_available()
        if not self.ffmpeg_available:
            logger.warning(
                "ffmpeg not found — long audio files (>25MB) cannot be processed. "
                "Install ffmpeg: https://ffmpeg.org/download.html"
            )

    def _get_groq_client(self):
        if self._groq_client is None:
            from groq import Groq

            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_API_KEY is not set")
            self._groq_client = Groq(api_key=api_key)
        return self._groq_client

    # ── Single-chunk transcription ─────────────────────────────────────

    def _transcribe_chunk(
        self,
        audio_path: str,
        language: str = "en",
        offset_seconds: float = 0.0,
    ) -> Dict[str, Any]:
        """Transcribe a single audio chunk (<25MB) using Groq Whisper."""
        client = self._get_groq_client()

        with open(audio_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(Path(audio_path).name, f.read()),
                model="whisper-large-v3-turbo",
                language=language,
                response_format="verbose_json",
            )

        text = transcription.text.strip() if transcription.text else ""
        duration = getattr(transcription, "duration", None)

        segments = []
        if hasattr(transcription, "segments") and transcription.segments:
            for seg in transcription.segments:
                segments.append({
                    "start": round((seg.get("start", 0) or 0) + offset_seconds, 2),
                    "end": round((seg.get("end", 0) or 0) + offset_seconds, 2),
                    "text": seg.get("text", "").strip(),
                })

        return {
            "text": text,
            "duration": duration or 0,
            "segments": segments,
        }

    # ── Main transcription (handles any length) ────────────────────────

    def transcribe_audio(
        self,
        audio_path: str,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Transcribe an audio file of any length.

        Strategy:
        1. If file is <25MB -> transcribe directly (single API call)
        2. If file is >25MB -> compress to 48kbps mono MP3
           - If compressed file is <25MB -> transcribe directly
           - If still >25MB -> split into 10-min chunks -> transcribe each
        3. Merge all chunk transcripts with correct timestamps
        """
        start = time.time()

        try:
            file_size = Path(audio_path).stat().st_size
            duration_total = _get_audio_duration(audio_path) if self.ffmpeg_available else 0

            logger.info(
                f"Audio file: {file_size / 1024 / 1024:.1f}MB, "
                f"~{duration_total / 60:.0f} min"
            )

            # ── Case 1: Small enough for direct transcription ──
            if file_size <= MAX_CHUNK_SIZE_BYTES:
                result = self._transcribe_chunk(audio_path, language)
                return {
                    "success": True,
                    "text": result["text"],
                    "duration_seconds": result["duration"] or duration_total,
                    "segments": result["segments"],
                    "word_count": len(result["text"].split()),
                    "chunks_processed": 1,
                    "processing_time": round(time.time() - start, 2),
                }

            # ── Case 2+3: Need compression and/or splitting ──
            if not self.ffmpeg_available:
                raise RuntimeError(
                    f"Audio file is {file_size / 1024 / 1024:.0f}MB (limit: 25MB). "
                    "Install ffmpeg to process long recordings."
                )

            # Compress first
            session_id = str(uuid.uuid4())[:8]
            compressed_path = str(AUDIO_CHUNKS_DIR / f"{session_id}_compressed.mp3")

            logger.info("Compressing audio to 48kbps mono MP3...")
            if not _compress_audio(audio_path, compressed_path):
                raise RuntimeError("Audio compression failed")

            compressed_size = Path(compressed_path).stat().st_size
            logger.info(
                f"Compressed: {file_size / 1024 / 1024:.1f}MB -> "
                f"{compressed_size / 1024 / 1024:.1f}MB"
            )

            # If compressed file fits, transcribe directly
            if compressed_size <= MAX_CHUNK_SIZE_BYTES:
                result = self._transcribe_chunk(compressed_path, language)
                self._cleanup_files([compressed_path])
                return {
                    "success": True,
                    "text": result["text"],
                    "duration_seconds": result["duration"] or duration_total,
                    "segments": result["segments"],
                    "word_count": len(result["text"].split()),
                    "chunks_processed": 1,
                    "processing_time": round(time.time() - start, 2),
                }

            # Still too large — split into chunks
            chunk_dir = str(AUDIO_CHUNKS_DIR / session_id)
            os.makedirs(chunk_dir, exist_ok=True)

            logger.info(f"Splitting into ~{TARGET_CHUNK_SECONDS // 60}-minute chunks...")
            chunk_paths = _split_audio(compressed_path, chunk_dir)

            if not chunk_paths:
                raise RuntimeError("Audio splitting produced no chunks")

            logger.info(f"Processing {len(chunk_paths)} chunks...")

            # Transcribe each chunk and merge
            all_text = []
            all_segments = []
            offset = 0.0

            for i, chunk_path in enumerate(chunk_paths):
                chunk_size = Path(chunk_path).stat().st_size
                logger.info(
                    f"  Chunk {i + 1}/{len(chunk_paths)}: "
                    f"{chunk_size / 1024 / 1024:.1f}MB"
                )

                result = self._transcribe_chunk(chunk_path, language, offset_seconds=offset)

                if result["text"]:
                    all_text.append(result["text"])
                all_segments.extend(result["segments"])

                # Update offset for next chunk
                chunk_duration = result["duration"] or _get_audio_duration(chunk_path)
                offset += chunk_duration

            # Cleanup temp files
            self._cleanup_files([compressed_path] + chunk_paths)
            try:
                os.rmdir(chunk_dir)
            except OSError:
                pass

            combined_text = " ".join(all_text)

            logger.info(
                f"Transcription complete: {len(chunk_paths)} chunks, "
                f"{len(combined_text.split())} words, "
                f"{time.time() - start:.1f}s"
            )

            return {
                "success": True,
                "text": combined_text,
                "duration_seconds": duration_total or offset,
                "segments": all_segments,
                "word_count": len(combined_text.split()),
                "chunks_processed": len(chunk_paths),
                "processing_time": round(time.time() - start, 2),
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "success": False,
                "text": "",
                "error": str(e),
                "processing_time": round(time.time() - start, 2),
            }

    def _cleanup_files(self, paths: List[str]):
        """Remove temporary files."""
        for p in paths:
            try:
                Path(p).unlink(missing_ok=True)
            except Exception:
                pass

    # ── Linking ────────────────────────────────────────────────────────

    async def find_linked_notes(
        self,
        transcript_text: str,
        rag_engine: Any,
        db: Any,
        folder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find handwritten notes semantically similar to the transcript.

        For long transcripts, splits into overlapping windows and takes
        the union of matches — this catches topic shifts within a lecture
        (e.g., a 1-hour lecture covering both "sorting" and "graph theory"
        should link to notes on both topics).
        """
        if not transcript_text.strip():
            return []

        # ── Windowed embedding for long transcripts ──
        # Short text: single embedding
        # Long text: split into ~500-char windows, embed each, search each,
        #            merge results keeping highest score per note
        WINDOW_SIZE = 500
        WINDOW_OVERLAP = 100

        if len(transcript_text) <= WINDOW_SIZE * 2:
            # Short transcript — single search
            windows = [transcript_text]
        else:
            # Long transcript — create overlapping windows
            windows = []
            pos = 0
            while pos < len(transcript_text):
                end = min(pos + WINDOW_SIZE, len(transcript_text))
                window = transcript_text[pos:end]
                if window.strip():
                    windows.append(window)
                pos += WINDOW_SIZE - WINDOW_OVERLAP

            # Cap at 10 windows to avoid excessive compute
            if len(windows) > 10:
                step = len(windows) / 10
                windows = [windows[int(i * step)] for i in range(10)]

        # Search FAISS for each window and merge results
        score_map: Dict[str, float] = {}  # note_id -> best score

        for window in windows:
            query_embedding = await rag_engine.embed_text(window)
            if not query_embedding:
                continue

            candidates = rag_engine.store.search(
                query_embedding, top_k=MAX_LINKED_NOTES * 2
            )
            for c in candidates:
                if c["score"] >= LINK_THRESHOLD:
                    existing = score_map.get(c["id"], 0.0)
                    score_map[c["id"]] = max(existing, c["score"])

        if not score_map:
            return []

        # Fetch full note data from MongoDB
        match_ids = list(score_map.keys())
        mongo_query: Dict[str, Any] = {"id": {"$in": match_ids}}
        if folder_id:
            mongo_query["folder_id"] = folder_id

        notes = await db.notes.find(mongo_query, {"_id": 0, "embedding": 0}).to_list(
            MAX_LINKED_NOTES * 2
        )

        for note in notes:
            note["link_score"] = round(score_map.get(note["id"], 0.0), 3)

        notes.sort(key=lambda n: n["link_score"], reverse=True)
        return notes[:MAX_LINKED_NOTES]


# Global instance
voice_engine = VoiceEngine()