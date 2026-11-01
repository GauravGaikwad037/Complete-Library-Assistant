from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from datetime import datetime, timedelta
from ..agents.tools import load_catalog, save_catalog, load_map_data, save_map_data
from ..models.schemas import BorrowRequest, RoomBookingRequest

router = APIRouter(prefix="/api/circulation", tags=["Circulation"])

@router.get("/map")
async def get_library_map():
    return load_map_data()

@router.post("/borrow")
async def borrow_book(req: BorrowRequest):
    books = load_catalog()
    map_data = load_map_data()
    policies = map_data.get("loan_policies", {})
    policy = policies.get(req.user_role.lower(), policies.get("undergraduate"))
    loan_days = policy["duration_days"]

    target = None
    for b in books:
        if b["id"] == req.book_id:
            target = b
            break
            
    if not target:
        raise HTTPException(status_code=404, detail="Book not found in catalog")
        
    circ = target["circulation"]
    if circ["available_copies"] <= 0:
        raise HTTPException(status_code=400, detail="No copies currently available to borrow. You may place a hold.")
        
    circ["available_copies"] -= 1
    due_date = (datetime.now() + timedelta(days=loan_days)).strftime("%Y-%m-%d")
    borrow_record = {
        "user_id": req.user_id,
        "user_name": req.user_name,
        "borrowed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "due_date": due_date,
        "role": req.user_role
    }
    circ.setdefault("borrowed_by", []).append(borrow_record)
    save_catalog(books)
    
    return {
        "status": "success",
        "message": f"Successfully checked out '{target['title']}'",
        "book_id": target["id"],
        "title": target["title"],
        "due_date": due_date,
        "remaining_copies": circ["available_copies"],
        "loan_days": loan_days
    }

@router.post("/return")
async def return_book(book_id: str, user_id: str):
    books = load_catalog()
    target = next((b for b in books if b["id"] == book_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Book not found")
        
    circ = target["circulation"]
    borrowed_list = circ.get("borrowed_by", [])
    updated_list = [r for r in borrowed_list if r.get("user_id") != user_id]
    
    if len(updated_list) == len(borrowed_list) and circ["available_copies"] >= circ["total_copies"]:
        return {"status": "info", "message": "Book was not currently checked out by this user."}
        
    circ["available_copies"] = min(circ["total_copies"], circ["available_copies"] + 1)
    circ["borrowed_by"] = updated_list
    save_catalog(books)
    
    return {
        "status": "success",
        "message": f"Successfully returned '{target['title']}'",
        "available_copies": circ["available_copies"]
    }

@router.post("/book-room")
async def book_study_room(req: RoomBookingRequest):
    map_data = load_map_data()
    found = False
    for fl in map_data.get("floors", []):
        for rm in fl.get("study_rooms", []):
            if rm["id"] == req.room_id:
                found = True
                if rm.get("status") == "Reserved":
                    raise HTTPException(status_code=400, detail="This room is already reserved for this slot.")
                rm["status"] = "Reserved"
                rm["reserved_by"] = req.user_name
                rm["reserved_date"] = req.date
                rm["reserved_slot"] = req.time_slot
                save_map_data(map_data)
                return {
                    "status": "success",
                    "message": f"Room '{rm['name']}' booked for {req.user_name} on {req.date} at {req.time_slot}.",
                    "room": rm
                }
    if not found:
        raise HTTPException(status_code=404, detail="Study room not found")
