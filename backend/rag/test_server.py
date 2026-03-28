# backend/rag/test_server.py
# Run this to test your endpoints in the browser BEFORE connecting to Person 1
# Command: python -m backend.rag.test_server

import uvicorn
from fastapi import FastAPI
from .rag_router import router

app = FastAPI(title="RAG Engine Test Server")
app.include_router(router)

if __name__ == "__main__":
    print("\nStarting test server...")
    print("Open these URLs in your browser:")
    print("  http://localhost:8001/docs          ← Interactive API docs")
    print("  http://localhost:8001/rag/health    ← Health check")
    print("\nPress Ctrl+C to stop\n")
    uvicorn.run(app, host="0.0.0.0", port=8001)