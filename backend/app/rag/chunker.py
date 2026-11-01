import re
from typing import List, Dict, Any, Optional
import pypdf
import io

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts text from PDF bytes using pypdf with page markers."""
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    text_parts = []
    for idx, page in enumerate(reader.pages, 1):
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_parts.append(f"[Page {idx}]\n{page_text.strip()}")
    return "\n\n".join(text_parts)

def extract_pdf_pages(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extracts text per page from PDF bytes using pypdf."""
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    pages = []
    for idx, page in enumerate(reader.pages, 1):
        text = page.extract_text() or ""
        pages.append({
            "page_num": idx,
            "text": text.strip()
        })
    return pages

def chunk_text(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 80,
    page_num: Optional[int] = None,
    total_pages_override: Optional[int] = None,
    is_exact_page: bool = False
) -> List[Dict[str, Any]]:
    """
    Splits text into overlapping semantic passages with precise positional tracking:
    - Character start & end offsets
    - Percentage into the text
    - Exact or estimated book page number & total pages
    - Relative section (Beginning, Middle, Conclusion)
    """
    clean_text = re.sub(r'\s+', ' ', text).strip()
    if not clean_text:
        return []
        
    chunks = []
    start = 0
    total_len = len(clean_text)
    total_pages = total_pages_override or max(1, (total_len // 1500) + 1)
    
    while start < total_len:
        end = min(start + chunk_size, total_len)
        
        # Try to find a sentence boundary near the end
        if end < total_len:
            last_period = clean_text.rfind('. ', start + chunk_size // 2, end)
            if last_period != -1 and (last_period - start) > chunk_size // 3:
                end = last_period + 1
                
        chunk_content = clean_text[start:end].strip()
        if chunk_content:
            pct = round((start / total_len) * 100, 1) if total_len > 0 else 0.0
            approx_page = max(1, (start // 1500) + 1)
            
            if pct <= 25.0:
                rel_sec = "Beginning Chapters (0-25%)"
            elif pct <= 75.0:
                rel_sec = "Core / Middle Chapters (25-75%)"
            else:
                rel_sec = "Concluding Chapters (75-100%)"
                
            actual_page = page_num if is_exact_page and page_num is not None else approx_page
            page_label = f"Page {actual_page} of {total_pages}" if is_exact_page else f"Estimated Page ~{approx_page} of {total_pages}"
            
            chunks.append({
                "text": chunk_content,
                "start_char": start,
                "end_char": end,
                "total_chars": total_len,
                "percentage": pct,
                "approx_page": approx_page,
                "page_num": actual_page,
                "is_exact_page": is_exact_page,
                "total_pages": total_pages,
                "page_label": page_label,
                "relative_section": rel_sec,
                "char_span": f"{start:,} - {end:,} of {total_len:,} chars"
            })
            
        if end >= total_len:
            break
            
        start = max(start + 1, end - overlap)
        
    return chunks

def chunk_pdf_document(file_bytes: bytes, chunk_size: int = 500, overlap: int = 80) -> List[Dict[str, Any]]:
    """
    Chunks a PDF document page by page to guarantee that each chunk maintains
    exact physical PDF page provenance.
    """
    pages = extract_pdf_pages(file_bytes)
    total_pages = len(pages)
    if total_pages == 0:
        return []
    
    all_chunks = []
    global_char_offset = 0
    full_text_len = sum(len(p["text"]) for p in pages)
    
    for page_info in pages:
        p_num = page_info["page_num"]
        p_text = page_info["text"]
        if not p_text.strip():
            continue
            
        p_chunks = chunk_text(
            p_text, 
            chunk_size=chunk_size, 
            overlap=overlap, 
            page_num=p_num, 
            total_pages_override=total_pages, 
            is_exact_page=True
        )
        
        for ch in p_chunks:
            # Adjust start_char and end_char to be relative to the entire document
            ch["start_char"] += global_char_offset
            ch["end_char"] += global_char_offset
            ch["total_chars"] = max(full_text_len, ch["end_char"])
            if full_text_len > 0:
                ch["percentage"] = round((ch["start_char"] / full_text_len) * 100, 1)
            ch["char_span"] = f"{ch['start_char']:,} - {ch['end_char']:,} of {full_text_len:,} chars"
            all_chunks.append(ch)
            
        global_char_offset += len(p_text) + 2  # newline buffer
        
    return all_chunks
