import re
from typing import List, Dict, Any, Optional

def estimate_tokens(text: str) -> int:
    """Token counting estimator: characters divided by 3.6."""
    return max(1, int(len(text) / 3.6))

def detect_headings_and_sections(pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detects headings and structures content with hierarchical heading_path.
    Pages data contains: {'page_num': int, 'text': str, 'blocks': list}
    """
    sections = []
    current_heading_path = ["General"]
    
    derivation_keywords = ("derivation", "worked example", "proof", "example", "problem")
    
    for page in pages_data:
        p_num = page["page_num"]
        lines = page["text"].split("\n")
        
        buffer = []
        for line in lines:
            trimmed = line.strip()
            if not trimmed:
                continue

            # Check if this line looks like a heading
            # Patterns like "Chapter 1", "3.2 Ohm's Law", or short all-caps lines
            is_heading = False
            heading_title = trimmed
            
            if re.match(r'^(Chapter\s+\d+|Unit\s+\d+|\d+\.\d+|\b[A-Z\s]{4,30}\b)', trimmed):
                if len(trimmed) < 60:
                    is_heading = True

            if is_heading:
                # Flush existing buffer
                if buffer:
                    content_str = "\n".join(buffer)
                    sections.append({
                        "heading_path": list(current_heading_path),
                        "content": content_str,
                        "page_start": p_num,
                        "page_end": p_num,
                        "is_derivation": any(k in content_str.lower() for k in derivation_keywords)
                    })
                    buffer = []
                
                # Update heading path
                if re.match(r'^(Chapter|Unit)', trimmed, re.I):
                    current_heading_path = [trimmed]
                else:
                    if len(current_heading_path) > 1:
                        current_heading_path = [current_heading_path[0], trimmed]
                    else:
                        current_heading_path.append(trimmed)
            else:
                buffer.append(trimmed)

        if buffer:
            content_str = "\n".join(buffer)
            sections.append({
                "heading_path": list(current_heading_path),
                "content": content_str,
                "page_start": p_num,
                "page_end": p_num,
                "is_derivation": any(k in content_str.lower() for k in derivation_keywords)
            })

    return sections

def chunk_sections(sections: List[Dict[str, Any]], target_tokens: int = 700, max_tokens: int = 1000, overlap_tokens: int = 100) -> List[Dict[str, Any]]:
    """
    Chunks sections to target 700 tokens (hard max 1000) with 100 token overlap.
    Worked examples or derivations under 1200 tokens are kept whole.
    """
    chunks = []
    chunk_index = 0

    for sec in sections:
        content = sec["content"]
        tokens = estimate_tokens(content)

        # Invariant: Derivations/worked examples under 1200 tokens are kept whole
        if sec.get("is_derivation", False) and tokens <= 1200:
            chunks.append({
                "chunk_index": chunk_index,
                "page_start": sec["page_start"],
                "page_end": sec["page_end"],
                "heading_path": sec["heading_path"],
                "content": content,
                "token_count": tokens,
                "has_math": ("$" in content or "\\ce{" in content),
                "embedding_text": f"{' > '.join(sec['heading_path'])}\n{content}"
            })
            chunk_index += 1
            continue

        # Split on paragraph boundaries
        paragraphs = content.split("\n\n")
        cur_para_buf = []
        cur_tokens = 0
        p_start = sec["page_start"]
        p_end = sec["page_end"]

        for p in paragraphs:
            p_tok = estimate_tokens(p)
            if cur_tokens + p_tok > target_tokens and cur_para_buf:
                chunk_str = "\n\n".join(cur_para_buf)
                chunks.append({
                    "chunk_index": chunk_index,
                    "page_start": p_start,
                    "page_end": p_end,
                    "heading_path": sec["heading_path"],
                    "content": chunk_str,
                    "token_count": cur_tokens,
                    "has_math": ("$" in chunk_str or "\\ce{" in chunk_str),
                    "embedding_text": f"{' > '.join(sec['heading_path'])}\n{chunk_str}"
                })
                chunk_index += 1

                # Keep overlap paragraphs
                overlap_buf = []
                overlap_tok = 0
                for op in reversed(cur_para_buf):
                    ot = estimate_tokens(op)
                    if overlap_tok + ot <= overlap_tokens:
                        overlap_buf.insert(0, op)
                        overlap_tok += ot
                    else:
                        break
                cur_para_buf = overlap_buf
                cur_tokens = overlap_tok

            cur_para_buf.append(p)
            cur_tokens += p_tok

        if cur_para_buf:
            chunk_str = "\n\n".join(cur_para_buf)
            chunks.append({
                "chunk_index": chunk_index,
                "page_start": p_start,
                "page_end": p_end,
                "heading_path": sec["heading_path"],
                "content": chunk_str,
                "token_count": cur_tokens,
                "has_math": ("$" in chunk_str or "\\ce{" in chunk_str),
                "embedding_text": f"{' > '.join(sec['heading_path'])}\n{chunk_str}"
            })
            chunk_index += 1

    return chunks
