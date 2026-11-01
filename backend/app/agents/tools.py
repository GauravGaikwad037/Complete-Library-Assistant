import json
import os
import re
from typing import List, Dict, Any, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def load_catalog() -> List[Dict[str, Any]]:
    path = os.path.join(DATA_DIR, "catalog.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_catalog(books: List[Dict[str, Any]]):
    path = os.path.join(DATA_DIR, "catalog.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(books, f, indent=2)

def load_map_data() -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, "library_map.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_map_data(data: Dict[str, Any]):
    path = os.path.join(DATA_DIR, "library_map.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# Tool 1: Semantic Catalog Search
def tool_catalog_search(query: str, category: Optional[str] = None, top_k: int = 4) -> Dict[str, Any]:
    """
    Search library catalog by natural language query, title, author, concept, or tags.
    Returns ranked books with relevance score.
    """
    books = load_catalog()
    query_tokens = [t.lower() for t in re.findall(r'\w+', query) if len(t) > 2]
    
    scored_books = []
    for b in books:
        score = 0.0
        b_title = b["title"].lower()
        b_author = b["author"].lower()
        b_summary = b["summary"].lower()
        b_category = b.get("category", "").lower()
        b_tags = [t.lower() for t in b.get("tags", [])]
        b_concepts = [c.lower() for c in b.get("key_concepts", [])]
        
        # Category filter if provided
        if category and category.lower() not in b_category:
            continue
            
        # Exact title match bonus
        if query.lower() in b_title:
            score += 15.0
            
        for tok in query_tokens:
            if tok in b_title:
                score += 5.0
            if tok in b_author:
                score += 4.0
            if tok in b_tags:
                score += 3.5
            if any(tok in c for c in b_concepts):
                score += 3.0
            if tok in b_summary:
                score += 1.5
            if tok in b_category:
                score += 2.0
                
        if score > 0:
            scored_books.append((score, b))
            
    # Sort descending by score
    scored_books.sort(key=lambda x: x[0], reverse=True)
    results = [item[1] for item in scored_books[:top_k]]
    
    # If no strict token match, provide top relevant books
    if not results and books:
        results = books[:top_k]
        
    return {
        "status": "success",
        "query": query,
        "match_count": len(results),
        "books": results
    }

# Tool 2: Physical Shelf Locator
def tool_shelf_locator(book_id_or_title: str) -> Dict[str, Any]:
    """
    Locates the physical shelf in the library stacks for a book by ID or title.
    Returns floor, wing, aisle, rack, shelf number, call number and 2.5D coordinates.
    """
    books = load_catalog()
    target_book = None
    query = book_id_or_title.lower().strip()
    
    for b in books:
        if b["id"].lower() == query or query in b["title"].lower():
            target_book = b
            break
            
    if not target_book:
        # fallback to closest match
        search_res = tool_catalog_search(book_id_or_title, top_k=1)
        if search_res["books"]:
            target_book = search_res["books"][0]
            
    if not target_book:
        return {"status": "not_found", "message": f"Could not find shelf location for '{book_id_or_title}'"}
        
    loc = target_book["physical_location"]
    return {
        "status": "success",
        "book_id": target_book["id"],
        "title": target_book["title"],
        "call_number": target_book["call_number"],
        "floor": loc["floor"],
        "floor_name": loc["floor_name"],
        "wing": loc["wing"],
        "aisle": loc["aisle"],
        "rack": loc["rack"],
        "shelf": loc["shelf"],
        "zone_color": loc.get("zone_color", "#06b6d4"),
        "map_coords": loc.get("map_coords", {"x": 100, "y": 100}),
        "navigation_hint": f"Take stairs/elevator to {loc['floor_name']}, head to {loc['wing']}, locate {loc['aisle']}, {loc['rack']}, on {loc['shelf']}."
    }

# Tool 3: Circulation Policy Officer
def tool_circulation_policy(role: str = "undergraduate", action: str = "borrow") -> Dict[str, Any]:
    """
    Checks loan durations, borrowing limits, late fees, and renewal rules for a user role.
    """
    map_data = load_map_data()
    policies = map_data.get("loan_policies", {})
    clean_role = role.lower().strip()
    
    policy = policies.get(clean_role, policies.get("undergraduate"))
    return {
        "status": "success",
        "user_role": clean_role,
        "max_allowed_books": policy["max_books"],
        "loan_duration_days": policy["duration_days"],
        "overdue_fine_per_day": f"${policy['fine_per_day']:.2f}",
        "max_renewals": policy["renewal_limit"],
        "rules_summary": f"{clean_role.capitalize()} users can borrow up to {policy['max_books']} books for {policy['duration_days']} days with {policy['renewal_limit']} allowed renewals. Late return fee is ${policy['fine_per_day']:.2f}/day."
    }

# Tool 4: Academic Citation Tool
def tool_academic_citation(book_id: str, style: str = "all") -> Dict[str, Any]:
    """
    Generates standard academic citations (APA, MLA, IEEE, BibTeX) for any book in the catalog.
    """
    books = load_catalog()
    target_book = None
    for b in books:
        if b["id"] == book_id or book_id.lower() in b["title"].lower():
            target_book = b
            break
            
    if not target_book:
        return {"status": "not_found", "message": f"Book '{book_id}' not found for citation"}
        
    citations = target_book.get("citations", {})
    if style.lower() in citations:
        return {
            "status": "success",
            "book_title": target_book["title"],
            "style": style,
            "citation": citations[style.lower()]
        }
        
    return {
        "status": "success",
        "book_title": target_book["title"],
        "citations": citations
    }

# Tool 5: Book Study Companion
def tool_study_companion(book_id: str, action: str = "summary") -> Dict[str, Any]:
    """
    Generates structured chapter summaries, core conceptual breakdowns, or flashcards for studying.
    """
    books = load_catalog()
    target_book = next((b for b in books if b["id"] == book_id or book_id.lower() in b["title"].lower()), None)
    
    if not target_book:
        return {"status": "not_found", "message": f"Book '{book_id}' not found"}
        
    if action == "flashcards":
        flashcards = [
            {
                "question": f"What is the central premise of '{target_book['title']}'?",
                "answer": target_book['summary'][:180] + "..."
            },
            {
                "question": f"Which core concept does this book focus on?",
                "answer": target_book['key_concepts'][0] if target_book['key_concepts'] else "Core foundation principles."
            },
            {
                "question": "What is a practical application discussed in this work?",
                "answer": f"It is applied in {target_book['category']} for solving foundational and advanced research problems."
            }
        ]
        return {
            "status": "success",
            "book_id": target_book["id"],
            "title": target_book["title"],
            "type": "flashcards",
            "flashcards": flashcards
        }
        
    return {
        "status": "success",
        "book_id": target_book["id"],
        "title": target_book["title"],
        "summary": target_book["summary"],
        "key_concepts": target_book.get("key_concepts", []),
        "table_of_contents": target_book.get("table_of_contents", [])
    }

# Tool 6: Study Room & Resource Reservation
def tool_room_reservation(room_id: Optional[str] = None, user_name: str = "Student", time_slot: Optional[str] = None) -> Dict[str, Any]:
    """
    Queries or reserves collaborative study rooms across library floors.
    """
    map_data = load_map_data()
    all_rooms = []
    for fl in map_data.get("floors", []):
        for rm in fl.get("study_rooms", []):
            rm_copy = dict(rm)
            rm_copy["floor_id"] = fl["id"]
            rm_copy["floor_name"] = fl["name"]
            all_rooms.append(rm_copy)
            
    if not room_id:
        return {
            "status": "success",
            "action": "list",
            "rooms": all_rooms
        }
        
    for fl in map_data.get("floors", []):
        for rm in fl.get("study_rooms", []):
            if rm["id"].lower() == room_id.lower() or room_id.lower() in rm["name"].lower():
                if rm["status"] == "Reserved":
                    return {
                        "status": "unavailable",
                        "message": f"Room '{rm['name']}' is currently reserved. Please choose another room."
                    }
                rm["status"] = "Reserved"
                rm["reserved_by"] = user_name
                rm["reserved_slot"] = time_slot or "Next Available (2 Hours)"
                save_map_data(map_data)
                return {
                    "status": "success",
                    "action": "reserved",
                    "room_name": rm["name"],
                    "reserved_by": user_name,
                    "slot": rm["reserved_slot"],
                    "floor": fl["name"]
                }
                
    return {"status": "not_found", "message": f"Room '{room_id}' not found"}

TOOL_REGISTRY = {
    "semantic_catalog_search": tool_catalog_search,
    "physical_shelf_locator": tool_shelf_locator,
    "circulation_policy_officer": tool_circulation_policy,
    "academic_citation_generator": tool_academic_citation,
    "book_study_companion": tool_study_companion,
    "study_room_reservation": tool_room_reservation
}
