from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class PhysicalLocation(BaseModel):
    floor: int
    floor_name: str
    wing: str
    aisle: str
    rack: str
    shelf: str
    zone_color: str = "#06b6d4"
    map_coords: Dict[str, int] = Field(default_factory=lambda: {"x": 100, "y": 100})

class CirculationInfo(BaseModel):
    total_copies: int = 1
    available_copies: int = 1
    loan_period_days: int = 14
    status: str = "Available"
    borrowed_by: List[Dict[str, Any]] = Field(default_factory=list)

class Book(BaseModel):
    id: str
    title: str
    author: str
    year: int
    edition: Optional[str] = "1st Edition"
    isbn: str
    call_number: str
    category: str
    tags: List[str] = Field(default_factory=list)
    summary: str
    table_of_contents: List[str] = Field(default_factory=list)
    key_concepts: List[str] = Field(default_factory=list)
    physical_location: PhysicalLocation
    circulation: CirculationInfo
    citations: Dict[str, str] = Field(default_factory=dict)
    sample_chunks: List[str] = Field(default_factory=list)

class AgentTraceStep(BaseModel):
    step_number: int
    thought: str
    tool: str
    tool_input: Dict[str, Any]
    tool_output: Any
    latency_ms: float = 0.0

class AgentQueryRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = "default"
    history: List[Dict[str, str]] = Field(default_factory=list)
    api_key: Optional[str] = None
    agent_mode: Optional[str] = "concierge" # "concierge", "academic", "locator", "study_tutor"

class AgentResponse(BaseModel):
    answer: str
    thought_process: str
    steps: List[AgentTraceStep]
    matched_books: List[Book] = Field(default_factory=list)
    shelf_highlight: Optional[Dict[str, Any]] = None
    citations: Optional[Dict[str, str]] = None
    suggested_questions: List[str] = Field(default_factory=list)
    model_used: str = "Gemini-2.5-Flash (or Autonomous Fallback Engine)"
    execution_time_ms: float = 0.0

class CitationRequest(BaseModel):
    book_id: str
    format: str = "apa" # apa, mla, ieee, bibtex, all

class StudyRequest(BaseModel):
    book_id: str
    mode: str = "summary" # "summary", "concepts", "flashcards", "chat"
    query: Optional[str] = ""
    api_key: Optional[str] = None

class BorrowRequest(BaseModel):
    book_id: str
    user_id: str
    user_name: str
    user_role: str = "undergraduate"

class RoomBookingRequest(BaseModel):
    room_id: str
    user_id: str
    user_name: str
    date: str
    time_slot: str
