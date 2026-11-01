import os
import json
import uuid
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from ..rag.engine import rag_engine, DATA_DIR

REQUESTS_FILE = os.path.join(DATA_DIR, "requests.json")
LOANS_FILE = os.path.join(DATA_DIR, "loans.json")
ACTIVITY_FILE = os.path.join(DATA_DIR, "activity_log.json")
QUERY_HISTORY_FILE = os.path.join(DATA_DIR, "query_history.json")

def _safe_load_json(file_path: str, default: Any = None) -> Any:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default if default is not None else []
    return default if default is not None else []

def _safe_save_json(file_path: str, data: Any):
    temp_file = f"{file_path}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(temp_file, file_path)

class LibraryCirculationService:
    def __init__(self):
        self._ensure_seed_records()

    def _ensure_seed_records(self):
        """Initializes sample demonstration records if empty."""
        requests = _safe_load_json(REQUESTS_FILE, [])
        loans = _safe_load_json(LOANS_FILE, [])
        activity = _safe_load_json(ACTIVITY_FILE, [])

        # If completely empty, add a couple of realistic demo loan records to demonstrate features to teacher
        if not loans and not requests:
            books = rag_engine.get_books()
            if books:
                first_book = books[0]
                today_str = datetime.now().strftime("%Y-%m-%d")
                past_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
                due_date = (datetime.now() + timedelta(days=9)).strftime("%Y-%m-%d")

                demo_loan = {
                    "id": f"loan-{str(uuid.uuid4())[:8]}",
                    "request_id": f"req-demo-01",
                    "student_id": "student",
                    "student_name": "Student Scholar",
                    "book_id": first_book["id"],
                    "book_title": first_book["title"],
                    "author": first_book["author"],
                    "issue_date": past_date,
                    "loan_duration_days": 14,
                    "due_date": due_date,
                    "return_date": None,
                    "status": "Issued"
                }
                # Decrement copy count for the issued demo loan
                first_book["available_copies"] = max(0, first_book.get("available_copies", 5) - 1)
                rag_engine._save_books(books)
                _safe_save_json(LOANS_FILE, [demo_loan])

                demo_activity = [
                    {
                        "id": f"act-{str(uuid.uuid4())[:8]}",
                        "timestamp": (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M"),
                        "type": "book_issued",
                        "description": f"Issued '{first_book['title']}' to Student Scholar (Due: {due_date})",
                        "student_id": "student",
                        "book_id": first_book["id"]
                    },
                    {
                        "id": f"act-{str(uuid.uuid4())[:8]}",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "type": "system_ready",
                        "description": "VidyaAI Library System initialized with verified Google Gemini RAG",
                        "student_id": None,
                        "book_id": None
                    }
                ]
                _safe_save_json(ACTIVITY_FILE, demo_activity)

    def log_activity(self, event_type: str, description: str, student_id: Optional[str] = None, book_id: Optional[str] = None):
        activities = _safe_load_json(ACTIVITY_FILE, [])
        record = {
            "id": f"act-{str(uuid.uuid4())[:8]}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "type": event_type,
            "description": description,
            "student_id": student_id,
            "book_id": book_id
        }
        activities.insert(0, record)
        # Keep recent 100 activities
        _safe_save_json(ACTIVITY_FILE, activities[:100])

    # ------------------ Borrowing Requests ------------------
    def get_requests(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        requests = _safe_load_json(REQUESTS_FILE, [])
        if status:
            return [r for r in requests if r.get("status") == status]
        return requests

    def get_student_requests(self, student_id: str) -> List[Dict[str, Any]]:
        requests = _safe_load_json(REQUESTS_FILE, [])
        return [r for r in requests if r.get("student_id") == student_id]

    def create_borrow_request(self, student_id: str, student_name: str, book_id: str, notes: str = "") -> Dict[str, Any]:
        book = rag_engine.get_book_by_id(book_id)
        if not book:
            raise ValueError("Book not found in library inventory.")

        if book.get("available_copies", 0) <= 0:
            raise ValueError(f"All physical copies of '{book['title']}' are currently checked out. Please try again later.")

        # Check for duplicate active request by same student
        existing_requests = self.get_requests()
        for r in existing_requests:
            if r.get("student_id") == student_id and r.get("book_id") == book_id and r.get("status") == "Pending":
                raise ValueError("You already have a pending borrowing request for this book.")

        # Check if student currently has an active unreturned loan for this book
        active_loans = self.get_loans(status="Issued")
        for ln in active_loans:
            if ln.get("student_id") == student_id and ln.get("book_id") == book_id:
                raise ValueError("You currently have an active borrowed copy of this book.")

        req_id = f"req-{str(uuid.uuid4())[:8]}"
        new_req = {
            "id": req_id,
            "student_id": student_id,
            "student_name": student_name or "Student",
            "book_id": book_id,
            "book_title": book["title"],
            "author": book.get("author", "Unknown"),
            "category": book.get("category", "General"),
            "request_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "Pending",
            "rejection_reason": None,
            "notes": notes.strip()
        }

        existing_requests.insert(0, new_req)
        _safe_save_json(REQUESTS_FILE, existing_requests)

        self.log_activity(
            event_type="request_created",
            description=f"{new_req['student_name']} submitted a borrow request for '{book['title']}'",
            student_id=student_id,
            book_id=book_id
        )

        return new_req

    def approve_borrow_request(self, request_id: str, loan_duration_days: int = 14) -> Dict[str, Any]:
        requests = self.get_requests()
        target_req = next((r for r in requests if r["id"] == request_id), None)
        if not target_req:
            raise ValueError("Borrowing request not found.")

        if target_req["status"] != "Pending":
            raise ValueError(f"Cannot approve request with status '{target_req['status']}'.")

        book = rag_engine.get_book_by_id(target_req["book_id"])
        if not book:
            raise ValueError("Associated book record no longer exists.")

        if book.get("available_copies", 0) <= 0:
            raise ValueError(f"No available copies of '{book['title']}' left to issue.")

        # Decrement available copies
        books = rag_engine.get_books()
        for b in books:
            if b["id"] == book["id"]:
                b["available_copies"] = max(0, b["available_copies"] - 1)
                break
        rag_engine._save_books(books)

        # Update request status
        target_req["status"] = "Approved"
        target_req["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        _safe_save_json(REQUESTS_FILE, requests)

        # Create issued loan record
        loan_id = f"loan-{str(uuid.uuid4())[:8]}"
        today = datetime.now()
        due_date = (today + timedelta(days=loan_duration_days)).strftime("%Y-%m-%d")

        new_loan = {
            "id": loan_id,
            "request_id": target_req["id"],
            "student_id": target_req["student_id"],
            "student_name": target_req["student_name"],
            "book_id": book["id"],
            "book_title": book["title"],
            "author": book.get("author", "Unknown"),
            "issue_date": today.strftime("%Y-%m-%d"),
            "loan_duration_days": loan_duration_days,
            "due_date": due_date,
            "return_date": None,
            "status": "Issued"
        }

        loans = _safe_load_json(LOANS_FILE, [])
        loans.insert(0, new_loan)
        _safe_save_json(LOANS_FILE, loans)

        self.log_activity(
            event_type="request_approved",
            description=f"Approved request & issued '{book['title']}' to {target_req['student_name']} (Due: {due_date})",
            student_id=target_req["student_id"],
            book_id=book["id"]
        )

        return {
            "status": "success",
            "message": f"Request approved. Book '{book['title']}' issued with due date {due_date}.",
            "loan": new_loan
        }

    def reject_borrow_request(self, request_id: str, reason: str = "Unavailable or limit reached") -> Dict[str, Any]:
        requests = self.get_requests()
        target_req = next((r for r in requests if r["id"] == request_id), None)
        if not target_req:
            raise ValueError("Borrowing request not found.")

        if target_req["status"] != "Pending":
            raise ValueError(f"Cannot reject request with status '{target_req['status']}'.")

        target_req["status"] = "Rejected"
        target_req["rejection_reason"] = reason.strip() or "Request rejected by library administrator."
        target_req["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        _safe_save_json(REQUESTS_FILE, requests)

        self.log_activity(
            event_type="request_rejected",
            description=f"Rejected request for '{target_req['book_title']}' from {target_req['student_name']}: {target_req['rejection_reason']}",
            student_id=target_req["student_id"],
            book_id=target_req["book_id"]
        )

        return {
            "status": "success",
            "message": "Borrowing request marked as Rejected.",
            "request": target_req
        }

    # ------------------ Loans & Circulation ------------------
    def get_loans(self, status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        loans = _safe_load_json(LOANS_FILE, [])
        today_str = datetime.now().strftime("%Y-%m-%d")

        for ln in loans:
            if ln.get("status") == "Issued" and ln.get("due_date"):
                ln["is_overdue"] = ln["due_date"] < today_str
            else:
                ln["is_overdue"] = False

        if status:
            loans = [ln for ln in loans if ln.get("status") == status]

        if search and search.strip():
            s = search.strip().lower()
            loans = [
                ln for ln in loans if (
                    s in ln.get("book_title", "").lower() or
                    s in ln.get("student_name", "").lower() or
                    s in ln.get("student_id", "").lower() or
                    s in ln.get("author", "").lower()
                )
            ]

        return loans

    def issue_direct_loan(
        self,
        student_id: str,
        student_name: str,
        book_id: str,
        loan_duration_days: int = 14
    ) -> Dict[str, Any]:
        book = rag_engine.get_book_by_id(book_id)
        if not book:
            raise ValueError("Book not found.")

        if book.get("available_copies", 0) <= 0:
            raise ValueError(f"No available physical copies of '{book['title']}' to issue.")

        # Decrement available copies
        books = rag_engine.get_books()
        for b in books:
            if b["id"] == book["id"]:
                b["available_copies"] = max(0, b["available_copies"] - 1)
                break
        rag_engine._save_books(books)

        today = datetime.now()
        due_date = (today + timedelta(days=loan_duration_days)).strftime("%Y-%m-%d")
        loan_id = f"loan-{str(uuid.uuid4())[:8]}"

        new_loan = {
            "id": loan_id,
            "request_id": None,
            "student_id": student_id,
            "student_name": student_name,
            "book_id": book["id"],
            "book_title": book["title"],
            "author": book.get("author", "Unknown"),
            "issue_date": today.strftime("%Y-%m-%d"),
            "loan_duration_days": loan_duration_days,
            "due_date": due_date,
            "return_date": None,
            "status": "Issued"
        }

        loans = _safe_load_json(LOANS_FILE, [])
        loans.insert(0, new_loan)
        _safe_save_json(LOANS_FILE, loans)

        self.log_activity(
            event_type="book_issued",
            description=f"Direct issued '{book['title']}' to {student_name} (Due: {due_date})",
            student_id=student_id,
            book_id=book["id"]
        )

        return new_loan

    def return_loan(self, loan_id: str) -> Dict[str, Any]:
        loans = self.get_loans()
        target_loan = next((ln for ln in loans if ln["id"] == loan_id), None)
        if not target_loan:
            raise ValueError("Loan record not found.")

        if target_loan["status"] == "Returned":
            raise ValueError("This book has already been marked as returned.")

        target_loan["status"] = "Returned"
        target_loan["return_date"] = datetime.now().strftime("%Y-%m-%d")
        target_loan["is_overdue"] = False
        _safe_save_json(LOANS_FILE, loans)

        # Increment available copies exactly once
        books = rag_engine.get_books()
        for b in books:
            if b["id"] == target_loan["book_id"]:
                b["available_copies"] = min(b.get("total_copies", 5), b.get("available_copies", 0) + 1)
                break
        rag_engine._save_books(books)

        self.log_activity(
            event_type="book_returned",
            description=f"Received return for '{target_loan['book_title']}' from {target_loan['student_name']}",
            student_id=target_loan["student_id"],
            book_id=target_loan["book_id"]
        )

        return {
            "status": "success",
            "message": f"Book '{target_loan['book_title']}' marked as returned successfully.",
            "loan": target_loan
        }

    def has_active_loans(self, book_id: str) -> bool:
        loans = self.get_loans(status="Issued")
        return any(ln["book_id"] == book_id for ln in loans)

    # ------------------ Student Specific Views ------------------
    def get_student_books(self, student_id: str) -> Dict[str, Any]:
        all_loans = self.get_loans()
        student_loans = [ln for ln in all_loans if ln.get("student_id") == student_id]
        requests = self.get_student_requests(student_id)

        borrowed = [ln for ln in student_loans if ln.get("status") == "Issued"]
        returned = [ln for ln in student_loans if ln.get("status") == "Returned"]
        pending = [r for r in requests if r.get("status") == "Pending"]
        rejected = [r for r in requests if r.get("status") == "Rejected"]

        return {
            "borrowed": borrowed,
            "returned": returned,
            "pending": pending,
            "rejected": rejected,
            "history": student_loans
        }

    # ------------------ Dashboards ------------------
    def get_admin_dashboard(self) -> Dict[str, Any]:
        books = rag_engine.get_books()
        loans = self.get_loans()
        requests = self.get_requests()
        activities = _safe_load_json(ACTIVITY_FILE, [])

        total_titles = len(books)
        total_physical_copies = sum(b.get("total_copies", 5) for b in books)
        available_copies = sum(b.get("available_copies", 0) for b in books)
        issued_loans = [ln for ln in loans if ln.get("status") == "Issued"]
        issued_copies = len(issued_loans)
        pending_requests = len([r for r in requests if r.get("status") == "Pending"])
        overdue_loans = len([ln for ln in issued_loans if ln.get("is_overdue")])

        return {
            "total_titles": total_titles,
            "total_physical_copies": total_physical_copies,
            "available_copies": available_copies,
            "issued_copies": issued_copies,
            "pending_requests": pending_requests,
            "overdue_loans": overdue_loans,
            "recent_activity": activities[:10]
        }

    def get_student_dashboard(self, student_id: str) -> Dict[str, Any]:
        books = rag_engine.get_books()
        student_books = self.get_student_books(student_id)
        activities = _safe_load_json(ACTIVITY_FILE, [])

        total_available = len([b for b in books if b.get("available_copies", 0) > 0])
        borrowed = student_books["borrowed"]
        pending = student_books["pending"]
        overdue = len([ln for ln in borrowed if ln.get("is_overdue")])

        # Upcoming due dates (within 7 days)
        today = datetime.now()
        upcoming = []
        for ln in borrowed:
            try:
                due_dt = datetime.strptime(ln["due_date"], "%Y-%m-%d")
                delta_days = (due_dt - today).days
                if 0 <= delta_days <= 7:
                    upcoming.append({
                        "book_title": ln["book_title"],
                        "due_date": ln["due_date"],
                        "days_left": delta_days
                    })
            except Exception:
                pass

        # Filter recent activities for this student
        student_activity = [
            a for a in activities if a.get("student_id") == student_id or a.get("student_id") is None
        ][:8]

        return {
            "total_available_books": total_available,
            "currently_borrowed": len(borrowed),
            "pending_requests": len(pending),
            "overdue_books": overdue,
            "upcoming_due_dates": upcoming,
            "recent_activity": student_activity
        }

    # ------------------ AI Query History ------------------
    def add_query_history(
        self,
        student_id: str,
        query: str,
        book_id: Optional[str],
        book_title: str,
        answer: str,
        sources: List[Dict[str, Any]],
        model_used: str
    ):
        history = _safe_load_json(QUERY_HISTORY_FILE, [])
        record = {
            "id": f"q-{str(uuid.uuid4())[:8]}",
            "student_id": student_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "query": query,
            "book_id": book_id or "all",
            "book_title": book_title,
            "answer_preview": answer[:220] + ("..." if len(answer) > 220 else ""),
            "answer": answer,
            "sources": [
                {
                    "book_title": s.get("book_title", "Unknown"),
                    "page_label": s.get("page_label", "Page 1"),
                    "relevance_score": s.get("relevance_score", 0),
                    "chunk_id": s.get("chunk_id", ""),
                    "excerpt": s.get("text", "")[:160] + "..."
                }
                for s in sources
            ],
            "model_used": model_used
        }
        history.insert(0, record)
        # Keep recent 200 queries
        _safe_save_json(QUERY_HISTORY_FILE, history[:200])

    def get_student_query_history(self, student_id: str) -> List[Dict[str, Any]]:
        history = _safe_load_json(QUERY_HISTORY_FILE, [])
        return [q for q in history if q.get("student_id") == student_id]

    def clear_student_query_history(self, student_id: str):
        history = _safe_load_json(QUERY_HISTORY_FILE, [])
        remaining = [q for q in history if q.get("student_id") != student_id]
        _safe_save_json(QUERY_HISTORY_FILE, remaining)

circulation_service = LibraryCirculationService()
