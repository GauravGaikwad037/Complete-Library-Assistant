from fastapi import APIRouter, HTTPException
from ..agents.tools import load_catalog
from ..models.schemas import StudyRequest, CitationRequest

router = APIRouter(prefix="/api/study", tags=["Study Companion"])

@router.post("/companion")
async def study_companion(req: StudyRequest):
    books = load_catalog()
    book = next((b for b in books if b["id"] == req.book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    if req.mode == "summary":
        return {
            "title": book["title"],
            "summary": book["summary"],
            "table_of_contents": book.get("table_of_contents", []),
            "key_concepts": book.get("key_concepts", [])
        }
        
    elif req.mode == "flashcards":
        cards = []
        concepts = book.get("key_concepts", [])
        for idx, c in enumerate(concepts, 1):
            cards.append({
                "id": idx,
                "front": f"Concept: {c}",
                "back": f"Defined in '{book['title']}'. Crucial theoretical framework analyzed in chapter studies."
            })
        if not cards:
            cards.append({
                "id": 1,
                "front": f"What is the primary contribution of {book['title']}?",
                "back": book["summary"][:200]
            })
        return {
            "title": book["title"],
            "flashcards": cards
        }
        
    elif req.mode == "chat":
        q = (req.query or "").lower()
        chunks = book.get("sample_chunks", [])
        matched_chunk = chunks[0] if chunks else book["summary"]
        for ch in chunks:
            if any(w in ch.lower() for w in q.split() if len(w) > 3):
                matched_chunk = ch
                break
                
        reply = f"From **'{book['title']}'** by *{book['author']}*:\n\n> \"{matched_chunk}\"\n\nIn relation to your question ('{req.query}'), the author explores how this principle operates within the broader context of {book['category']}."
        return {
            "title": book["title"],
            "answer": reply,
            "source_citation": book["citations"].get("apa", "")
        }

@router.post("/citation")
async def get_citation(req: CitationRequest):
    books = load_catalog()
    book = next((b for b in books if b["id"] == req.book_id), None)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    cites = book.get("citations", {})
    if req.format.lower() in cites:
        return {"format": req.format, "citation": cites[req.format.lower()]}
    return {"format": "all", "citations": cites}
