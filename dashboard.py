"""
Streamlit dashboard: pick a real test-set record (or enter values manually),
run it through the full pipeline live, and see triage -> investigation ->
containment -> audit trail rendered visually instead of as terminal text.

Run with: streamlit run dashboard.py
"""
import streamlit as st
import pandas as pd
import os
import sys
from dotenv import load_dotenv

load_dotenv()  # reads .env in this folder if present -- see .env.example

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orchestrator import Orchestrator

st.set_page_config(page_title="SOC-Agent Dashboard", layout="wide")

@st.cache_resource
def get_orchestrator():
    return Orchestrator()

@st.cache_data
def load_test_data():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "test_clean.csv")
    return pd.read_csv(path)

orchestrator = get_orchestrator()
df = load_test_data()

st.title("🛡️ SOC-Agent: Multi-Agent Security Incident Response")
st.caption(
    "Portfolio/demo project — evaluated on the public NSL-KDD benchmark dataset. "
    "Not a production security product. See README for full scope and honest limitations."
)

st.sidebar.header("Select an Alert")
mode = st.sidebar.radio("Source", ["Pick a real test-set example", "Random sample"])

if mode == "Pick a real test-set example":
    category = st.sidebar.selectbox("Ground-truth category", sorted(df["category"].unique()))
    subset = df[df["category"] == category]
    idx = st.sidebar.slider("Example index", 0, min(len(subset) - 1, 99), 0)
    row = subset.iloc[idx]
else:
    if st.sidebar.button("🎲 Draw random record"):
        st.session_state["random_row"] = df.sample(1).iloc[0]
    row = st.session_state.get("random_row", df.sample(1, random_state=1).iloc[0])

ground_truth = row["category"]
record = row.drop(labels=["label", "category"]).to_dict()

with st.sidebar.expander("Raw record features"):
    st.json({k: v for k, v in list(record.items())[:15]})

st.sidebar.markdown(f"**Ground truth category:** `{ground_truth}`")
run = st.sidebar.button("▶️ Run through pipeline", type="primary")

if run:
    result = orchestrator.process_alert(record)

    col1, col2, col3 = st.columns(3)
    col1.metric("Incident ID", result["incident_id"])
    col2.metric("Verdict", result["verdict"])
    col3.metric("Total latency", f"{result['timings']['total_sec']*1000:.1f} ms")

    st.divider()

    # --- Stage 1: Triage ---
    st.subheader("1️⃣ Triage Agent")
    t = result["triage"]
    correct = t["category"] == ground_truth
    badge = "✅ matches ground truth" if correct else "⚠️ MISCLASSIFIED (see README for known r2l/u2r limitation)"
    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    tcol1.metric("Predicted category", t["category"])
    tcol2.metric("Severity", t["severity"])
    tcol3.metric("Confidence", f"{t['confidence']*100:.1f}%")
    tcol4.markdown(f"**{badge}**")

    if result["verdict"] == "benign":
        st.info("Classified as normal traffic — pipeline stops here. No investigation or containment triggered.")
    else:
        # --- Stage 2: Investigation ---
        st.subheader("2️⃣ Investigation Agent")
        inv = result["investigation"]
        st.markdown(f"**MITRE ATT&CK:** `{inv['mitre_technique_id']}` — {inv['mitre_technique_name']}")
        st.markdown(f"**Narrative:** {inv['narrative']}")
        st.markdown("**Timeline:**")
        for event in inv["timeline"]:
            st.markdown(f"- {event}")

        # --- Stage 3: Containment ---
        st.subheader("3️⃣ Containment Agent")
        cont = result["containment"]
        for action in cont["actions"]:
            tier = action["tier"]
            if action.get("blocked_reason"):
                st.warning(f"🚫 `{action['action']}` (Tier {tier}) — blocked: {action['blocked_reason']}")
            elif action["auto"]:
                st.success(f"✅ `{action['action']}` (Tier {tier}) — auto-approved, executed immediately")
            elif action["approved"]:
                st.success(f"✅ `{action['action']}` (Tier {tier}) — human-approved (simulated), executed")
            else:
                st.error(f"❌ `{action['action']}` (Tier {tier}) — human REJECTED, rolled back")

    st.divider()

    # --- Audit Trail ---
    st.subheader("📋 Full Audit Trail")
    trail = orchestrator.get_audit_trail(result["incident_id"])
    trail_df = pd.DataFrame(trail)[["agent", "action", "outcome"]]
    st.table(trail_df)

    # --- Timings breakdown ---
    st.subheader("⏱️ Stage Timings")
    timings = result["timings"]
    timing_df = pd.DataFrame(
        [{"stage": k.replace("_sec", ""), "milliseconds": v * 1000} for k, v in timings.items() if k != "total_sec"]
    )
    if not timing_df.empty:
        st.bar_chart(timing_df.set_index("stage"))
else:
    st.info("👈 Select an alert in the sidebar and click **Run through pipeline** to see it processed live.")

st.divider()
with st.expander("ℹ️ About this project"):
    st.markdown("""
    - **Dataset:** NSL-KDD (public academic benchmark for network intrusion detection)
    - **Triage Agent:** Random Forest classifier, real measured accuracy ~74-75% on held-out test data
    - **Known limitation:** r2l and u2r attack recall is very low — a documented property of this benchmark's harder test set (novel attack variants not seen in training). See the confusion matrix in `docs/confusion_matrix.png`.
    - **Guardrails:** tiered human-approval gates, rate limiting, rollback on rejection — all tested in `tests/test_guardrails.py`, not just designed.
    - **What's mocked:** human approval response, real firewall/IAM execution, live threat intel API calls.
    - Full architecture reasoning: `docs/ARCHITECTURE_DECISIONS.md`
    """)
