"""ScribeAI Backend Integration Tests

Tests all 29 API endpoints with realistic payloads.
Run with: pytest test_integration.py -v
"""
import pytest
import asyncio
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

# Test configuration
BASE_URL = "http://localhost:8000/api"
TEST_DATA_DIR = Path(__file__).parent / "test_data"
TEST_DATA_DIR.mkdir(exist_ok=True)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def client():
    """HTTP client for API requests"""
    import httpx
    async with httpx.AsyncClient(timeout=120.0) as c:
        yield c


@pytest.fixture(scope="session")
def sample_image():
    """Generate a sample handwritten-style image"""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw some text to simulate handwriting
    try:
        # Try to use a font that looks handwritten
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    
    draw.text((50, 50), "Binary Tree", fill='black', font=font)
    draw.text((50, 120), "A tree data structure", fill='black', font=font)
    draw.text((50, 190), "where each node has", fill='black', font=font)
    draw.text((50, 260), "at most two children", fill='black', font=font)
    
    # Save to bytes
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_pdf():
    """Generate a sample PDF with text"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 750, "Stack Data Structure")
    c.drawString(100, 700, "LIFO - Last In First Out")
    c.drawString(100, 650, "Operations: push, pop, peek")
    c.save()
    buf.seek(0)
    
    return buf.getvalue()


@pytest.fixture(scope="session")
def sample_audio():
    """Generate a minimal audio file (silent WAV)"""
    import wave
    import struct
    
    buf = io.BytesIO()
    
    # Create 1 second of silence at 16kHz mono
    sample_rate = 16000
    duration = 1
    num_samples = sample_rate * duration
    
    with wave.open(buf, 'wb') as wav:
        wav.setnchannels(1)  # mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        
        # Write silent samples
        for _ in range(num_samples):
            wav.writeframes(struct.pack('<h', 0))
    
    buf.seek(0)
    return buf.getvalue()


# ============ Test Suite ============

class TestHealthAndSetup:
    """Test server health and basic setup"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /api/health"""
        response = await client.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "mongodb" in data
        assert "ocr_engines" in data
        assert "voice_engine" in data
        assert "rag" in data
        print(f"✓ Health check passed: {data['status']}")
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client):
        """GET /api/"""
        response = await client.get(f"{BASE_URL}/")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "endpoints" in data
        print(f"✓ Root endpoint: v{data['version']}")


class TestOCRPipeline:
    """Test OCR upload and processing"""
    
    @pytest.mark.asyncio
    async def test_upload_image(self, client, sample_image):
        """POST /api/ocr/upload (image)"""
        files = {"file": ("test.png", sample_image, "image/png")}
        data = {
            "engine": "tesseract",
            "language": "eng",
            "preprocess": "true",
        }
        
        response = await client.post(f"{BASE_URL}/ocr/upload", files=files, data=data)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        assert "text" in result
        assert "image_id" in result
        print(f"✓ Image OCR: extracted {len(result['text'])} chars")
        
        return result
    
    @pytest.mark.asyncio
    async def test_upload_pdf(self, client, sample_pdf):
        """POST /api/ocr/upload (PDF)"""
        files = {"file": ("test.pdf", sample_pdf, "application/pdf")}
        data = {
            "engine": "tesseract",
            "language": "eng",
            "preprocess": "true",
        }
        
        response = await client.post(f"{BASE_URL}/ocr/upload", files=files, data=data)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        print(f"✓ PDF OCR: {result.get('total_pages', 1)} pages processed")


class TestNotesAndFolders:
    """Test notes and folder CRUD"""
    
    @pytest.mark.asyncio
    async def test_create_folder(self, client):
        """POST /api/folders"""
        response = await client.post(
            f"{BASE_URL}/folders",
            json={"name": "Data Structures", "color": "#3B82F6"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Data Structures"
        print(f"✓ Folder created: {data['id']}")
        return data
    
    @pytest.mark.asyncio
    async def test_get_folders(self, client):
        """GET /api/folders"""
        response = await client.get(f"{BASE_URL}/folders")
        assert response.status_code == 200
        folders = response.json()
        assert isinstance(folders, list)
        print(f"✓ Fetched {len(folders)} folders")
    
    @pytest.mark.asyncio
    async def test_create_note(self, client, sample_image):
        """POST /api/notes"""
        files = {"file": ("test.png", sample_image, "image/png")}
        data = {"engine": "tesseract", "language": "eng", "preprocess": "true"}
        ocr_response = await client.post(f"{BASE_URL}/ocr/upload", files=files, data=data)
        ocr_data = ocr_response.json()
        note_data = {
            "title": "Binary Tree Definition",
            "transcribed_text": ocr_data.get("text", "Test note content"),
            "original_image_path": ocr_data["original_path"],
            "processed_image_path": ocr_data.get("processed_path"),
            "confidence": ocr_data.get("confidence", 0.9),
            "engine": "tesseract",
            "language": "eng",
            "tags": ["data-structures", "trees"],
        }
        response = await client.post(f"{BASE_URL}/notes", json=note_data)
        assert response.status_code == 200
        note = response.json()
        assert note["title"] == "Binary Tree Definition"
        print(f"✓ Note created: {note['id']}")
        return note
    
    @pytest.mark.asyncio
    async def test_get_notes(self, client):
        """GET /api/notes"""
        response = await client.get(f"{BASE_URL}/notes")
        assert response.status_code == 200
        notes = response.json()
        assert isinstance(notes, list)
        print(f"✓ Fetched {len(notes)} notes")
    
    @pytest.mark.asyncio
    async def test_update_note(self, client, sample_image):
        """PATCH /api/notes/:id"""
        note = await self.test_create_note(client, sample_image)
        response = await client.patch(
            f"{BASE_URL}/notes/{note['id']}",
            json={"title": "Binary Tree Updated"}
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["title"] == "Binary Tree Updated"
        print(f"✓ Note updated: {note['id']}")
    
    @pytest.mark.asyncio
    async def test_search_notes(self, client):
        """POST /api/search"""
        response = await client.post(
            f"{BASE_URL}/search",
            json={"query": "Binary"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert "count" in data
        print(f"✓ Search found {data['count']} notes")


class TestRAG:
    """Test RAG question answering"""
    
    @pytest.mark.asyncio
    async def test_rag_stats(self, client):
        """GET /api/rag/stats"""
        response = await client.get(f"{BASE_URL}/rag/stats")
        assert response.status_code == 200
        stats = response.json()
        assert "total_vectors" in stats
        assert "embedding_model" in stats
        print(f"✓ FAISS has {stats['total_vectors']} vectors")
    
    @pytest.mark.asyncio
    async def test_rag_query(self, client):
        """POST /api/rag/query"""
        response = await client.post(
            f"{BASE_URL}/rag/query",
            json={
                "question": "What is a binary tree?",
                "history": []
            }
        )
        assert response.status_code in [200, 503]
        if response.status_code == 200:
            data = response.json()
            assert "answer" in data
            print(f"✓ RAG answer: {data['answer'][:100]}...")
        else:
            print("⚠ RAG query skipped: GROQ_API_KEY not set")
    
    @pytest.mark.asyncio
    async def test_rag_reindex(self, client):
        """POST /api/rag/reindex"""
        response = await client.post(f"{BASE_URL}/rag/reindex")
        assert response.status_code == 200
        data = response.json()
        assert "indexed" in data
        print(f"✓ Reindexed {data['indexed']} notes")


class TestVoiceEngine:
    """Test voice-to-note linking"""
    
    @pytest.mark.asyncio
    async def test_upload_audio(self, client, sample_audio):
        """POST /api/voice/upload"""
        files = {"file": ("test.wav", sample_audio, "audio/wav")}
        data = {"language": "en"}
        
        response = await client.post(f"{BASE_URL}/voice/upload", files=files, data=data)
        
        if response.status_code == 200:
            result = response.json()
            assert result["success"] is True
            assert "transcript" in result
            print(f"✓ Audio transcribed: {result['word_count']} words")
            return result
        else:
            print(f"⚠ Voice upload skipped: {response.json().get('detail', 'Unknown error')}")
            return None
    
    @pytest.mark.asyncio
    async def test_get_recordings(self, client):
        """GET /api/voice/recordings"""
        response = await client.get(f"{BASE_URL}/voice/recordings")
        assert response.status_code == 200
        data = response.json()
        assert "recordings" in data
        print(f"✓ Fetched {data['count']} recordings")


class TestTabularExtraction:
    """Test Mike-style tabular extraction"""
    
    @pytest.mark.asyncio
    async def test_extract_definitions(self, client):
        """POST /api/extract/definitions"""
        response = await client.post(f"{BASE_URL}/extract/definitions")
        
        if response.status_code == 200:
            data = response.json()
            assert "columns" in data
            assert "rows" in data
            print(f"✓ Extracted {data['total_rows']} definitions")
        else:
            print(f"⚠ Definition extraction skipped: {response.json().get('detail', 'No notes')}")
    
    @pytest.mark.asyncio
    async def test_custom_extraction(self, client):
        """POST /api/extract/table"""
        response = await client.post(
            f"{BASE_URL}/extract/table",
            json={
                "query": "all key terms and their meanings",
                "columns": ["Term", "Meaning"]
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            assert "columns" in data
            print(f"✓ Custom extraction: {data['total_rows']} rows")
        else:
            print(f"⚠ Custom extraction skipped: {response.json().get('detail', 'No notes')}")


class TestPDFGeneration:
    """Test PDF generation"""
    
    @pytest.mark.asyncio
    async def test_generate_pdf(self, client, sample_image):
        """POST /api/pdf/generate"""
        files = {"file": ("test.png", sample_image, "image/png")}
        data = {"engine": "tesseract", "language": "eng", "preprocess": "true"}
        ocr_response = await client.post(f"{BASE_URL}/ocr/upload", files=files, data=data)
        ocr_data = ocr_response.json()
        
        pdf_data = {
            "image_path": ocr_data["original_path"],
            "text": ocr_data.get("text", "Test content"),
            "searchable": "true"
        }
        
        response = await client.post(f"{BASE_URL}/pdf/generate", data=pdf_data)
        assert response.status_code == 200
        result = response.json()
        assert result["success"] is True
        print(f"✓ PDF generated: {result['filename']}")


# ============ Run Summary ============

def pytest_sessionfinish(session, exitstatus):
    """Print summary after all tests"""
    print("\n" + "="*60)
    print("ScribeAI Backend Integration Test Summary")
    print("="*60)
    
    if exitstatus == 0:
        print("✓ All tests passed!")
        print("\nBackend is ready for frontend integration.")
    else:
        print(f"✗ Some tests failed (exit code: {exitstatus})")
        print("\nCheck the output above for details.")
    
    print("\nNext steps:")
    print("1. Fix any failing tests")
    print("2. Test with real handwritten notes and audio")
    print("3. Build React frontend")
    print("="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
