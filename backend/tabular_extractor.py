"""Tabular Extraction Engine

Extract structured information across multiple notes into a
spreadsheet-style table. Each cell is cited back to the source note.

Example queries:
  - "Extract all definitions from my notes"
  - "List all formulas with their descriptions"
  - "Find all key dates and events"
  - "Extract all theorems and their proofs"
"""
import os
import json
import logging
from typing import Any, Dict, List, Optional
logger = logging.getLogger(__name__)

CHAT_MODEL = "llama-3.1-8b-instant"
MAX_CONTEXT_CHARS = 8000


class TabularExtractor:
    """Extract structured data from notes into cited tables."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from groq import AsyncGroq
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_API_KEY is not set")
            self._client = AsyncGroq(api_key=api_key)
        return self._client

    async def extract(
        self,
        query: str,
        notes: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Run tabular extraction across a list of notes.

        Args:
            query: What to extract, e.g. "all definitions", "key formulas"
            notes: List of note dicts with 'id', 'title', 'transcribed_text'
            columns: Optional column names for the table. If not provided,
                     the LLM will auto-detect appropriate columns.

        Returns:
            {
                "query": str,
                "columns": ["Term", "Definition", "Source Note"],
                "rows": [
                    {"Term": "...", "Definition": "...", "source_note_id": "...", "source_note_title": "..."},
                    ...
                ],
                "total_rows": int,
                "notes_processed": int,
            }
        """
        if not notes:
            return {
                "query": query,
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "notes_processed": 0,
            }

        # Build context from notes, respecting size limit
        context_parts = []
        total = 0
        notes_included = 0
        for note in notes:
            text = note.get("transcribed_text", "").strip()
            if not text:
                continue
            block = f'[NOTE_ID: {note["id"]} | TITLE: {note.get("title", "Untitled")}]\n{text}'
            if total + len(block) > MAX_CONTEXT_CHARS:
                break
            context_parts.append(block)
            total += len(block)
            notes_included += 1

        if not context_parts:
            return {
                "query": query,
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "notes_processed": 0,
            }

        context_block = "\n\n---\n\n".join(context_parts)

        # Build the extraction prompt
        if columns:
            columns_instruction = (
                f"Use exactly these columns: {json.dumps(columns)}. "
                f"Add a 'source_note_id' and 'source_note_title' column to every row."
            )
        else:
            columns_instruction = (
                "Auto-detect the most appropriate columns for the data. "
                "Always include a 'source_note_id' and 'source_note_title' column "
                "so every row is traceable to its source note."
            )

        system_prompt = (
            "You are a data extraction assistant. You extract structured information "
            "from students' handwritten notes (which have been OCR'd) into a JSON table.\n\n"
            "Rules:\n"
            "1. Extract ONLY information that is explicitly present in the notes.\n"
            "2. Every row MUST include 'source_note_id' and 'source_note_title' from the [NOTE_ID] and [TITLE] tags.\n"
            "3. If a note contains no relevant information for the query, skip it.\n"
            "4. Do NOT hallucinate or invent information not in the notes.\n"
            "5. Return ONLY valid JSON — no markdown, no explanation, no backticks.\n\n"
            f"Column instructions: {columns_instruction}\n\n"
            "Return format:\n"
            '{"columns": ["col1", "col2", "source_note_id", "source_note_title"], '
            '"rows": [{"col1": "...", "col2": "...", "source_note_id": "...", "source_note_title": "..."}, ...]}'
        )

        user_message = (
            f"Extract the following from these notes: {query}\n\n"
            f"Notes:\n\n{context_block}"
        )

        try:
            client = self._get_client()
            response = await client.chat.completions.create(
                model=CHAT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=2048,
            )

            raw_text = response.choices[0].message.content.strip()

            # Clean potential markdown fences
            if raw_text.startswith("```"):
                raw_text = raw_text.split("\n", 1)[-1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]
            raw_text = raw_text.strip()

            parsed = json.loads(raw_text)
            result_columns = parsed.get("columns", [])
            result_rows = parsed.get("rows", [])

            logger.info(
                f"Tabular extraction: {len(result_rows)} rows, "
                f"{len(result_columns)} columns from {notes_included} notes"
            )

            return {
                "query": query,
                "columns": result_columns,
                "rows": result_rows,
                "total_rows": len(result_rows),
                "notes_processed": notes_included,
            }

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.debug(f"Raw response: {raw_text[:500]}")
            return {
                "query": query,
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "notes_processed": notes_included,
                "error": "Failed to parse extraction results",
            }
        except Exception as e:
            logger.error(f"Tabular extraction failed: {e}")
            return {
                "query": query,
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "notes_processed": 0,
                "error": str(e),
            }

    # ── Preset extraction templates ────────────────────────────────────

    async def extract_definitions(self, notes: List[Dict]) -> Dict:
        """Extract all definitions from notes."""
        return await self.extract(
            query="all definitions, key terms, and their meanings",
            notes=notes,
            columns=["Term", "Definition"],
        )

    async def extract_formulas(self, notes: List[Dict]) -> Dict:
        """Extract all formulas and equations from notes."""
        return await self.extract(
            query="all formulas, equations, and mathematical expressions with their names or descriptions",
            notes=notes,
            columns=["Formula/Equation", "Name", "Description"],
        )

    async def extract_key_points(self, notes: List[Dict]) -> Dict:
        """Extract key points and summaries from notes."""
        return await self.extract(
            query="all key points, important facts, and main takeaways",
            notes=notes,
            columns=["Key Point", "Topic"],
        )

    async def extract_dates_events(self, notes: List[Dict]) -> Dict:
        """Extract dates and events from notes."""
        return await self.extract(
            query="all dates, events, deadlines, and milestones mentioned",
            notes=notes,
            columns=["Date", "Event", "Details"],
        )


# Global instance
tabular_extractor = TabularExtractor()
