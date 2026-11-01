from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from ..rag.engine import rag_engine
from ..rag.chunker import extract_text_from_pdf
from ..services.library_service import circulation_service
from .deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"])

class AddBookRequest(BaseModel):
    title: str = Field(..., min_length=1)
    author: str = Field("Unknown Author")
    year: int = Field(2026)
    category: str = Field("General")
    isbn: Optional[str] = None
    description: Optional[str] = None
    total_copies: int = Field(5, ge=1)
    raw_text: Optional[str] = ""

class UpdateBookRequest(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    year: Optional[int] = None
    category: Optional[str] = None
    isbn: Optional[str] = None
    description: Optional[str] = None
    total_copies: Optional[int] = None

class RejectRequestPayload(BaseModel):
    reason: str = Field(..., min_length=1)

class DirectIssuePayload(BaseModel):
    student_id: str = Field(..., min_length=1)
    student_name: str = Field(..., min_length=1)
    book_id: str = Field(..., min_length=1)
    loan_duration_days: int = Field(14, ge=1, le=90)

class KeyUpdateRequest(BaseModel):
    api_key: str

# ----------------- Dashboard -----------------
@router.get("/dashboard")
async def get_admin_dashboard(user: dict = Depends(require_admin)):
    """Admin summary statistics from actual stored data."""
    return circulation_service.get_admin_dashboard()

# ----------------- Books Management -----------------
@router.get("/books")
async def get_all_books():
    """Returns all registered library books with current availability."""
    return rag_engine.get_books()

@router.post("/books")
async def add_book_record(req: AddBookRequest, user: dict = Depends(require_admin)):
    """Adds a new book record with metadata and physical copy inventory."""
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="Book title is required.")

    res = rag_engine.add_book(
        title=req.title.strip(),
        author=req.author.strip() or "Unknown Author",
        year=req.year,
        category=req.category.strip() or "General",
        raw_text=req.raw_text.strip() if req.raw_text else f"Catalogue entry for {req.title.strip()} by {req.author.strip()}.",
        isbn=req.isbn,
        description=req.description,
        total_copies=req.total_copies
    )

    circulation_service.log_activity(
        event_type="book_added",
        description=f"Added new book '{req.title.strip()}' with {req.total_copies} copies.",
        book_id=res["book"]["id"]
    )

    return {
        "status": "success",
        "message": f"Book '{req.title}' registered successfully with {req.total_copies} physical copies.",
        "book": res["book"],
        "chunks_count": res["chunks_count"]
    }

@router.put("/books/{book_id}")
async def edit_book(book_id: str, req: UpdateBookRequest, user: dict = Depends(require_admin)):
    """Edits book metadata, updating physical copy counts and chunk headers."""
    updates = {k: v for k, v in req.dict().items() if v is not None}
    updated = rag_engine.update_book(book_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Book not found.")

    circulation_service.log_activity(
        event_type="book_updated",
        description=f"Updated details for '{updated['title']}'.",
        book_id=book_id
    )

    return {
        "status": "success",
        "message": f"Book '{updated['title']}' updated successfully.",
        "book": updated
    }

@router.delete("/books/{book_id}")
async def delete_book(book_id: str, user: dict = Depends(require_admin)):
    """Deletes a book only if it has no active loans."""
    book = rag_engine.get_book_by_id(book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found.")

    if circulation_service.has_active_loans(book_id):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete '{book['title']}'. There are currently active loans issued to students. Mark all loans returned first."
        )

    title = book["title"]
    success = rag_engine.delete_book(book_id)
    if not success:
        raise HTTPException(status_code=404, detail="Failed to delete book record.")

    circulation_service.log_activity(
        event_type="book_deleted",
        description=f"Removed book '{title}' and all its RAG chunks from library.",
        book_id=book_id
    )

    return {
        "status": "success",
        "message": f"Book '{title}' and all associated RAG chunks removed successfully."
    }

# ----------------- Document Ingestion & Upload -----------------
@router.post("/books/upload")
async def add_book_upload(
    title: str = Form(...),
    author: str = Form("Unknown Author"),
    year: int = Form(2026),
    category: str = Form("General"),
    isbn: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    total_copies: int = Form(5),
    raw_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    user: dict = Depends(require_admin)
):
    """
    Ingests PDF, TXT, or Markdown documents with exact page preservation (for PDF)
    into the RAG knowledge base.
    """
    extracted_text = ""
    is_pdf = False
    content_bytes = None

    if file and file.filename:
        content_bytes = await file.read()
        fname_lower = file.filename.lower()
        if fname_lower.endswith(".pdf"):
            is_pdf = True
            try:
                extracted_text = extract_text_from_pdf(content_bytes)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to read PDF document: {str(e)}")
        else:
            try:
                extracted_text = content_bytes.decode("utf-8", errors="replace")
            except Exception:
                extracted_text = content_bytes.decode("latin-1", errors="replace")

    if not extracted_text and raw_text:
        extracted_text = raw_text

    if not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Please provide text either by uploading a PDF/TXT document or using the paste field."
        )

    res = rag_engine.add_book(
        title=title.strip(),
        author=author.strip(),
        year=year,
        category=category.strip(),
        raw_text=extracted_text.strip(),
        isbn=isbn,
        description=description,
        total_copies=max(1, total_copies),
        source_document=file.filename if file and file.filename else "Uploaded Text Material",
        file_bytes=content_bytes if is_pdf else None,
        is_pdf=is_pdf
    )

    circulation_service.log_activity(
        event_type="book_ingested",
        description=f"Ingested document for '{title.strip()}' ({res['chunks_count']} RAG chunks).",
        book_id=res["book"]["id"]
    )

    return {
        "status": "success",
        "message": f"Document '{title}' successfully indexed into {res['chunks_count']} RAG chunks!",
        "book": res["book"],
        "chunks_count": res["chunks_count"],
        "sample_chunk": res["sample_chunk"]
    }

# Backward compatibility with existing add-json route
@router.post("/books/add-json")
async def add_book_json(req: AddBookRequest, user: dict = Depends(require_admin)):
    return await add_book_record(req, user)

# ----------------- Chunks Inspector -----------------
@router.get("/chunks")
async def get_chunks(book_id: Optional[str] = Query(None)):
    """Inspects RAG chunks with page tracking and metadata."""
    if book_id and book_id != "all":
        return rag_engine.get_book_chunks(book_id)
    chunks = rag_engine._load_chunks()
    for c in chunks:
        rag_engine._enrich_chunk_position(c)
    return chunks

@router.get("/books/{book_id}/chunks")
async def get_book_chunks(book_id: str):
    chunks = rag_engine.get_book_chunks(book_id)
    if not chunks:
        raise HTTPException(status_code=404, detail="No chunks found for this book ID.")
    return chunks

# ----------------- Borrowing Management -----------------
@router.get("/borrowing/requests")
async def get_borrowing_requests(status: Optional[str] = Query(None), user: dict = Depends(require_admin)):
    """Lists student borrowing requests."""
    return circulation_service.get_requests(status=status)

@router.post("/borrowing/requests/{request_id}/approve")
async def approve_request(request_id: str, loan_duration_days: int = Query(14), user: dict = Depends(require_admin)):
    """Approves a student borrowing request, reduces copy count, and creates an issued loan."""
    try:
        res = circulation_service.approve_borrow_request(request_id, loan_duration_days=loan_duration_days)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/borrowing/requests/{request_id}/reject")
async def reject_request(request_id: str, payload: RejectRequestPayload, user: dict = Depends(require_admin)):
    """Rejects a student borrowing request with an explanatory reason."""
    try:
        res = circulation_service.reject_borrow_request(request_id, reason=payload.reason)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/borrowing/loans")
async def get_loans(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    user: dict = Depends(require_admin)
):
    """Lists issued and returned loans with overdue status calculation."""
    return circulation_service.get_loans(status=status, search=search)

@router.post("/borrowing/loans/{loan_id}/return")
async def return_loan_record(loan_id: str, user: dict = Depends(require_admin)):
    """Marks an issued book as returned and restores inventory copy count."""
    try:
        res = circulation_service.return_loan(loan_id)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/borrowing/issue-direct")
async def issue_direct_loan(payload: DirectIssuePayload, user: dict = Depends(require_admin)):
    """Directly issues a book to a student without an online request."""
    try:
        loan = circulation_service.issue_direct_loan(
            student_id=payload.student_id,
            student_name=payload.student_name,
            book_id=payload.book_id,
            loan_duration_days=payload.loan_duration_days
        )
        return {"status": "success", "message": f"Book issued directly to {payload.student_name}.", "loan": loan}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------- Status & Settings -----------------
@router.post("/set-key")
async def set_gemini_key(req: KeyUpdateRequest, user: dict = Depends(require_admin)):
    if not req.api_key.strip():
        raise HTTPException(status_code=400, detail="API key cannot be empty.")
    rag_engine.set_api_key(req.api_key.strip())
    status = rag_engine.validate_gemini_connection(force_check=True)
    return {
        "status": "success",
        "has_key": status["has_key"],
        "is_valid": status["is_valid"],
        "message": status["message"]
    }

@router.get("/status")
async def get_system_status():
    books = rag_engine.get_books()
    chunks = rag_engine._load_chunks()
    validation = rag_engine.validate_gemini_connection(force_check=False)
    return {
        "status": "operational",
        "total_books": len(books),
        "total_chunks": len(chunks),
        "has_gemini_key": validation["has_key"],
        "is_gemini_valid": validation["is_valid"],
        "gemini_status": validation["status"],
        "active_model": validation["model"],
        "message": validation["message"]
    }
