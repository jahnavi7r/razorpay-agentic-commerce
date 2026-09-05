from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

app = FastAPI(title="Razorpay Agentic Commerce API")

CATALOG = {
    "SKU-01": {"name": "Mechanical Keyboard", "price": 3000.0, "stock": 4},
    "SKU-02": {"name": "Gaming Mousepad", "price": 800.0, "stock": 10},
    "SKU-03": {"name": "Laptop Riser Stand", "price": 1200.0, "stock": 0},
    "SKU-04": {"name": "Type-C Fast Cable", "price": 400.0, "stock": 15},
}

AUDIT_LOGS: List[Dict[str, Any]] = []

def log_audit(action: str, status: str, details: Dict[str, Any]):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "status": status,
        "details": details
    }
    AUDIT_LOGS.append(entry)

class PurchaseIntent(BaseModel):
    items: List[str]
    max_budget: float

class CheckoutResult(BaseModel):
    success: bool
    status: str
    order_id: Optional[str] = None
    total_charged: float
    message: str
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
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 30px; }
            .container { max-width: 900px; margin: auto; }
            h1 { color: #38bdf8; font-size: 24px; margin-bottom: 20px; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
            .card { background: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; }
            button { background: #0284c7; color: white; border: none; padding: 10px 16px; border-radius: 6px; cursor: pointer; margin-right: 8px; font-weight: bold; }
            button:hover { background: #0369a1; }
            pre { background: #0b0f19; padding: 15px; border-radius: 6px; color: #4ade80; overflow-x: auto; font-size: 13px; min-height: 250px; border: 1px solid #1e293b; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Razorpay Agentic Commerce - Live Demo Dashboard</h1>
            <div class="grid">
                <div class="card">
                    <h3>Simulate Agent Actions</h3>
                    <p style="color: #94a3b8; font-size: 14px;">Trigger agentic checkout workflows to observe bounded execution and recovery rails.</p>
                    <button onclick="runTest(['Keyboard', 'Mousepad'], 4000)">1. Happy Path (Bounded ₹4000)</button><br><br>
                    <button onclick="runTest(['Laptop Riser Stand'], 3000)">2. Failure Mode (Stockout Recovery)</button><br><br>
                    <button onclick="runTest(['Keyboard', 'Mousepad'], 2000)">3. Guardrail Trip (Over Budget)</button>
                </div>
                <div class="card">
                    <h3>Live Agent Telemetry & Audit Trail</h3>
                    <pre id="output">// Results and audit trail will render here...</pre>
                </div>
            </div>
        </div>
        <script>
            async function runTest(items, budget) {
                const output = document.getElementById('output');
                output.innerText = "Executing bounded agent transaction...";
                try {
                    const res = await fetch('/agent/checkout', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ items: items, max_budget: budget })
                    });
                    const data = await res.json();
                    output.innerText = JSON.stringify(data, null, 2);
                } catch (e) {
                    output.innerText = "Error: " + e;
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/agent/checkout", response_model=CheckoutResult)
def execute_agent_checkout(intent: PurchaseIntent):
    log_audit("INTENT_RECEIVED", "SUCCESS", {"items": intent.items, "budget": intent.max_budget})

    resolved_items = []
    for item_name in intent.items:
        found = False
        for sku, info in CATALOG.items():
            if item_name.lower() in info["name"].lower():
                resolved_items.append({"sku": sku, **info})
                found = True
                break
        if not found:
            resolved_items.append({"sku": None, "name": item_name, "stock": 0, "price": 0.0})

    for item in resolved_items:
        if item.get("stock", 0) <= 0:
            alternative = next((v for v in CATALOG.values() if v["stock"] > 0 and v["price"] <= item.get("price", 1000)), None)
            log_audit("STOCKOUT_DETECTED", "GRACEFUL_RECOVERY", {
                "failed_sku": item["name"],
                "suggested_alt": alternative["name"] if alternative else None
            })
            return CheckoutResult(
                success=False,
                status="OUT_OF_STOCK_RECOVERED",
                total_charged=0.0,
                message=f"Item '{item['name']}' is out of stock. Graceful recovery fallback triggered.",
                recovery_action={
                    "action": "AUTO_RECOMMEND_ALTERNATIVE",
                    "suggestion": alternative
                },
                recent_audit=AUDIT_LOGS[-3:]
            )

    raw_total = sum(i["price"] for i in resolved_items)
    discount = 0.10 if len(resolved_items) >= 2 else 0.0
    final_total = round(raw_total * (1.0 - discount), 2)

    if final_total > intent.max_budget:
        log_audit("BUDGET_LIMIT_EXCEEDED", "BLOCKED", {
            "requested_total": final_total,
            "user_ceiling": intent.max_budget
        })
        return CheckoutResult(
            success=False,
            status="REJECTED_BUDGET_EXCEEDED",
            total_charged=final_total,
            message=f"Calculated cost (₹{final_total}) exceeds maximum authorized budget (₹{intent.max_budget}).",
            recovery_action={"action": "REQUEST_BUDGET_INCREASE"},
            recent_audit=AUDIT_LOGS[-3:]
        )

    order_id = f"order_{uuid.uuid4().hex[:14]}"
    log_audit("RAZORPAY_ORDER_CREATED", "COMPLETED", {
        "order_id": order_id,
        "amount_paise": int(final_total * 100),
        "discount_applied": f"{int(discount * 100)}%"
    })

    return CheckoutResult(
        success=True,
        status="ORDER_SUCCESS",
        order_id=order_id,
        total_charged=final_total,
        message="Agent completed bounded checkout successfully.",
        recent_audit=AUDIT_LOGS[-3:]
    )