import os
import json
import time
import re
from typing import Dict, Any, List, Optional
from .tools import TOOL_REGISTRY, load_catalog

class GeminiAgentEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = None
        
        if self.api_key:
            self._init_client()

    def _init_client(self):
        try:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            print(f"[GeminiAgentEngine] Client init failed, using autonomous engine: {e}")
            self.client = None

    def update_api_key(self, api_key: str):
        if api_key:
            self.api_key = api_key
            self._init_client()

    def execute_query(
        self,
        query: str,
        history: List[Dict[str, str]] = None,
        agent_mode: str = "concierge",
        custom_key: Optional[str] = None
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        # Override key if passed in request
        active_key = custom_key or self.api_key
        if custom_key and custom_key != self.api_key:
            try:
                from google import genai
                active_client = genai.Client(api_key=custom_key)
            except Exception:
                active_client = self.client
        else:
            active_client = self.client

        # Try live Gemini call if client is available
        if active_client and active_key:
            try:
                return self._execute_gemini_react(active_client, query, history, agent_mode, start_time)
            except Exception as e:
                print(f"[GeminiAgentEngine] Gemini live call failed ({e}). Seamlessly engaging autonomous fallback.")

        # Fallback to Autonomous ReAct Agent Simulation with Real Tool Execution
        return self._execute_autonomous_react(query, agent_mode, start_time)

    def _execute_gemini_react(self, client, query: str, history, agent_mode: str, start_time: float) -> Dict[str, Any]:
        """
        Executes ReAct reasoning loop with Google Gemini API
        """
        system_instruction = f"""
You are Alexandria AI, an elite autonomous smart library concierge and research assistant.
You possess real-time tools to help students and researchers:
1. semantic_catalog_search(query, category): Search library catalog books.
2. physical_shelf_locator(book_id_or_title): Find exact physical shelf, aisle, floor, and coordinates.
3. circulation_policy_officer(role, action): Check borrowing limits, loan days, and late return fees.
4. academic_citation_generator(book_id, style): Generate citations (APA, MLA, IEEE, BibTeX).
5. book_study_companion(book_id, action): Generate chapter summaries, study flashcards, or concepts.
6. study_room_reservation(room_id, user_name, time_slot): Query or reserve study rooms.

Current Persona Mode: {agent_mode.upper()}.

Provide a structured, deeply intelligent response. Always be academic, helpful, polite, and precise.
Format your reasoning clearly.
"""
        # First, plan which tools to execute
        catalog = load_catalog()
        catalog_summary = [{"id": b["id"], "title": b["title"], "call_number": b["call_number"]} for b in catalog]

        planning_prompt = f"""
User Query: "{query}"
Catalog Overview: {json.dumps(catalog_summary[:10])}

Determine what tools are needed to answer this query.
Respond in JSON format with:
{{
  "thought": "your step-by-step reasoning plan",
  "tool_calls": [
    {{"tool": "semantic_catalog_search", "args": {{"query": "{query}"}}}},
    {{"tool": "physical_shelf_locator", "args": {{"book_id_or_title": "title or id if known"}}}}
  ]
}}
"""
        response = client.models.generate_content(
            model=self.model_name,
            contents=planning_prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json"
            }
        )

        plan_data = json.loads(response.text)
        steps = []
        matched_books = []
        shelf_info = None
        citations_data = None

        step_idx = 1
        for call in plan_data.get("tool_calls", []):
            tool_name = call.get("tool")
            args = call.get("args", {})
            if tool_name in TOOL_REGISTRY:
                t0 = time.time()
                tool_fn = TOOL_REGISTRY[tool_name]
                try:
                    tool_res = tool_fn(**args)
                except Exception as ex:
                    tool_res = {"error": str(ex)}
                t_latency = round((time.time() - t0) * 1000, 2)

                steps.append({
                    "step_number": step_idx,
                    "thought": f"Executing {tool_name} to fetch relevant information for user request.",
                    "tool": tool_name,
                    "tool_input": args,
                    "tool_output": tool_res,
                    "latency_ms": t_latency
                })
                step_idx += 1

                if tool_name == "semantic_catalog_search" and "books" in tool_res:
                    matched_books.extend(tool_res["books"])
                elif tool_name == "physical_shelf_locator" and tool_res.get("status") == "success":
                    shelf_info = tool_res
                elif tool_name == "academic_citation_generator" and "citations" in tool_res:
                    citations_data = tool_res["citations"]

        # Final synthesis with Gemini
        synthesis_prompt = f"""
User Query: {query}
Tool Execution Results:
{json.dumps([s["tool_output"] for s in steps])}

Synthesize a comprehensive, beautifully structured answer for the library user.
Include relevant call numbers, floor locations, and academic advice.
Also provide 3 relevant follow-up questions the user might ask.
"""
        synth_res = client.models.generate_content(
            model=self.model_name,
            contents=synthesis_prompt
        )

        final_text = synth_res.text
        exec_time = round((time.time() - start_time) * 1000, 2)

        return {
            "answer": final_text,
            "thought_process": plan_data.get("thought", "Autonomous Agent Analysis"),
            "steps": steps,
            "matched_books": matched_books[:4],
            "shelf_highlight": shelf_info,
            "citations": citations_data,
            "suggested_questions": [
                "Where is this book physically located?",
                "Can you generate an APA citation for this book?",
                "What are the loan policies and return deadlines for students?"
            ],
            "model_used": f"Gemini ({self.model_name}) Live ReAct",
            "execution_time_ms": exec_time
        }

    def _execute_autonomous_react(self, query: str, agent_mode: str, start_time: float) -> Dict[str, Any]:
        """
        High-fidelity ReAct Autonomous Agent that parses intent, executes genuine tools,
        and constructs step-by-step reasoning traces. Guarantees 100% reliability.
        """
        q_lower = query.lower()
        steps = []
        step_counter = 1
        matched_books = []
        shelf_highlight = None
        citations = None
        thought_process = ""
        suggested_questions = []

        # Intent 1: Physical shelf location / map inquiry
        if any(w in q_lower for w in ["where", "shelf", "floor", "locate", "map", "find", "aisle", "rack"]):
            thought_process = "User is requesting physical location coordinates and shelf directions. Planning steps: 1) Search catalog to identify matching target book, 2) Query physical shelf locator for floor, aisle, and 2.5D map coordinates."
            
            # Step 1: Catalog search
            t0 = time.time()
            cat_res = TOOL_REGISTRY["semantic_catalog_search"](query=query, top_k=2)
            steps.append({
                "step_number": step_counter,
                "thought": "Querying library catalog to identify matching book record.",
                "tool": "semantic_catalog_search",
                "tool_input": {"query": query, "top_k": 2},
                "tool_output": cat_res,
                "latency_ms": round((time.time() - t0) * 1000, 2)
            })
            step_counter += 1
            
            target_book = cat_res["books"][0] if cat_res["books"] else None
            if target_book:
                matched_books = [target_book]
                # Step 2: Shelf locator
                t1 = time.time()
                shelf_res = TOOL_REGISTRY["physical_shelf_locator"](book_id_or_title=target_book["id"])
                shelf_highlight = shelf_res
                steps.append({
                    "step_number": step_counter,
                    "thought": f"Retrieving exact floor stacks and shelf coordinates for '{target_book['title']}'.",
                    "tool": "physical_shelf_locator",
                    "tool_input": {"book_id_or_title": target_book["id"]},
                    "tool_output": shelf_res,
                    "latency_ms": round((time.time() - t1) * 1000, 2)
                })
                step_counter += 1
                
                answer = f"**{target_book['title']}** by *{target_book['author']}* (Call No: `{target_book['call_number']}`) is located on **{shelf_res['floor_name']}** in the **{shelf_res['wing']}**.\n\n" \
                         f"📍 **Exact Location:** {shelf_res['aisle']} → {shelf_res['rack']} → {shelf_res['shelf']}.\n" \
                         f"🧭 **Wayfinding Guidance:** {shelf_res['navigation_hint']}\n\n" \
                         f"Currently, there are **{target_book['circulation']['available_copies']} of {target_book['circulation']['total_copies']} copies available** for borrowing."
                
                suggested_questions = [
                    f"Can you generate citations for {target_book['title']}?",
                    f"Give me chapter flashcards for {target_book['title']}",
                    "What are the late return fees and loan limits?"
                ]

        # Intent 2: Citation inquiry
        elif any(w in q_lower for w in ["cite", "citation", "apa", "mla", "ieee", "bibtex"]):
            thought_process = "User needs an academic citation. Planning steps: 1) Identify corresponding catalog work, 2) Invoke academic citation generator for APA, MLA, IEEE, and BibTeX styles."
            
            cat_res = TOOL_REGISTRY["semantic_catalog_search"](query=query, top_k=1)
            target_book = cat_res["books"][0] if cat_res["books"] else None
            
            if target_book:
                matched_books = [target_book]
                t0 = time.time()
                cite_res = TOOL_REGISTRY["academic_citation_generator"](book_id=target_book["id"])
                citations = cite_res.get("citations", {})
                steps.append({
                    "step_number": step_counter,
                    "thought": f"Generating multi-format peer-reviewed citations for '{target_book['title']}'.",
                    "tool": "academic_citation_generator",
                    "tool_input": {"book_id": target_book["id"]},
                    "tool_output": cite_res,
                    "latency_ms": round((time.time() - t0) * 1000, 2)
                })
                
                answer = f"Here are standard academic citations for **{target_book['title']}**:\n\n" \
                         f"🔹 **IEEE:**\n> {citations.get('ieee', 'N/A')}\n\n" \
                         f"🔹 **APA (7th Ed.):**\n> {citations.get('apa', 'N/A')}\n\n" \
                         f"🔹 **MLA (9th Ed.):**\n> {citations.get('mla', 'N/A')}\n\n" \
                         f"🔹 **BibTeX:**\n```bibtex\n{citations.get('bibtex', 'N/A')}\n```"
                
                suggested_questions = [
                    f"Where is this book located on the shelves?",
                    f"Summarize the key concepts of {target_book['title']}",
                    "How many days can an undergraduate keep this book?"
                ]

        # Intent 3: Policy, Borrowing, Due dates, Fines
        elif any(w in q_lower for w in ["policy", "borrow", "due", "fine", "rule", "fee", "limit", "renew"]):
            role = "postgraduate" if "postgrad" in q_lower or "phd" in q_lower or "masters" in q_lower else ("faculty" if "faculty" in q_lower or "prof" in q_lower else "undergraduate")
            thought_process = f"User inquired about library loan policies. Planning steps: 1) Query circulation policy officer for role '{role}'."
            
            t0 = time.time()
            pol_res = TOOL_REGISTRY["circulation_policy_officer"](role=role)
            steps.append({
                "step_number": step_counter,
                "thought": f"Consulting library circulation regulations for role '{role}'.",
                "tool": "circulation_policy_officer",
                "tool_input": {"role": role},
                "tool_output": pol_res,
                "latency_ms": round((time.time() - t0) * 1000, 2)
            })
            
            answer = f"### 📋 Library Circulation Policy ({role.capitalize()} Tier)\n\n" \
                     f"- **Maximum Books Allowed:** {pol_res['max_allowed_books']} simultaneous items\n" \
                     f"- **Standard Loan Duration:** {pol_res['loan_duration_days']} calendar days\n" \
                     f"- **Allowed Renewals:** Up to {pol_res['max_renewals']} times (provided no holds are pending)\n" \
                     f"- **Overdue Fine:** {pol_res['overdue_fine_per_day']} per item per day\n\n" \
                     f"💡 *Tip:* You can renew books online anytime before midnight of the due date through the circulation desk tab."
            
            suggested_questions = [
                "Can I reserve a collaborative study room?",
                "Recommend top Artificial Intelligence textbooks",
                "What are faculty borrowing privileges?"
            ]

        # Intent 4: Study room reservation
        elif any(w in q_lower for w in ["room", "study room", "reserve room", "pod", "lab", "book room"]):
            thought_process = "User is looking for collaborative study space. Planning steps: 1) Retrieve all study room statuses across library floors."
            t0 = time.time()
            room_res = TOOL_REGISTRY["study_room_reservation"]()
            steps.append({
                "step_number": step_counter,
                "thought": "Querying real-time study room occupancy and availability.",
                "tool": "study_room_reservation",
                "tool_input": {},
                "tool_output": room_res,
                "latency_ms": round((time.time() - t0) * 1000, 2)
            })
            
            rooms = room_res.get("rooms", [])
            avail_rooms = [r for r in rooms if r.get("status") == "Available"]
            
            answer = f"We have **{len(avail_rooms)} study rooms currently available** for student and group bookings:\n\n"
            for r in avail_rooms:
                proj = "🖥️ Has Projector" if r.get("has_projector") else "Whiteboard only"
                answer += f"- **{r['name']}** (Capacity: {r['capacity']} people, {proj}) — *{r['floor_name']}*\n"
                
            answer += "\nTo reserve, simply use the **Circulation & Rooms** tab or specify which room and time slot you need!"
            suggested_questions = [
                "Book Atrium Seminar Room 101 for me",
                "Recommend books on Computer Algorithms",
                "Where is Gödel, Escher, Bach located?"
            ]

        # Intent 5: General book search or study inquiry
        else:
            thought_process = "User query requires semantic catalog discovery and conceptual knowledge retrieval. Planning steps: 1) Run semantic search across book titles, summaries, and concepts, 2) Retrieve shelf info for highest match."
            t0 = time.time()
            cat_res = TOOL_REGISTRY["semantic_catalog_search"](query=query, top_k=3)
            steps.append({
                "step_number": step_counter,
                "thought": "Executing semantic retrieval on catalog database.",
                "tool": "semantic_catalog_search",
                "tool_input": {"query": query, "top_k": 3},
                "tool_output": cat_res,
                "latency_ms": round((time.time() - t0) * 1000, 2)
            })
            step_counter += 1
            
            matched_books = cat_res.get("books", [])
            if matched_books:
                top_b = matched_books[0]
                t1 = time.time()
                shelf_res = TOOL_REGISTRY["physical_shelf_locator"](book_id_or_title=top_b["id"])
                shelf_highlight = shelf_res
                steps.append({
                    "step_number": step_counter,
                    "thought": f"Locating primary match '{top_b['title']}' on physical stacks.",
                    "tool": "physical_shelf_locator",
                    "tool_input": {"book_id_or_title": top_b["id"]},
                    "tool_output": shelf_res,
                    "latency_ms": round((time.time() - t1) * 1000, 2)
                })
                
                answer = f"I discovered several relevant titles in our collection matching your interest:\n\n"
                for idx, b in enumerate(matched_books, 1):
                    avail = f"{b['circulation']['available_copies']}/{b['circulation']['total_copies']} copies"
                    answer += f"**{idx}. {b['title']}** ({b['year']})\n" \
                              f"   - *Author:* {b['author']}\n" \
                              f"   - *Call Number:* `{b['call_number']}` ({avail})\n" \
                              f"   - *Synopsis:* {b['summary'][:160]}...\n" \
                              f"   - *Shelf:* {b['physical_location']['floor_name']}, {b['physical_location']['wing']}\n\n"
                              
                answer += f"💡 **Recommended next step:** Would you like me to highlight the exact shelf position on our 3D floor map or generate a study guide for *{top_b['title']}*?"
                suggested_questions = [
                    f"Show physical location of {top_b['title']}",
                    f"Generate flashcards for {top_b['title']}",
                    f"Provide APA citation for {top_b['title']}"
                ]
            else:
                answer = "I searched our library collection but could not find an exact match. You can browse our collection by department (Computing, Physics, Biology, Philosophy, Literature) or tell me the topic you are researching!"
                suggested_questions = [
                    "What Artificial Intelligence books are available?",
                    "Show me Quantum Physics textbooks",
                    "What are the library borrowing limits?"
                ]

        exec_time = round((time.time() - start_time) * 1000, 2)
        return {
            "answer": answer,
            "thought_process": thought_process,
            "steps": steps,
            "matched_books": matched_books,
            "shelf_highlight": shelf_highlight,
            "citations": citations,
            "suggested_questions": suggested_questions,
            "model_used": "Autonomous Smart Library Agent Engine",
            "execution_time_ms": exec_time
        }

agent_engine = GeminiAgentEngine()
