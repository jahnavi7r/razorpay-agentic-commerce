from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

app = FastAPI(title="Razorpay Agentic Commerce API")

# 1. Product Catalog Database
CATALOG = {
    "SKU-01": {"name": "Mechanical Keyboard", "price": 3000.0, "stock": 4},
    "SKU-02": {"name": "Gaming Mousepad", "price": 800.0, "stock": 10},
    "SKU-03": {"name": "Laptop Riser Stand", "price": 1200.0, "stock": 0},  # Stockout test
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

# 2. Request / Response Models
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

# 3. Agent Execution Endpoint
@app.post("/agent/checkout", response_model=CheckoutResult)
def execute_agent_checkout(intent: PurchaseIntent):
    log_audit("INTENT_RECEIVED", "SUCCESS", {"items": intent.items, "budget": intent.max_budget})

    # Step A: Resolve items against catalog
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

    # Step B: Graceful Failure Check (Stockout Recovery)
    for item in resolved_items:
        if item.get("stock", 0) <= 0:
            # Find an in-stock alternative under the same price
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

    # Step C: Dynamic Bundle Discount Logic
    raw_total = sum(i["price"] for i in resolved_items)
    discount = 0.10 if len(resolved_items) >= 2 else 0.0  # 10% bundle discount
    final_total = round(raw_total * (1.0 - discount), 2)

    # Step D: Hard Spending Guardrail (Bounded Barrier)
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

    # Step E: Razorpay Order Creation (Deterministic Test Gateway)
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

@app.get("/agent/audit-trail")
def view_audit_trail():
    return {"total_actions": len(AUDIT_LOGS), "audit_trail": AUDIT_LOGS}