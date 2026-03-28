# backend/rag/retriever.py
"""
WHAT THIS FILE DOES:
- Takes all the text chunks from ingest.py
- Converts them to vectors (numbers) using a sentence embedding model
- Stores them in a FAISS index (a fast similarity search database)
- Lets you search: "what are penalties for dumping waste?" 
  → returns the 5 most relevant law excerpts

RUN THIS FILE DIRECTLY TO BUILD THE INDEX + TEST:
  python -m backend.rag.retriever
"""

import faiss
import numpy as np
import pickle
import os
from sentence_transformers import SentenceTransformer

from .ingest import extract_text_from_pdf



# This small model is fast and works well for legal text
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Where to save the built index (commit this file to git!)
INDEX_PATH = "data/faiss_index.bin"
CHUNKS_PATH = "data/chunks_store.pkl"

PDF_PATH = "data/swm.pdf"



# These are module-level variables so we only load them once
_model = None
_index = None
_chunks = None


def _get_model() -> SentenceTransformer:
    """Load the embedding model (only loads once, then reuses)."""
    global _model
    if _model is None:
        print(f"Loading embedding model: {EMBEDDING_MODEL}")
        print("(First time takes 1-2 min to download, then it's cached)")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print("Model loaded ✓")
    return _model


def build_index(pdf_path: str = PDF_PATH) -> None:
    """
    STEP 1: Run this ONCE to create the FAISS index.
    
    What it does:
    1. Parses the PDF into chunks
    2. Converts each chunk to a vector (384 numbers)
    3. Stores all vectors in FAISS for fast search
    4. Saves index + chunks to disk
    
    After running this, you never need to run it again
    unless the PDF changes.
    """
    print("BUILDING FAISS INDEX")
   

    # Step 1: Get chunks from PDF
    chunks = extract_text_from_pdf(pdf_path)
    texts = [chunk["text"] for chunk in chunks]
    print(f"\nEmbedding {len(texts)} chunks into vectors...")

    # Step 2: Convert text → vectors
    model = _get_model()
    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        batch_size=32,        # Process 32 chunks at a time
        normalize_embeddings=True  # Required for cosine similarity
    )
    embeddings = np.array(embeddings, dtype="float32")
    print(f"Embeddings shape: {embeddings.shape}")  # Should be (num_chunks, 384)

    # Step 3: Build FAISS index
    dimension = embeddings.shape[1]  # 384 for this model
    # IndexFlatIP = Inner Product search (= cosine similarity when normalized)
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    print(f"FAISS index built with {index.ntotal} vectors ✓")

    # Step 4: Save everything to disk
    os.makedirs("data", exist_ok=True)
    faiss.write_index(index, INDEX_PATH)
    with open(CHUNKS_PATH, "wb") as f:
        pickle.dump(chunks, f)

    print(f"\nSaved index to: {INDEX_PATH}")
    print(f"Saved chunks to: {CHUNKS_PATH}")
    print("\n✓ Index built successfully! Commit data/ folder to git.")


def _load_index():
    """Load the FAISS index from disk (only once per session)."""
    global _index, _chunks

    if _index is not None:
        return _index, _chunks  # Already loaded

    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(
            f"FAISS index not found at {INDEX_PATH}\n"
            "Run build_index() first:\n"
            "  python -m backend.rag.retriever"
        )

    print("Loading FAISS index from disk...")
    _index = faiss.read_index(INDEX_PATH)
    with open(CHUNKS_PATH, "rb") as f:
        _chunks = pickle.load(f)
    print(f"Index loaded: {_index.ntotal} vectors, {len(_chunks)} chunks ✓")

    return _index, _chunks


def query_law(question: str, top_k: int = 5) -> list[dict]:
    """
    
    THE MAIN FUNCTION — Person 1 calls this for Agent 1 (Compliance).
    
    
    Give it a question, get back the most relevant law excerpts.
    
    Args:
        question: Any compliance question, e.g.
                  "What are the penalties for illegal waste dumping?"
                  "What are rules for biomedical waste segregation?"
        top_k:    How many results to return (default 5)
    
    Returns:
        List of dicts, sorted by relevance (best first):
        [
            {
                "page": 23,
                "text": "Section 15: Any person found dumping...",
                "relevance_score": 0.87,
                "chunk_index": 4
            },
            ...
        ]
    """
    index, chunks = _load_index()
    model = _get_model()

    # Convert the question to a vector
    query_vector = model.encode(
        [question],
        normalize_embeddings=True
    )
    query_vector = np.array(query_vector, dtype="float32")

    # Search the index
    scores, indices = index.search(query_vector, top_k)

    # Build results
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:
            continue  # FAISS returns -1 if fewer results than top_k
        if score < 0.25:
            continue  # Skip very low relevance results

        results.append({
            "page": chunks[idx]["page"],
            "text": chunks[idx]["text"],
            "relevance_score": round(float(score), 4),
            "chunk_index": chunks[idx]["chunk_index"],
        })

    return results


if __name__ == "__main__":
    import sys

    # ── STEP 1: Build the index ──
    if not os.path.exists(INDEX_PATH):
        print("Index not found. Building now...")
        build_index()
    else:
        print(f"Index already exists at {INDEX_PATH}")
        print("Delete it and re-run if you want to rebuild.\n")

    # ── STEP 2: Test some queries ──
    TEST_QUESTIONS = [
        "What are the penalties for illegal waste dumping?",
        "What are the rules for biomedical waste segregation?",
        "What is the responsibility of the municipality for solid waste collection?",
        "What are the rules for plastic waste management?",
    ]

    print("\n" + "=" * 50)
    print("TESTING QUERIES")
    print("=" * 50)

    for question in TEST_QUESTIONS:
        print(f"\nQ: {question}")
        print("-" * 40)
        results = query_law(question, top_k=3)

        if not results:
            print("  No results found (check your PDF has text content)")
        else:
            for i, r in enumerate(results, 1):
                print(f"  Result {i} (page {r['page']}, score {r['relevance_score']}):")
                print(f"  {r['text'][:200]}...")

    print("\n✓ retriever.py is working correctly!")