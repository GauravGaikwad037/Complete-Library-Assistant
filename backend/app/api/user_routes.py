from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from ..rag.engine import rag_engine
from ..services.library_service import circulation_service
from .deps import get_current_user

router = APIRouter(prefix="/api/user", tags=["Student"])

class AskQuestionRequest(BaseModel):
    query: str = Field(..., min_length=1)
    book_id: Optional[str] = None

class StudentBorrowRequestPayload(BaseModel):
    book_id: str = Field(..., min_length=1)
    notes: Optional[str] = ""

# ----------------- Student Dashboard -----------------
@router.get("/dashboard")
async def get_student_dashboard(user: dict = Depends(get_current_user)):
    """Returns student personal dashboard statistics and upcoming loans."""
    return circulation_service.get_student_dashboard(user["username"])

# ----------------- Library Catalogue -----------------
@router.get("/books")
async def get_catalogue_books(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
):
    """
    Returns books with dynamic availability classification:
    - Available (>= 2 copies)
    - Limited Copies (== 1 copy)
    - Currently Unavailable (0 copies)
    """
    books = rag_engine.get_books()
    if category and category != "all":
        books = [b for b in books if b.get("category", "").lower() == category.lower()]

    if search and search.strip():
        s = search.strip().lower()
        books = [
            b for b in books if (
                s in b.get("title", "").lower() or
                s in b.get("author", "").lower() or
                s in b.get("category", "").lower() or
                s in b.get("isbn", "").lower() or
                s in b.get("description", "").lower()
            )
        ]

    for b in books:
        avail = b.get("available_copies", 0)
        if avail >= 2:
            b["availability_status"] = "Available"
        elif avail == 1:
            b["availability_status"] = "Limited Copies"
        else:
            b["availability_status"] = "Currently Unavailable"

    return books

@router.get("/catalogue")
async def get_catalogue_alias(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None)
):
    return await get_catalogue_books(search=search, category=category)

# ----------------- Borrowing Workflow -----------------
@router.post("/borrow-request")
async def request_borrow_book(
    payload: StudentBorrowRequestPayload,
    user: dict = Depends(get_current_user)
):
    """Allows student to submit a borrowing request for an available book."""
    try:
        req = circulation_service.create_borrow_request(
            student_id=user["username"],
            student_name=user["name"],
            book_id=payload.book_id,
            notes=payload.notes or ""
        )
        return {
            "status": "success",
            "message": f"Borrowing request for '{req['book_title']}' submitted successfully. Awaiting librarian approval.",
            "request": req
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/my-books")
async def get_my_books(user: dict = Depends(get_current_user)):
    """Returns student's currently borrowed books, pending requests, and history."""
    return circulation_service.get_student_books(user["username"])

# ----------------- AI Research Assistant -----------------
@router.post("/ask")
async def ask_library_assistant(
    req: AskQuestionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Executes the 5-Stage RAG Pipeline with compulsory Google Gemini LLM generation.
    Returns transparent stages, evidence citations, and stores student query history.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    try:
        result = rag_engine.query_rag(
            query=req.query.strip(),
            book_id=req.book_id if req.book_id and req.book_id != "all" else None
        )

        # Record student query history
        circulation_service.add_query_history(
            student_id=user["username"],
            query=req.query.strip(),
            book_id=req.book_id,
            book_title=result.get("book_title", "Library Knowledge Base"),
            answer=result.get("answer", ""),
            sources=result.get("matched_chunks", []),
            model_used=result.get("model_used", "Google Gemini")
        )

        return result
    except RuntimeError as e:
        # Per specification: report real Gemini failure; never trigger a local answer fallback
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Assistant query error: {str(e)}")

# ----------------- Query History -----------------
@router.get("/query-history")
async def get_query_history(user: dict = Depends(get_current_user)):
    """Returns student's past research assistant queries."""
    return circulation_service.get_student_query_history(user["username"])

@router.delete("/query-history")
async def clear_query_history(user: dict = Depends(get_current_user)):
    """Clears query history for the logged-in student."""
    circulation_service.clear_student_query_history(user["username"])
    return {"status": "success", "message": "Query history cleared."}
