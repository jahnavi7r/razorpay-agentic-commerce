from fastapi import FastAPI, Header
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import hashlib
import json

app = FastAPI(title="Razorpay Enterprise Agentic Commerce Gateway")

CATALOG = {
    "SKU-01": {"name": "Mechanical Keyboard", "price": 3000.0, "stock": 4, "category": "peripherals"},
    "SKU-02": {"name": "Gaming Mousepad", "price": 800.0, "stock": 10, "category": "peripherals"},
    "SKU-03": {"name": "Laptop Riser Stand", "price": 1200.0, "stock": 0, "category": "furniture"},
    "SKU-04": {"name": "Type-C Fast Cable", "price": 400.0, "stock": 15, "category": "cables"},
}

AUDIT_LOGS: List[Dict[str, Any]] = []
IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}

def compute_state_hash(data: Dict[str, Any]) -> str:
    serialized = json.dumps(data, sort_keys=True)
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]

def log_audit(action: str, status: str, details: Dict[str, Any]):
    event_payload = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "status": status,
        "details": details
    }
    event_payload["state_integrity_hash"] = compute_state_hash(event_payload)
    AUDIT_LOGS.append(event_payload)

class PurchaseIntent(BaseModel):
    items: List[str]
    max_budget: float
    idempotency_key: Optional[str] = None

class CheckoutResult(BaseModel):
    success: bool
    status: str
    order_id: Optional[str] = None
    total_charged: float
    message: str
    upsell_opportunity: Optional[Dict[str, Any]] = None
    recovery_action: Optional[Dict[str, Any]] = None
    recent_audit: List[Dict[str, Any]]

@app.get("/", response_class=HTMLResponse)
def serve_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Razorpay Agentic Commerce Portal</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0b0f19; color: #f8fafc; margin: 0; padding: 25px; }
            .container { max-width: 1000px; margin: auto; }
            h1 { color: #38bdf8; font-size: 22px; margin-bottom: 6px; }
            .subtitle { color: #94a3b8; font-size: 13px; margin-bottom: 24px; }
            .grid { display: grid; grid-template-columns: 1fr 1.2fr; gap: 20px; }
            .card { background: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; }
            button { background: #0284c7; color: white; border: none; padding: 10px 14px; border-radius: 6px; cursor: pointer; margin-bottom: 12px; font-weight: 600; width: 100%; text-align: left; font-size: 13px; transition: 0.2s; }
            button:hover { background: #0369a1; }
            button.danger { background: #b91c1c; }
            button.danger:hover { background: #991b1b; }
            pre { background: #030712; padding: 15px; border-radius: 6px; color: #4ade80; overflow-x: auto; font-size: 12px; min-height: 380px; border: 1px solid #1f2937; line-height: 1.4; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Razorpay Agentic Commerce - Institutional Gateway</h1>
            <div class="subtitle">Bounded Execution Engine &bull; Idempotency Rails &bull; Tamper-Evident SHA-256 Audit Stream</div>
            <div class="grid">
                <div class="card">
                    <h3 style="margin-top:0; font-size: 15px; color: #e2e8f0;">Autonomous Test Harness</h3>
                    <button onclick="runTest(['Keyboard', 'Mousepad'], 4000, 'idem_tx_001')">1. Happy Path + AI Upsell Discovery</button>
                    <button onclick="runTest(['Keyboard', 'Mousepad'], 4000, 'idem_tx_001')">2. Idempotency Lock (Replay Same Tx Key)</button>
                    <button onclick="runTest(['Laptop Riser Stand'], 3000, 'idem_tx_002')">3. Graceful Recovery (Stockout Rerouting)</button>
                    <button class="danger" onclick="runTest(['Keyboard', 'Mousepad'], 2000, 'idem_tx_003')">4. Policy Trip (Hard Budget Ceiling)</button>
                </div>
                <div class="card">
                    <h3 style="margin-top:0; font-size: 15px; color: #e2e8f0;">Live Telemetry & Integrity Hash</h3>
                    <pre id="output">// Gateway ready. Select an execution harness above...</pre>
                </div>
            </div>
        </div>
        <script>
            async function runTest(items, budget, key) {
                const output = document.getElementById('output');
                output.innerText = "Transmitting signed intent payload to gateway...";
                try {
                    const res = await fetch('/agent/checkout', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ items: items, max_budget: budget, idempotency_key: key })
                    });
                    const data = await res.json();
                    output.innerText = JSON.stringify(data, null, 2);
                } catch (e) {
                    output.innerText = "Gateway Connection Error: " + e;
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/agent/checkout", response_model=CheckoutResult)
def execute_agent_checkout(intent: PurchaseIntent):
    # FinTech Feature 1: Idempotency Interceptor
    idem_key = intent.idempotency_key or str(uuid.uuid4())
    if idem_key in IDEMPOTENCY_STORE:
        log_audit("IDEMPOTENCY_CACHE_HIT", "REPLAYED", {"idempotency_key": idem_key})
        cached = IDEMPOTENCY_STORE[idem_key]
        cached_copy = cached.copy()
        cached_copy["recent_audit"] = AUDIT_LOGS[-2:]
        return CheckoutResult(**cached_copy)

    log_audit("INTENT_RECEIVED", "PARSED", {"items": intent.items, "budget": intent.max_budget, "key": idem_key})

    # Catalog SKU Resolution
    resolved_items = []
    for item_name in intent.items:
        found = False
        for sku, info in CATALOG.items():
            if item_name.lower() in info["name"].lower():
                resolved_items.append({"sku": sku, **info})
                found = True
                break
        if not found:
            resolved_items.append({"sku": None, "name": item_name, "stock": 0, "price": 0.0, "category": "unknown"})

    # Graceful Recovery on Stockout
    for item in resolved_items:
        if item.get("stock", 0) <= 0:
            alt = next((v for v in CATALOG.values() if v["stock"] > 0 and v["price"] <= item.get("price", 1000)), None)
            log_audit("STOCKOUT_MITIGATED", "REROUTED", {
                "failed_sku": item["name"],
                "allocated_fallback": alt["name"] if alt else None
            })
            result = {
                "success": False,
                "status": "OUT_OF_STOCK_RECOVERED",
                "order_id": None,
                "total_charged": 0.0,
                "message": f"Inventory depleted for '{item['name']}'. Autonomous fallback suggested.",
                "upsell_opportunity": None,
                "recovery_action": {"action": "RECOMMEND_ALTERNATIVE", "suggestion": alt},
                "recent_audit": AUDIT_LOGS[-3:]
            }
            IDEMPOTENCY_STORE[idem_key] = result
            return CheckoutResult(**result)

    # Dynamic Pricing & Bundle Optimization
    raw_total = sum(i["price"] for i in resolved_items)
    discount = 0.10 if len(resolved_items) >= 2 else 0.0
    final_total = round(raw_total * (1.0 - discount), 2)

    # Strict Budget Gating
    if final_total > intent.max_budget:
        log_audit("BUDGET_GUARDRAIL_TRIPPED", "HALTED", {
            "computed_amount": final_total,
            "authorized_ceiling": intent.max_budget
        })
        result = {
            "success": False,
            "status": "REJECTED_BUDGET_EXCEEDED",
            "order_id": None,
            "total_charged": final_total,
            "message": f"Charge ₹{final_total} exceeds agent spending cap of ₹{intent.max_budget}.",
            "upsell_opportunity": None,
            "recovery_action": {"action": "REQUEST_HUMAN_OVERRIDE"},
            "recent_audit": AUDIT_LOGS[-3:]
        }
        IDEMPOTENCY_STORE[idem_key] = result
        return CheckoutResult(**result)

    # FinTech Feature 2: Agentic Upsell Engine (Track 01 Core Goal)
    upsell = None
    remaining_budget = intent.max_budget - final_total
    eligible_addon = next((v for v in CATALOG.values() if v["name"] not in intent.items and 0 < v["price"] <= remaining_budget and v["stock"] > 0), None)
    if eligible_addon:
        upsell = {
            "sku": eligible_addon["name"],
            "price": eligible_addon["price"],
            "remaining_budget_post_upsell": round(remaining_budget - eligible_addon["price"], 2),
            "reason": f"Fits inside remaining authorized budget limit of ₹{remaining_budget}."
        }
        log_audit("DYNAMIC_UPSELL_IDENTIFIED", "ATTACHED", upsell)

    # Secure Razorpay Order Generation
    order_id = f"order_{uuid.uuid4().hex[:14]}"
    log_audit("RAZORPAY_ORDER_CREATED", "SETTLED", {
        "order_id": order_id,
        "amount_paise": int(final_total * 100),
        "discount_applied": f"{int(discount * 100)}%"
    })

    result = {
        "success": True,
        "status": "ORDER_SUCCESS",
        "order_id": order_id,
        "total_charged": final_total,
        "message": "Bounded transaction completed across Razorpay test rails.",
        "upsell_opportunity": upsell,
        "recovery_action": None,
        "recent_audit": AUDIT_LOGS[-3:]
    }
    IDEMPOTENCY_STORE[idem_key] = result
    return CheckoutResult(**result)