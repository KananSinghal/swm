# backend/main.py
"""
FASTAPI SERVER — The entry point Disha's frontend talks to.

ENDPOINTS:
  GET  /health              → Quick health check
  POST /audit               → Returns full audit as JSON (non-streaming)
  POST /audit/stream        → SSE: streams each agent as it runs (the "War Room")
  GET  /docs                → Auto-generated API docs (use during development)

HOW TO RUN:
  From project root:
    uvicorn backend.main:app --reload --port 8000

  Frontend connects to:
    http://localhost:8000

ENVIRONMENT:
  Create a .env file in project root:
    ANTHROPIC_API_KEY=sk-ant-...
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .schemas import SocietyInput, AuditResponse
from .agents import (
    run_compliance_agent,
    run_facility_agent,
    run_vendor_agent,
    run_communication_agent,
    run_crisis_synthesis,
)
from .rag.rag_router import router as rag_router
from .rag.retriever import _load_index

load_dotenv()


# ── Preload FAISS index on startup so first request is fast ────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 KaizenWaste backend starting...")
    try:
        _load_index()
        print("✅ FAISS index loaded")
    except FileNotFoundError:
        print("⚠️  FAISS index not found — RAG will fail. Run retriever.py first.")
    yield
    print("👋 Shutting down")


app = FastAPI(
    title="KaizenWaste API",
    description="Multi-agent AI system for SWM 2026 compliance",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow frontend (localhost:3000 or any origin during dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Kanan's RAG router at /rag/...
app.include_router(rag_router)


# ═══════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "KaizenWaste API",
        "anthropic_key_set": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


# ═══════════════════════════════════════════════════════════════════
# FULL AUDIT — non-streaming (useful for testing / Kaushiki's PDF)
# ═══════════════════════════════════════════════════════════════════

@app.post("/audit", response_model=AuditResponse)
async def run_audit(data: SocietyInput):
    """
    Runs all 4 agents sequentially and returns the complete result as JSON.
    Use this for: automated testing, generating the PDF compliance report.
    NOT used for the streaming War Room demo.
    """
    try:
        compliance = run_compliance_agent(data)
        facility = run_facility_agent(data, fine_risk=compliance.total_fine_risk_inr)
        vendor = run_vendor_agent(data)
        communication = run_communication_agent(data, fine_risk=compliance.total_fine_risk_inr)
        synthesis = run_crisis_synthesis(data, compliance, facility, vendor)

        return AuditResponse(
            society_name=data.society_name,
            compliance=compliance,
            facility=facility,
            vendor=vendor,
            communication=communication,
            crisis_synthesis=synthesis,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# STREAMING AUDIT — SSE (the "War Room" with live streaming panels)
# ═══════════════════════════════════════════════════════════════════

def _sse(event_type: str, agent: str, data: dict | str) -> str:
    """
    Format a Server-Sent Event.
    Frontend receives: event: <type>\ndata: <json>\n\n
    """
    payload = {
        "agent": agent,
        "type": event_type,
        "content": data if isinstance(data, str) else json.dumps(data),
    }
    return f"data: {json.dumps(payload)}\n\n"


async def _audit_stream(data: SocietyInput):
    """
    Generator that runs each agent and yields SSE events.
    Disha's frontend listens to this with EventSource.

    SSE event types:
      "thinking"  — agent has started, show spinner
      "result"    — agent finished, show the data
      "done"      — all agents done, show synthesis
      "error"     — something went wrong
    """

    # ── Agent 1: Compliance ─────────────────────────────────────────
    yield _sse("thinking", "Compliance Agent",
               "Querying SWM 2026 law database and analysing waste data...")
    await asyncio.sleep(0.1)  # let the frontend render the thinking state

    try:
        compliance = await asyncio.to_thread(run_compliance_agent, data)
        yield _sse("result", "Compliance Agent", compliance.model_dump())
    except Exception as e:
        yield _sse("error", "Compliance Agent", f"Agent failed: {str(e)}")
        return

    await asyncio.sleep(0.3)

    # ── Agent 2: Facility ───────────────────────────────────────────
    yield _sse("thinking", "Facility Agent",
               f"Analysing composter sensors — temp {data.composter_temp_celsius}°C, pH {data.composter_ph}...")
    await asyncio.sleep(0.1)

    try:
        facility = await asyncio.to_thread(
            run_facility_agent, data, compliance.total_fine_risk_inr
        )
        yield _sse("result", "Facility Agent", facility.model_dump())
    except Exception as e:
        yield _sse("error", "Facility Agent", f"Agent failed: {str(e)}")
        return

    await asyncio.sleep(0.3)

    # ── Agent 3: Vendor ─────────────────────────────────────────────
    yield _sse("thinking", "Vendor Agent",
               f"Fetching vendor quotes for {data.area}. Comparing certified suppliers...")
    await asyncio.sleep(0.1)

    try:
        vendor = await asyncio.to_thread(run_vendor_agent, data)
        yield _sse("result", "Vendor Agent", vendor.model_dump())
    except Exception as e:
        yield _sse("error", "Vendor Agent", f"Agent failed: {str(e)}")
        return

    await asyncio.sleep(0.3)

    # ── Agent 4: Communication ──────────────────────────────────────
    yield _sse("thinking", "Communication Agent",
               f"Analysing block-level segregation data. Block B at {data.block_b_segregation_pct}% — drafting WhatsApp message...")
    await asyncio.sleep(0.1)

    try:
        communication = await asyncio.to_thread(
            run_communication_agent, data, compliance.total_fine_risk_inr
        )
        yield _sse("result", "Communication Agent", communication.model_dump())
    except Exception as e:
        yield _sse("error", "Communication Agent", f"Agent failed: {str(e)}")
        return

    await asyncio.sleep(0.3)

    # ── Crisis Synthesis ────────────────────────────────────────────
    yield _sse("thinking", "Compliance Agent",
               "All agents complete. Running cost-benefit analysis across options...")
    await asyncio.sleep(0.1)

    try:
        synthesis = await asyncio.to_thread(
            run_crisis_synthesis, data, compliance, facility, vendor
        )
        yield _sse("done", "Compliance Agent", {
            "crisis_synthesis": synthesis.model_dump(),
            "full_audit": AuditResponse(
                society_name=data.society_name,
                compliance=compliance,
                facility=facility,
                vendor=vendor,
                communication=communication,
                crisis_synthesis=synthesis,
            ).model_dump()
        })
    except Exception as e:
        yield _sse("error", "Compliance Agent", f"Synthesis failed: {str(e)}")


@app.post("/audit/stream")
async def stream_audit(data: SocietyInput):
    """
    SSE endpoint for the War Room.

    HOW DISHA CONNECTS (frontend):

      const source = new EventSource('/audit/stream', {
          // Note: EventSource doesn't support POST body natively.
          // Use fetchEventSource from @microsoft/fetch-event-source instead:
      });

    RECOMMENDED FRONTEND LIBRARY:
      npm install @microsoft/fetch-event-source

    EXAMPLE FETCH (in React):
      import { fetchEventSource } from '@microsoft/fetch-event-source';

      await fetchEventSource('http://localhost:8000/audit/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(societyData),
        onmessage(event) {
          const msg = JSON.parse(event.data);
          // msg.agent  → which panel to update
          // msg.type   → "thinking" | "result" | "done" | "error"
          // msg.content → string (thinking) or JSON string (result/done)
          dispatch(updatePanel(msg));
        }
      });
    """
    return StreamingResponse(
        _audit_stream(data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disables nginx buffering (important for SSE)
            "Connection": "keep-alive",
        },
    )


# ── Dev runner ─────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
