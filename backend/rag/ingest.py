# backend/rag/ingest.py
"""
WHAT THIS FILE DOES:
- Opens the SWM 2026 gazette PDF
- Extracts text from every page
- Splits text into overlapping chunks (~500 words each)
- Returns a list of chunks for FAISS to embed

"""

import pdfplumber
import os


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """
    Opens the PDF and extracts text page by page.
    
    Returns:
        List of dicts: [{"page": 1, "text": "...", "char_count": 450}, ...]
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(
            f"PDF not found at: {pdf_path}\n"
        )    

    chunks = []

    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        print(f"PDF loaded: {total_pages} pages found")

        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()

            # Some pages might be images (scanned) — skip if no text
            if not text or len(text.strip()) < 20:
                print(f"  Page {page_num}: skipped (no readable text)")
                continue

            page_chunks = split_into_chunks(text, page_num)
            chunks.extend(page_chunks)

            if page_num % 10 == 0:
                print(f"  Processed page {page_num}/{total_pages}...")

    print(f"\nDone! Total chunks created: {len(chunks)}")
    return chunks


def split_into_chunks(
    text: str,
    page_num: int,
    chunk_size: int = 200,
    overlap: int = 100
) -> list[dict]:
    """
    Splits a page's text into overlapping chunks.
    
    Why overlap? So that if a law sentence spans two chunks,
    it still appears fully in at least one of them.
    
    Args:
        text: The full text of one page
        page_num: Which page this came from (for reference)
        chunk_size: ~words per chunk
        overlap: how many words to repeat between chunks
    
    Returns:
        List of chunk dicts
    """
    chunks = []
    words = text.split()

    if len(words) < 10:
        return []  # Too short to be useful

    i = 0
    chunk_index = 0

    while i < len(words):
        chunk_words = words[i : i + chunk_size]
        chunk_text = " ".join(chunk_words)

        # Only keep chunks with real content
        if len(chunk_text.strip()) > 50:
            chunks.append({
                "page": page_num,
                "chunk_index": chunk_index,
                "text": chunk_text,
                "char_count": len(chunk_text),
                "word_count": len(chunk_words),
            })
            chunk_index += 1

        i += chunk_size - overlap 

    return chunks


if __name__ == "__main__":
    PDF_PATH = "data/swm.pdf"

    print("=" * 50)
    print("TESTING PDF INGESTION")
    print("=" * 50)

    chunks = extract_text_from_pdf(PDF_PATH)

    print(f"\nTotal chunks: {len(chunks)}")
    print(f"Average chunk size: {sum(c['char_count'] for c in chunks) // len(chunks)} chars")

    print("\nSAMPLE: First chunk")
    print(f"Page: {chunks[0]['page']}")
    print(f"Text preview: {chunks[0]['text'][:300]}")

    print("\nSAMPLE: Middle chunk ")
    mid = len(chunks) // 2
    print(f"Page: {chunks[mid]['page']}")
    print(f"Text preview: {chunks[mid]['text'][:300]}")

    print("\n✓ ingest.py is working correctly!")