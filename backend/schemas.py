# backend/schemas.py
"""
PYDANTIC SCHEMAS — The contracts between all agents.
Every agent reads from and writes to these shapes.
If a field is wrong, Pydantic will catch it BEFORE it crashes the demo.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ─────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────

class ViolationSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class CompostStatus(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"

class AgentName(str, Enum):
    COMPLIANCE = "Compliance Agent"
    FACILITY = "Facility Agent"
    VENDOR = "Vendor Agent"
    COMMUNICATION = "Communication Agent"


# ─────────────────────────────────────────
# INPUT: What the frontend sends to kick off the audit
# ─────────────────────────────────────────

class SocietyInput(BaseModel):
    """POST /audit — The trigger payload from the frontend."""
    society_name: str = Field(default="Green Valley Apartments")
    total_units: int = Field(default=500)
    area: str = Field(default="South Delhi")

    # Waste data (kg/day)
    wet_waste_kg: float = Field(default=95.0)
    dry_waste_kg: float = Field(default=55.0)
    wet_waste_processed_onsite_kg: float = Field(default=62.0)

    # Composter sensor readings
    composter_temp_celsius: float = Field(default=28.0)
    composter_ph: float = Field(default=8.4)
    composter_moisture_pct: float = Field(default=44.0)

    # Resident data
    segregation_quality_pct: float = Field(default=63.0)
    block_b_segregation_pct: float = Field(default=48.0)


# ─────────────────────────────────────────
# AGENT 1 OUTPUT: Compliance Agent
# ─────────────────────────────────────────

class Violation(BaseModel):
    rule_reference: str
    description: str
    severity: ViolationSeverity
    fine_per_day_inr: float
    days_at_risk: int = 1
    total_fine_risk_inr: float

class ComplianceResult(BaseModel):
    compliance_score: int
    violations: list[Violation]
    total_fine_risk_inr: float
    law_excerpts_used: list[str]
    summary: str
    recommendation: str


# ─────────────────────────────────────────
# AGENT 2 OUTPUT: Facility Agent
# ─────────────────────────────────────────

class CorrectiveAction(BaseModel):
    action: str
    estimated_cost_inr: float
    time_to_effect_hours: int

class FacilityResult(BaseModel):
    composter_status: CompostStatus
    diagnosis: str
    corrective_actions: list[CorrectiveAction]
    total_repair_cost_inr: float
    estimated_recovery_hours: int
    shutdown_risk: bool
    summary: str


# ─────────────────────────────────────────
# AGENT 3 OUTPUT: Vendor Agent
# ─────────────────────────────────────────

class VendorOption(BaseModel):
    vendor_name: str
    price_per_kg: float
    total_quoted_inr: float
    compliance_certified: bool
    rating: float
    estimated_response_hours: int
    compliance_warning: bool

class VendorResult(BaseModel):
    vendors_evaluated: list[VendorOption]
    recommended_vendor: str
    recommended_price_per_kg: float
    baseline_price_per_kg: float
    revenue_increase_pct: float
    monthly_gain_inr: float
    negotiation_notes: str
    summary: str


# ─────────────────────────────────────────
# AGENT 4 OUTPUT: Communication Agent
# ─────────────────────────────────────────

class ResidentMessage(BaseModel):
    target_block: str
    whatsapp_preview: str
    reasoning: str
    expected_improvement_pct: float

class CommunicationResult(BaseModel):
    messages: list[ResidentMessage]
    residents_targeted: int
    overall_segregation_pct: float
    target_segregation_pct: float
    summary: str


# ─────────────────────────────────────────
# CRISIS SYNTHESIS
# ─────────────────────────────────────────

class CrisisOption(BaseModel):
    label: str
    description: str
    cost_inr: float
    fine_exposure_inr: float
    total_outflow_inr: float
    recommended: bool
    reasoning: str

class CrisisSynthesis(BaseModel):
    options: list[CrisisOption]
    final_recommendation: str
    money_saved_vs_worst_inr: float


# ─────────────────────────────────────────
# SSE EVENT
# ─────────────────────────────────────────

class SSEEvent(BaseModel):
    agent: AgentName
    type: str           # "thinking" | "result" | "done" | "error"
    content: str


# ─────────────────────────────────────────
# FINAL AUDIT RESPONSE
# ─────────────────────────────────────────

class AuditResponse(BaseModel):
    society_name: str
    compliance: ComplianceResult
    facility: FacilityResult
    vendor: VendorResult
    communication: CommunicationResult
    crisis_synthesis: CrisisSynthesis
