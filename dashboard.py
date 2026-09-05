import streamlit as st
import requests
import pandas as pd
import sqlite3
from datetime import datetime

st.set_page_config(page_title="AI Fraud Operations Center", layout="wide")

# --- DATABASE SETUP ---
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
st.write("Real-time risk scoring, automated case narratives, and batch processing.")

# --- SIDEBAR THRESHOLD CONTROLS ---
st.sidebar.header("⚙️ Risk Sensitivity Controls")
st.sidebar.write("Adjust rules live to tune detection sensitivity.")
block_limit = st.sidebar.slider("Instant Block Threshold ($)", min_value=1000, max_value=20000, value=10000, step=1000)
velocity_limit = st.sidebar.slider("Velocity Warning Trigger (1-Hr)", min_value=1, max_value=10, value=5)

st.divider()

# --- TABS FOR SINGLE VS BATCH MODE ---
tab1, tab2 = st.tabs(["⚡ Live Single Transaction", "📁 Batch CSV Processing"])

with tab1:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. Incoming Transaction")
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
                st.error("Backend engine offline. Ensure Render service is running.")

    with col_right:
        st.subheader("2. AI Risk File & Resolution Queue")
        if "current_eval" in st.session_state:
            data = st.session_state.current_eval
            decision = data.get("decision")
            score = data.get("risk_score")
            narrative = data.get("investigation_narrative")
            
            # Apply dynamic sidebar overrides visually
            if amount >= block_limit:
                decision = "BLOCK"
                score = max(score, 90)
                narrative = f"HARD RULE BREACH: Amount exceeds dynamic sidebar limit of ${block_limit:,.2f}."

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
                    st.success("Saved to audit log.")
                    st.rerun()
            with act2:
                if st.button("Override & Approve"):
                    insert_log(f"${st.session_state.current_tx['amount']:,.2f}", decision, "APPROVED (OVERRIDE)", score)
                    st.success("Saved to audit log.")
                    st.rerun()
            with act3:
                if st.button("Escalate to SAR"):
                    insert_log(f"${st.session_state.current_tx['amount']:,.2f}", decision, "ESCALATED (SAR FILING)", score)
                    st.warning("Saved to audit log.")
                    st.rerun()

with tab2:
    st.subheader("Batch Transaction Assessment")
    st.write("Upload a CSV file containing transaction data (`amount`, `velocity_1h`, `location_mismatch`) to run risk evaluation at scale.")
    
    uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
    
    if uploaded_file is not None:
        batch_df = pd.read_csv(uploaded_file)
        st.write("Preview Uploaded Data:", batch_df.head())
        
        if st.button("Run Batch AI Risk Assessment"):
            results = []
            for idx, row in batch_df.iterrows():
                payload = {
                    "amount": float(row["amount"]),
                    "velocity_1h": int(row["velocity_1h"]),
                    "location_mismatch": int(row["location_mismatch"])
                }
                try:
                    res = requests.post("https://ai-fraud-engine.onrender.com/evaluate", json=payload).json()
                    
                    # Sidebar logic dynamic override
                    rec = res["decision"]
                    score = res["risk_score"]
                    if float(row["amount"]) >= block_limit:
                        rec = "BLOCK"
                        score = max(score, 90)
                        
                    results.append({
                        "Tx ID": f"TX-{idx+1001}",
                        "Amount": f"${float(row['amount']):,.2f}",
                        "Velocity": row["velocity_1h"],
                        "Mismatch": row["location_mismatch"],
                        "Risk Score": score,
                        "Recommendation": rec
                    })
                except Exception:
                    st.error("Error communicating with API backend.")
                    break
            
            res_df = pd.DataFrame(results)
            st.success(f"Processed {len(res_df)} transactions successfully!")
            
            # Risk Metrics Summary
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Allowed", len(res_df[res_df["Recommendation"] == "ALLOW"]))
            m2.metric("Requires Review", len(res_df[res_df["Recommendation"] == "REVIEW"]))
            m3.metric("Blocked", len(res_df[res_df["Recommendation"] == "BLOCK"]))
            
            st.dataframe(res_df, use_container_width=True)

st.divider()
st.subheader("3. Persistent Audit Log Queue")
logs_df = get_logs()
if not logs_df.empty:
    st.dataframe(logs_df, use_container_width=True)
else:
    st.caption("No persistent transactions logged in database yet.")
