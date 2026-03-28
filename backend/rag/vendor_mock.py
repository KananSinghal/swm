# backend/rag/vendor_mock.py
"""
WHAT THIS FILE DOES:
- Provides fake (but realistic) vendor data for Agent 3 (Vendor Negotiation)
- Simulates getting quotes from waste management vendors
- Includes some non-compliant vendors so Agent 3 can flag them

RUN THIS FILE DIRECTLY TO TEST:
  python -m backend.rag.vendor_mock
"""

import random
from datetime import datetime, timedelta

from typing import Optional

# ── Master vendor database (fake but realistic) ───────────────────
VENDOR_DATABASE = [
    {
        "vendor_id": "V001",
        "name": "GreenWaste Solutions Pvt Ltd",
        "contact_phone": "+91-9876543210",
        "whatsapp_number": "919876543210",   # No + for WhatsApp API
        "email": "info@greenwaste.in",
        "services": ["door-to-door collection", "bulk waste", "e-waste", "recycling"],
        "base_rate_per_kg": 2.5,             # INR per kg
        "minimum_quantity_kg": 100,
        "swm_license": "SWM/DL/2024/001",
        "compliance_certified": True,
        "rating": 4.2,
        "areas_covered": ["South Delhi", "Central Delhi", "Lajpat Nagar"],
        "response_time_hours": 24,
    },
    {
        "vendor_id": "V002",
        "name": "EcoClean Municipal Services",
        "contact_phone": "+91-9812345678",
        "whatsapp_number": "919812345678",
        "email": "ops@ecoclean.in",
        "services": ["bulk waste", "construction debris", "hazardous waste", "recycling"],
        "base_rate_per_kg": 3.1,
        "minimum_quantity_kg": 500,
        "swm_license": "SWM/DL/2024/018",
        "compliance_certified": True,
        "rating": 4.5,
        "areas_covered": ["North Delhi", "East Delhi", "Rohini"],
        "response_time_hours": 12,
    },
    {
        "vendor_id": "V003",
        "name": "Rapid Sanitation Corp",
        "contact_phone": "+91-9898765432",
        "whatsapp_number": "919898765432",
        "email": "contact@rapidsanit.in",
        "services": ["door-to-door collection", "bio-waste", "bulk waste"],
        "base_rate_per_kg": 1.8,             # Cheapest — but not certified!
        "minimum_quantity_kg": 50,
        "swm_license": None,                 # ← NOT LICENSED
        "compliance_certified": False,       # ← Agent 3 should flag this
        "rating": 3.1,
        "areas_covered": ["West Delhi", "Dwarka", "Janakpuri"],
        "response_time_hours": 48,
    },
    {
        "vendor_id": "V004",
        "name": "BestWaste Management Ltd",
        "contact_phone": "+91-9711234567",
        "whatsapp_number": "919711234567",
        "email": "bids@bestwaste.in",
        "services": ["bulk waste", "recycling", "door-to-door collection", "e-waste"],
        "base_rate_per_kg": 2.2,
        "minimum_quantity_kg": 200,
        "swm_license": "SWM/DL/2025/042",
        "compliance_certified": True,
        "rating": 4.0,
        "areas_covered": ["South Delhi", "Gurgaon", "Faridabad"],
        "response_time_hours": 24,
    },
    {
        "vendor_id": "V005",
        "name": "CityCare Waste Services",
        "contact_phone": "+91-9654321098",
        "whatsapp_number": "919654321098",
        "email": "hello@citycare.in",
        "services": ["door-to-door collection", "bio-waste", "recycling"],
        "base_rate_per_kg": 2.8,
        "minimum_quantity_kg": 100,
        "swm_license": "SWM/DL/2023/099",
        "compliance_certified": True,
        "rating": 3.8,
        "areas_covered": ["Central Delhi", "Connaught Place", "Karol Bagh"],
        "response_time_hours": 36,
    },
]


def get_vendor_quotes(
    waste_type: str = "bulk waste",
    area: str = None,
    quantity_kg: float = 1000.0
) -> list[dict]:
    """
    ════════════════════════════════════════════
    THE MAIN FUNCTION — Person 1 calls this for Agent 3 (Vendor Negotiation).
    ════════════════════════════════════════════
    
    Args:
        waste_type:   e.g. "bulk waste", "bio-waste", "e-waste", "recycling"
        area:         e.g. "South Delhi" — filters by coverage area
        quantity_kg:  How many kg of waste needs collection
    
    Returns:
        List of vendor quotes, sorted cheapest first:
        [
            {
                "vendor_id": "V004",
                "vendor_name": "BestWaste Management Ltd",
                "contact_phone": "+91-9711234567",
                "whatsapp_number": "919711234567",
                "compliance_certified": True,
                "swm_license": "SWM/DL/2025/042",
                "quoted_price_inr": 2134.50,
                "price_per_kg": 2.13,
                "services_offered": [...],
                "quote_valid_until": "2026-04-04",
                "estimated_response_hours": 24,
                "rating": 4.0,
                "compliance_warning": False,
            },
            ...
        ]
    """
    matched_vendors = []

    for vendor in VENDOR_DATABASE:
        # Check if vendor offers this type of service
        service_match = any(
            waste_type.lower() in service.lower()
            for service in vendor["services"]
        )
        if not service_match:
            continue

        # Check if vendor covers this area (if area filter given)
        if area:
            area_match = any(
                area.lower() in coverage.lower()
                for coverage in vendor["areas_covered"]
            )
            if not area_match:
                continue

        # Check minimum quantity
        if quantity_kg < vendor["minimum_quantity_kg"]:
            continue

        # Simulate realistic price variation (±15%)
        random.seed(vendor["vendor_id"])  # Same seed = same "quote" each run
        variation_factor = random.uniform(0.85, 1.15)
        final_rate = vendor["base_rate_per_kg"] * variation_factor
        total_price = final_rate * quantity_kg

        matched_vendors.append({
            "vendor_id": vendor["vendor_id"],
            "vendor_name": vendor["name"],
            "contact_phone": vendor["contact_phone"],
            "whatsapp_number": vendor["whatsapp_number"],
            "email": vendor["email"],
            "compliance_certified": vendor["compliance_certified"],
            "swm_license": vendor["swm_license"],
            "quoted_price_inr": round(total_price, 2),
            "price_per_kg": round(final_rate, 2),
            "services_offered": vendor["services"],
            "areas_covered": vendor["areas_covered"],
            "quote_valid_until": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
            "estimated_response_hours": vendor["response_time_hours"],
            "rating": vendor["rating"],
            "compliance_warning": not vendor["compliance_certified"],
        })

    # Sort: certified first, then by price
    matched_vendors.sort(
        key=lambda v: (not v["compliance_certified"], v["quoted_price_inr"])
    )

    return matched_vendors


def get_all_vendors() -> list[dict]:
    """Return full vendor database (for Agent 3 to browse all options)."""
    return VENDOR_DATABASE


def get_vendor_by_id(vendor_id: str) -> Optional[dict]:
    """Look up a specific vendor by ID."""
    for vendor in VENDOR_DATABASE:
        if vendor["vendor_id"] == vendor_id:
            return vendor
    return None


# ─────────────────────────────────────────────
# TEST: Run this file directly
# Command: python -m backend.rag.vendor_mock
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("TESTING VENDOR MOCK DATA")
    print("=" * 50)

    print("\n--- Test 1: Bulk waste in South Delhi, 1000kg ---")
    quotes = get_vendor_quotes("bulk waste", "South Delhi", 1000)
    for q in quotes:
        certified = "CERTIFIED ✓" if q["compliance_certified"] else "⚠ NOT CERTIFIED"
        print(f"  {q['vendor_name']}: ₹{q['quoted_price_inr']:,.2f} | {certified} | Rating: {q['rating']}")

    print("\n--- Test 2: Bio-waste, no area filter, 500kg ---")
    quotes = get_vendor_quotes("bio-waste", quantity_kg=500)
    for q in quotes:
        print(f"  {q['vendor_name']}: ₹{q['quoted_price_inr']:,.2f} | WhatsApp: {q['whatsapp_number']}")

    print("\n--- Test 3: Look up vendor V002 ---")
    vendor = get_vendor_by_id("V002")
    print(f"  Name: {vendor['name']}")
    print(f"  License: {vendor['swm_license']}")
    print(f"  Services: {', '.join(vendor['services'])}")

    print("\n✓ vendor_mock.py is working correctly!")