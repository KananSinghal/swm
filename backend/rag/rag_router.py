# backend/rag/rag_router.py
"""
WHAT THIS FILE DOES:
- Wraps all your RAG functions as HTTP API endpoints
- Person 1 imports this router into their main FastAPI server
- Agents call these endpoints to get law excerpts and vendor quotes

Person 1 adds TWO LINES to their main.py:
    from backend.rag.rag_router import router as rag_router
    app.include_router(rag_router)

That's it — they don't touch anything else in your folder.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .retriever import query_law, _load_index
from .vendor_mock import get_vendor_quotes, get_vendor_by_id, get_all_vendors


# All your endpoints will be at /rag/...
router = APIRouter(prefix="/rag", tags=["RAG Engine"])

from typing import Optional

# ═══════════════════════════════════════════════════
# REQUEST & RESPONSE MODELS
# Share these with Person 1 so their agents know what
# to send and what to expect back.
# ═══════════════════════════════════════════════════

class LawQueryRequest(BaseModel):
    question: str = Field(
        ...,
        example="What are the penalties for illegal waste dumping?",
        description="The compliance question to search for in SWM 2026 gazette"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of law excerpts to return"
    )

class LawExcerpt(BaseModel):
    page: int
    text: str
    relevance_score: float
    chunk_index: int

class LawQueryResponse(BaseModel):
    question: str
    excerpts: list[LawExcerpt]
    total_found: int
    status: str = "success"


class VendorQueryRequest(BaseModel):
    waste_type: str = Field(
        default="bulk waste",
        example="bulk waste",
        description="Type: 'bulk waste', 'bio-waste', 'e-waste', 'recycling', 'construction debris'"
    )
    area: Optional[str] = Field(
        default=None,
        example="South Delhi",
        description="Area name to filter vendors by coverage"
    )
    quantity_kg: float = Field(
        default=1000.0,
        gt=0,
        description="Weight of waste in kg"
    )

class VendorQuote(BaseModel):
    vendor_id: str
    vendor_name: str
    contact_phone: str
    whatsapp_number: str
    email: str
    compliance_certified: bool
    swm_license: Optional[str]
    quoted_price_inr: float
    price_per_kg: float
    services_offered: list[str]
    areas_covered: list[str]
    quote_valid_until: str
    estimated_response_hours: int
    rating: float
    compliance_warning: bool

class VendorQueryResponse(BaseModel):
    quotes: list[VendorQuote]
    total_vendors_found: int
    recommended_vendor: str        # Cheapest certified vendor
    has_compliance_warning: bool   # True if any vendor is not certified
    status: str = "success"


# ═══════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════

@router.get("/health")
async def health_check():
    """
    Person 1 uses this to check if your module loaded correctly.
    Visit: http://localhost:8000/rag/health
    """
    try:
        _load_index()
        index_status = "loaded"
    except FileNotFoundError:
        index_status = "not built yet — run build_index()"

    return {
        "status": "ok",
        "module": "rag-engine",
        "faiss_index": index_status,
    }


@router.post("/query-law", response_model=LawQueryResponse)
async def query_law_endpoint(request: LawQueryRequest):
    """
    Agent 1 (Compliance Agent) calls this endpoint.
    
    Give it a question → get relevant SWM 2026 law excerpts back.
    
    Example request body:
    {
        "question": "What are the penalties for illegal waste dumping?",
        "top_k": 5
    }
    """
    try:
        excerpts = query_law(request.question, top_k=request.top_k)

        if not excerpts:
            return LawQueryResponse(
                question=request.question,
                excerpts=[],
                total_found=0,
                status="no results found"
            )

        return LawQueryResponse(
            question=request.question,
            excerpts=excerpts,
            total_found=len(excerpts),
            status="success"
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RAG query failed: {str(e)}"
        )


@router.post("/vendor-quotes", response_model=VendorQueryResponse)
async def vendor_quotes_endpoint(request: VendorQueryRequest):
    """
    Agent 3 (Vendor Negotiation Agent) calls this endpoint.
    
    Give it waste type + area + quantity → get ranked vendor quotes.
    
    Example request body:
    {
        "waste_type": "bulk waste",
        "area": "South Delhi",
        "quantity_kg": 1000
    }
    """
    try:
        quotes = get_vendor_quotes(
            waste_type=request.waste_type,
            area=request.area,
            quantity_kg=request.quantity_kg,
        )

        if not quotes:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"No vendors found for waste_type='{request.waste_type}' "
                    f"in area='{request.area}'"
                )
            )

        # Find cheapest certified vendor for recommendation
        certified_quotes = [q for q in quotes if q["compliance_certified"]]
        if certified_quotes:
            recommended = certified_quotes[0]["vendor_name"]
        else:
            recommended = quotes[0]["vendor_name"] + " (WARNING: not certified)"

        has_warning = any(q["compliance_warning"] for q in quotes)

        return VendorQueryResponse(
            quotes=quotes,
            total_vendors_found=len(quotes),
            recommended_vendor=recommended,
            has_compliance_warning=has_warning,
            status="success"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vendor/{vendor_id}")
async def get_single_vendor(vendor_id: str):
    """
    Look up a specific vendor by their ID (e.g. V001, V002).
    Useful when an agent wants full details on one vendor.
    """
    vendor = get_vendor_by_id(vendor_id)
    if not vendor:
        raise HTTPException(
            status_code=404,
            detail=f"Vendor '{vendor_id}' not found"
        )
    return vendor


@router.get("/vendors/all")
async def get_all_vendors_endpoint():
    """Return the full vendor list. Useful for Agent 3 overview."""
    return {"vendors": get_all_vendors(), "total": len(get_all_vendors())}