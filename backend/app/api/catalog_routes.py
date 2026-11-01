from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
from ..agents.tools import load_catalog, save_catalog
from ..models.schemas import Book

router = APIRouter(prefix="/api/catalog", tags=["Catalog"])

@router.get("", response_model=List[Dict[str, Any]])
async def get_catalog(search: Optional[str] = None, category: Optional[str] = None):
    books = load_catalog()
    if search:
        s = search.lower()
        books = [b for b in books if s in b["title"].lower() or s in b["author"].lower() or any(s in t.lower() for t in b.get("tags", []))]
    if category and category != "All":
        books = [b for b in books if category.lower() in b.get("category", "").lower()]
    return books

@router.get("/categories")
async def get_categories():
    books = load_catalog()
    categories = set()
    for b in books:
        if b.get("category"):
            categories.add(b["category"].split("/")[0].strip())
    return sorted(list(categories))

@router.get("/{book_id}")
async def get_book_by_id(book_id: str):
    books = load_catalog()
    for b in books:
        if b["id"].lower() == book_id.lower():
            return b
    raise HTTPException(status_code=404, detail="Book not found")
