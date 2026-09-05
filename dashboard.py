import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client

# 1. PAGE CONFIGURATION (Must be the very first Streamlit command)
st.set_page_config(page_title="AI Fraud Operations Center", layout="wide")

# 2. AUTHENTICATION GATE
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔒 Operations Portal Access")
        st.caption("Restricted Access: Authorized Fraud Analyst Personnel Only")
        
        user_pwd = st.text_input("Enter Analyst Security Token", type="password")
        if st.button("Authenticate Session", type="primary"):
            if user_pwd == st.secrets.get("APP_PASSWORD", "admin123"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Access Denied: Invalid security token.")
        return False
    return True

if not check_password():
    st.stop()

# 3. SUPABASE CLOUD DATABASE CONNECTION
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

def insert_log(amount, rec, action, score):
    supabase.table("audit_logs").insert({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "ai_recommendation": rec,
        "analyst_action": action,
        "score": score
    }).execute()

def get_logs():
    response = supabase.table("audit_logs").select("*").order("id", desc=True).execute()
    if response.data:
        df = pd.DataFrame(response.data)
        df = df.rename(columns={
            "timestamp": "Timestamp",
            "amount": "Amount",
            "ai_recommendation": "AI Recommendation",
            "analyst_action": "Analyst Action",
            "score": "Score"
        })
        return df[["Timestamp", "Amount", "AI Recommendation", "Analyst Action", "Score"]]
    return pd.DataFrame()

# 4. DASHBOARD HEADER & SIDEBAR CONTROLS
st.title("🛡️ AI Fraud Operations & Risk Center")
st.write("Real-time risk scoring, automated case narratives, and persistent cloud audit logging.")

st.sidebar.header("⚙️ Risk Sensitivity Controls")
block_limit = st.sidebar.slider("Instant Block Threshold ($)", min_value=1000, max_value=20000, value=10000, step=1000)
velocity_limit = st.sidebar.slider("Velocity Warning Trigger (1-Hr)", min_value=1, max_value=10, value=5)

st.divider()

# 5. TABBED INTERFACE (LIVE ASSESSMENT & BATCH ASSESSMENT)
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
                st.error("Backend engine offline. Ensure Render web service is running.")

    with col_right:
        st.subheader("2. AI Risk File & Resolution Queue")
        if "current_eval" in st.session_state:
            data = st.session_state.current_eval
            decision = data.get("decision")
            score = data.get("risk_score")
            narrative = data.get("investigation_narrative")
            
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
                    st.success("Saved to Supabase database.")
                    st.rerun()
            with act2:
                if st.button("Override & Approve"):
                    insert_log(f"${st.session_state.current_tx['amount']:,.2f}", decision, "APPROVED (OVERRIDE)", score)
                    st.success("Saved to Supabase database.")
                    st.rerun()
            with act3:
                if st.button("Escalate to SAR"):
                    insert_log(f"${st.session_state.current_tx['amount']:,.2f}", decision, "ESCALATED (SAR FILING)", score)
                    st.warning("Saved to Supabase database.")
                    st.rerun()

with tab2:
    st.subheader("Batch Transaction Assessment")
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
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Allowed", len(res_df[res_df["Recommendation"] == "ALLOW"]))
            m2.metric("Requires Review", len(res_df[res_df["Recommendation"] == "REVIEW"]))
            m3.metric("Blocked", len(res_df[res_df["Recommendation"] == "BLOCK"]))
            
            st.dataframe(res_df, use_container_width=True)

# 6. PERSISTENT CLOUD DATABASE AUDIT LOG
st.divider()
st.subheader("3. Persistent Cloud Database Audit Log")
try:
    logs_df = get_logs()
    if not logs_df.empty:
        st.dataframe(logs_df, use_container_width=True)
    else:
        st.caption("No persistent transactions logged in database yet.")
except Exception as e:
    st.error(f"Error fetching audit logs: {e}")
