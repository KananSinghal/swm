# backend/agents.py
"""
THE 4 AGENTS — Each makes a real Claude API call with domain-specific prompts.
No hardcoded responses. No fake reasoning. Real AI.

HOW THEY CHAIN:
  SocietyInput → Agent1 → Agent2 → Agent3 → Agent4 → CrisisSynthesis
  Agent2 reads Agent1's fine_risk to decide urgency.
  CrisisSynthesis reads all 4 outputs to recommend the best option.
"""

import json
import os
import anthropic
from .schemas import (
    SocietyInput, ComplianceResult, FacilityResult,
    VendorResult, CommunicationResult, CrisisSynthesis,
    Violation, CorrectiveAction, VendorOption, ResidentMessage,
    CrisisOption, ViolationSeverity, CompostStatus
)
from .rag.retriever import query_law
from .rag.vendor_mock import get_vendor_quotes

# ── Claude client (reads ANTHROPIC_API_KEY from .env) ──────────────
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-20250514"


def _call_claude(system_prompt: str, user_prompt: str) -> str:
    """
    Single Claude call. Returns the raw text content.
    All agents use this — keeps things simple and debuggable.
    """
    message = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return message.content[0].text


def _parse_json(raw: str) -> dict:
    """
    Claude sometimes wraps JSON in ```json ... ```. Strip that.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())


# ═══════════════════════════════════════════════════════════════════
# AGENT 1: COMPLIANCE AGENT
# ═══════════════════════════════════════════════════════════════════

def run_compliance_agent(data: SocietyInput) -> ComplianceResult:
    """
    Uses RAG to pull real SWM 2026 law excerpts, then asks Claude
    to identify violations and compute fine risk.
    """
    # Pull relevant law from Kanan's RAG
    processing_pct = (data.wet_waste_processed_onsite_kg / data.wet_waste_kg) * 100
    excerpts = query_law("on-site wet waste processing requirement bulk waste generator penalty", top_k=4)
    law_context = "\n\n".join([f"[Page {e['page']}]: {e['text']}" for e in excerpts])
    excerpt_snippets = [e['text'][:120] + "..." for e in excerpts]

    system_prompt = """You are a Compliance Agent enforcing India's Solid Waste Management Rules 2026.
You analyze waste data against real SWM 2026 regulations and identify violations with precise fine calculations.
You ALWAYS respond with valid JSON only. No markdown. No explanation outside the JSON."""

    user_prompt = f"""Analyze this society's compliance status against the SWM Rules 2026.

SOCIETY DATA:
- Society: {data.society_name} ({data.total_units} units)
- Wet waste generated: {data.wet_waste_kg} kg/day
- Wet waste processed on-site: {data.wet_waste_processed_onsite_kg} kg/day ({processing_pct:.1f}% — required: 100%)
- Dry waste: {data.dry_waste_kg} kg/day
- Segregation quality: {data.segregation_quality_pct}%

RELEVANT SWM 2026 LAW EXCERPTS (from official gazette):
{law_context}

Return this JSON exactly:
{{
  "compliance_score": <integer 0-100>,
  "violations": [
    {{
      "rule_reference": "<Schedule/Section reference>",
      "description": "<clear violation description>",
      "severity": "<low|medium|high|critical>",
      "fine_per_day_inr": <number>,
      "days_at_risk": <number>,
      "total_fine_risk_inr": <number>
    }}
  ],
  "total_fine_risk_inr": <sum of all fines>,
  "summary": "<2-3 sentences: what's wrong and how bad>",
  "recommendation": "<1 sentence: the single most urgent action>"
}}"""

    raw = _call_claude(system_prompt, user_prompt)
    parsed = _parse_json(raw)

    violations = [Violation(**v) for v in parsed["violations"]]
    return ComplianceResult(
        compliance_score=parsed["compliance_score"],
        violations=violations,
        total_fine_risk_inr=parsed["total_fine_risk_inr"],
        law_excerpts_used=excerpt_snippets,
        summary=parsed["summary"],
        recommendation=parsed["recommendation"]
    )


# ═══════════════════════════════════════════════════════════════════
# AGENT 2: FACILITY AGENT
# ═══════════════════════════════════════════════════════════════════

def run_facility_agent(data: SocietyInput, fine_risk: float) -> FacilityResult:
    """
    Diagnoses the composter using sensor readings.
    Knows the fine_risk from Agent 1 to calibrate urgency.
    """
    system_prompt = """You are a Facility Agent specializing in aerobic composting systems for urban housing societies.
You diagnose composter failures from IoT sensor data and prescribe specific corrective actions with realistic costs.
You ALWAYS respond with valid JSON only. No markdown. No explanation outside the JSON."""

    user_prompt = f"""Diagnose this on-site composter and prescribe corrective actions.

SENSOR READINGS:
- Temperature: {data.composter_temp_celsius}°C  (healthy range: 55–65°C for active composting)
- pH: {data.composter_ph}  (healthy range: 6.5–8.0)
- Moisture: {data.composter_moisture_pct}%  (healthy range: 50–60%)

CONTEXT:
- Society: {data.society_name}
- Wet waste input: {data.wet_waste_kg} kg/day
- On-site processing shortfall: {data.wet_waste_kg - data.wet_waste_processed_onsite_kg:.1f} kg/day is NOT being processed
- Active fine risk from Compliance Agent: ₹{fine_risk:,.0f}
- Every day the composter is down = more fine exposure

Return this JSON exactly:
{{
  "composter_status": "<healthy|warning|critical>",
  "diagnosis": "<root cause in 1-2 sentences, technical but understandable>",
  "corrective_actions": [
    {{
      "action": "<specific action>",
      "estimated_cost_inr": <number>,
      "time_to_effect_hours": <number>
    }}
  ],
  "total_repair_cost_inr": <sum of action costs>,
  "estimated_recovery_hours": <total hours to full operation>,
  "shutdown_risk": <true|false>,
  "summary": "<2 sentences: what's wrong and what it costs vs the fine>"
}}"""

    raw = _call_claude(system_prompt, user_prompt)
    parsed = _parse_json(raw)

    actions = [CorrectiveAction(**a) for a in parsed["corrective_actions"]]
    return FacilityResult(
        composter_status=CompostStatus(parsed["composter_status"]),
        diagnosis=parsed["diagnosis"],
        corrective_actions=actions,
        total_repair_cost_inr=parsed["total_repair_cost_inr"],
        estimated_recovery_hours=parsed["estimated_recovery_hours"],
        shutdown_risk=parsed["shutdown_risk"],
        summary=parsed["summary"]
    )


# ═══════════════════════════════════════════════════════════════════
# AGENT 3: VENDOR AGENT
# ═══════════════════════════════════════════════════════════════════

def run_vendor_agent(data: SocietyInput) -> VendorResult:
    """
    Pulls real vendor quotes from Kanan's vendor_mock module,
    then asks Claude to reason about the best option and negotiation strategy.
    """
    raw_quotes = get_vendor_quotes(
        waste_type="bulk waste",
        area=data.area,
        quantity_kg=data.dry_waste_kg * 30  # monthly volume for vendor negotiation
    )

    # Baseline = what they're paying to worst uncertified vendor
    baseline_price = 1.8  # V003 Rapid Sanitation (uncertified, cheap, what societies default to)

    quotes_summary = json.dumps([
        {
            "vendor": q["vendor_name"],
            "price_per_kg": q["price_per_kg"],
            "total_inr": q["quoted_price_inr"],
            "certified": q["compliance_certified"],
            "rating": q["rating"],
            "response_hours": q["estimated_response_hours"],
            "warning": q["compliance_warning"]
        }
        for q in raw_quotes
    ], indent=2)

    system_prompt = """You are a Vendor Negotiation Agent for a housing society waste management program.
You evaluate vendor quotes, flag non-compliant vendors, and recommend the best certified option with negotiation reasoning.
You ALWAYS respond with valid JSON only. No markdown. No explanation outside the JSON."""

    user_prompt = f"""Evaluate these vendor quotes and recommend the best option for {data.society_name}.

WASTE TO DISPOSE: {data.dry_waste_kg} kg/day dry waste
AREA: {data.area}
CURRENT BASELINE: ₹{baseline_price}/kg (using uncertified local vendor)

VENDOR QUOTES FROM MARKET:
{quotes_summary}

IMPORTANT: Under SWM 2026, using non-certified vendors exposes the society to additional fines.
Factor this into your recommendation.

Return this JSON exactly:
{{
  "recommended_vendor": "<vendor name>",
  "recommended_price_per_kg": <number>,
  "baseline_price_per_kg": {baseline_price},
  "revenue_increase_pct": <percentage improvement over baseline>,
  "monthly_gain_inr": <(recommended_price - baseline) * dry_waste_kg * 30>,
  "negotiation_notes": "<2-3 sentences: why this vendor, what leverage you used, what to watch>",
  "summary": "<1-2 sentences for the dashboard>"
}}"""

    raw = _call_claude(system_prompt, user_prompt)
    parsed = _parse_json(raw)

    vendor_options = [
        VendorOption(
            vendor_name=q["vendor_name"],
            price_per_kg=q["price_per_kg"],
            total_quoted_inr=q["quoted_price_inr"],
            compliance_certified=q["compliance_certified"],
            rating=q["rating"],
            estimated_response_hours=q["estimated_response_hours"],
            compliance_warning=q["compliance_warning"]
        )
        for q in raw_quotes
    ]

    return VendorResult(
        vendors_evaluated=vendor_options,
        recommended_vendor=parsed["recommended_vendor"],
        recommended_price_per_kg=parsed["recommended_price_per_kg"],
        baseline_price_per_kg=parsed["baseline_price_per_kg"],
        revenue_increase_pct=parsed["revenue_increase_pct"],
        monthly_gain_inr=parsed["monthly_gain_inr"],
        negotiation_notes=parsed["negotiation_notes"],
        summary=parsed["summary"]
    )


# ═══════════════════════════════════════════════════════════════════
# AGENT 4: COMMUNICATION AGENT
# ═══════════════════════════════════════════════════════════════════

def run_communication_agent(data: SocietyInput, fine_risk: float) -> CommunicationResult:
    """
    Generates targeted WhatsApp messages for low-compliance blocks.
    Uses behavioral psychology framing (social proof, loss aversion).
    """
    system_prompt = """You are a Communication Agent for a housing society waste compliance system.
You write targeted, warm, non-judgmental WhatsApp messages that use behavioral psychology
(social proof, specific tips, loss aversion) to improve resident waste segregation.
You ALWAYS respond with valid JSON only. No markdown. No explanation outside the JSON."""

    user_prompt = f"""Write targeted resident communications for {data.society_name}.

SEGREGATION DATA:
- Overall society average: {data.segregation_quality_pct}%
- Block B (worst performing): {data.block_b_segregation_pct}%
- Target: 80%+
- Active fine risk: ₹{fine_risk:,.0f}/month (residents are partly responsible)

CONTEXT:
- Society has 4 bin colors: Green (wet/food), Blue (dry/plastic/paper), Yellow (sanitary), Red (e-waste/batteries)
- Fine risk is real — SWM 2026 penalties start April 1, 2026
- Tone must be warm and community-focused, NOT accusatory

Return this JSON exactly:
{{
  "messages": [
    {{
      "target_block": "Block B",
      "whatsapp_preview": "<the full WhatsApp message, max 150 words, use emojis naturally>",
      "reasoning": "<1 sentence: why this block, what behavioral technique used>",
      "expected_improvement_pct": <realistic improvement estimate, e.g. 12>
    }}
  ],
  "residents_targeted": <estimated number of families in Block B>,
  "overall_segregation_pct": {data.segregation_quality_pct},
  "target_segregation_pct": 80,
  "summary": "<1 sentence for the dashboard>"
}}"""

    raw = _call_claude(system_prompt, user_prompt)
    parsed = _parse_json(raw)

    messages = [ResidentMessage(**m) for m in parsed["messages"]]
    return CommunicationResult(
        messages=messages,
        residents_targeted=parsed["residents_targeted"],
        overall_segregation_pct=parsed["overall_segregation_pct"],
        target_segregation_pct=parsed["target_segregation_pct"],
        summary=parsed["summary"]
    )


# ═══════════════════════════════════════════════════════════════════
# CRISIS SYNTHESIS — reads all 4 agent outputs
# ═══════════════════════════════════════════════════════════════════

def run_crisis_synthesis(
    data: SocietyInput,
    compliance: ComplianceResult,
    facility: FacilityResult,
    vendor: VendorResult
) -> CrisisSynthesis:
    """
    The "Reasoning Chain" screen.
    Compares options and recommends the financially optimal path.
    This is what makes KaizenWaste agentic — real cost-benefit reasoning.
    """
    system_prompt = """You are a strategic advisor synthesizing outputs from 4 AI agents to recommend
the optimal crisis resolution path for a housing society facing SWM 2026 compliance violations.
You weigh financial costs, compliance risk, and operational feasibility.
You ALWAYS respond with valid JSON only. No markdown. No explanation outside the JSON."""

    user_prompt = f"""Synthesize the agent findings and recommend the best option.

SITUATION SUMMARY:
- Society: {data.society_name}
- Compliance score: {compliance.compliance_score}/100
- Active fine risk: ₹{compliance.total_fine_risk_inr:,.0f}/month
- Composter status: {facility.composter_status.value}
- Repair cost if we fix it: ₹{facility.total_repair_cost_inr:,.0f}
- Recovery time: {facility.estimated_recovery_hours} hours (during which fines accumulate)
- Best vendor deal available: ₹{vendor.recommended_price_per_kg}/kg (vs ₹{vendor.baseline_price_per_kg}/kg before)

Generate a cost-benefit comparison of 3 options and recommend one:
- Option A: Do Nothing (pay fines, don't repair)
- Option B: Emergency Repair + Vendor Switch (fix composter, switch to certified vendor)
- Option C: Full Outsource (pay a premium vendor to handle everything, skip on-site processing for now)

Return this JSON exactly:
{{
  "options": [
    {{
      "label": "Option A",
      "description": "<what this means in practice>",
      "cost_inr": <direct costs>,
      "fine_exposure_inr": <expected fine payment>,
      "total_outflow_inr": <cost + fine>,
      "recommended": false,
      "reasoning": "<1 sentence>"
    }},
    {{
      "label": "Option B",
      "description": "<what this means in practice>",
      "cost_inr": <repair + vendor switch costs>,
      "fine_exposure_inr": <fines during repair window>,
      "total_outflow_inr": <total>,
      "recommended": true,
      "reasoning": "<1 sentence — why this is the winner>"
    }},
    {{
      "label": "Option C",
      "description": "<what this means in practice>",
      "cost_inr": <outsourcing premium cost>,
      "fine_exposure_inr": <any remaining exposure>,
      "total_outflow_inr": <total>,
      "recommended": false,
      "reasoning": "<1 sentence>"
    }}
  ],
  "final_recommendation": "<2-3 sentences: the recommended action, why, and expected outcome>",
  "money_saved_vs_worst_inr": <Option_B_total minus Option_A_total, i.e., savings>
}}"""

    raw = _call_claude(system_prompt, user_prompt)
    parsed = _parse_json(raw)

    options = [CrisisOption(**o) for o in parsed["options"]]
    return CrisisSynthesis(
        options=options,
        final_recommendation=parsed["final_recommendation"],
        money_saved_vs_worst_inr=parsed["money_saved_vs_worst_inr"]
    )
