from fastapi import FastAPI
from pydantic import BaseModel
from sklearn.ensemble import IsolationForest

app = FastAPI(title="AI Fraud Detection Engine", version="1.1")

# --- MODEL SETUP ---
normal_activity = [
    [15.50, 1, 0], [45.00, 2, 0], [110.00, 1, 0], [25.00, 1, 0],
    [8.50, 1, 0],  [60.00, 3, 0], [210.00, 2, 0], [35.00, 1, 0]
]
ml_model = IsolationForest(contamination=0.05, random_state=42)
ml_model.fit(normal_activity)

class Transaction(BaseModel):
    amount: float
    velocity_1h: int
    location_mismatch: int

def generate_ai_narrative(decision: str, score: int, tx: Transaction) -> str:
    """Simulates an LLM agent generating an audit-ready risk summary."""
    if decision == "BLOCK":
        return (
            f"CRITICAL RISK ALERT (Score: {score}/100): Transaction of ${tx.amount:,.2f} "
            f"triggered a mandatory safety block. Velocity rate of {tx.velocity_1h} tx/hr "
            f"or threshold exceeds authorized limits. Immediate account freeze recommended."
        )
    elif decision == "REVIEW":
        mismatch_str = "Detected" if tx.location_mismatch == 1 else "None"
        return (
            f"ELEVATED RISK NOTICE (Score: {score}/100): High-amount outlier pattern flagged. "
            f"Amount: ${tx.amount:,.2f} | 1-Hour Velocity: {tx.velocity_1h} | Device/Geo Mismatch: {mismatch_str}. "
            f"Queued for manual analyst verification."
        )
    return f"LOW RISK (Score: {score}/100): Transaction meets baseline parameters. Approved."

@app.post("/evaluate")
def evaluate_transaction(tx: Transaction):
    # Rule 1: Hard Limits
    if tx.amount >= 10000 or tx.velocity_1h > 10:
        decision = "BLOCK"
        score = 95
    # Rule 2: Anomaly Model
    else:
        features = [[tx.amount, tx.velocity_1h, tx.location_mismatch]]
        is_anomaly = ml_model.predict(features)[0] == -1
        
        if is_anomaly or tx.location_mismatch == 1:
            decision = "REVIEW"
            score = 72
        else:
            decision = "ALLOW"
            score = 12

    # Generate Case Summary
    narrative = generate_ai_narrative(decision, score, tx)

    return {
        "decision": decision,
        "risk_score": score,
        "investigation_narrative": narrative
    }