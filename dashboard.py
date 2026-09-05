import streamlit as st
import requests
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="AI Fraud Operations Center", layout="wide")

# --- DATABASE ENGINE SETUP ---
def init_db():
    conn = sqlite3.connect("fraud_audit.db")
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            amount TEXT,
            ai_recommendation TEXT,
            analyst_action TEXT,
            score INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def insert_log(amount, rec, action, score):
    conn = sqlite3.connect("fraud_audit.db")
    c = conn.cursor()
    c.execute('''
        INSERT INTO audit_logs (timestamp, amount, ai_recommendation, analyst_action, score)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), amount, rec, action, score))
    conn.commit()
    conn.close()

def get_logs():
    conn = sqlite3.connect("fraud_audit.db")
    df = pd.read_sql_query("SELECT timestamp as 'Timestamp', amount as 'Amount', ai_recommendation as 'AI Recommendation', analyst_action as 'Analyst Action', score as 'Score' FROM audit_logs ORDER BY id DESC", conn)
    conn.close()
    return df

init_db()

st.title("🛡️ AI Fraud Operations & Risk Center")
st.write("Real-time risk scoring, automated case narratives, and persistent audit logging.")

st.divider()

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("1. Incoming Transaction Stream")
    amount = st.number_input("Transaction Amount ($)", min_value=0.0, value=3400.00, step=100.0)
    velocity = st.slider("1-Hour Velocity (Transactions)", min_value=1, max_value=15, value=6)
    mismatch_option = st.selectbox("Location / Device Mismatch?", ["No Mismatch", "Mismatch Detected"])
    location_mismatch = 1 if mismatch_option == "Mismatch Detected" else 0

    if st.button("Evaluate Transaction", type="primary"):
        payload = {"amount": amount, "velocity_1h": velocity, "location_mismatch": location_mismatch}
        try:
            response = requests.post("https://ai-fraud-engine.onrender.com/evaluate", json=payload)
            st.session_state.current_eval = response.json()
            st.session_state.current_tx = payload
        except Exception:
            st.error("Backend engine offline. Ensure Uvicorn is running.")

with col_right:
    st.subheader("2. AI Risk File & Resolution Queue")
    if "current_eval" in st.session_state:
        data = st.session_state.current_eval
        decision = data.get("decision")
        score = data.get("risk_score")
        narrative = data.get("investigation_narrative")
        
        if decision == "BLOCK":
            st.error(f"🚨 AI SUGGESTION: {decision} (Risk Score: {score}/100)")
        elif decision == "REVIEW":
            st.warning(f"⚠️ AI SUGGESTION: {decision} (Risk Score: {score}/100)")
        else:
            st.success(f"✅ AI SUGGESTION: {decision} (Risk Score: {score}/100)")
            
        st.info(narrative)
        
        st.write("**Analyst Action:**")
        act1, act2, act3 = st.columns(3)
        
        with act1:
            if st.button("Confirm Block"):
                insert_log(f"${st.session_state.current_tx['amount']:,.2f}", decision, "BLOCKED", score)
                st.success("Saved to database.")
                st.rerun()
        with act2:
            if st.button("Override & Approve"):
                insert_log(f"${st.session_state.current_tx['amount']:,.2f}", decision, "APPROVED (OVERRIDE)", score)
                st.success("Saved to database.")
                st.rerun()
        with act3:
            if st.button("Escalate to SAR"):
                insert_log(f"${st.session_state.current_tx['amount']:,.2f}", decision, "ESCALATED (SAR FILING)", score)
                st.warning("Saved to database.")
                st.rerun()

st.divider()
st.subheader("3. Persistent Database Audit Log")
logs_df = get_logs()
if not logs_df.empty:
    st.dataframe(logs_df, use_container_width=True)
else:
    st.caption("No persistent transactions logged in database yet.")
