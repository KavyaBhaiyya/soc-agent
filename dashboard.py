"""
Streamlit dashboard: pick a real test-set record (or enter values manually),
run it through the full pipeline live, and see triage -> investigation ->
containment -> audit trail rendered visually instead of as terminal text.

VISUAL POLISH (Decision 023, revised): custom dark theme. Two elements that
resisted CSS overrides through several rounds of testing were replaced
outright instead of continuing to fight Streamlit/Vega-Lite internals with
!important overrides:
  - st.json() -> st.code(json.dumps(...)) : json viewer had a hardcoded white
    background not reachable via the data-testid selector in this Streamlit
    version.
  - st.bar_chart() -> a custom HTML/CSS bar : built-in charts render via
    Vega-Lite with their own hardcoded light background, which standard CSS
    overrides cannot reliably reach. A simple custom bar gives full color
    control and removes this class of bug entirely.
Purely cosmetic -- no change to orchestrator calls, data flow, or pipeline
logic anywhere below the styling block.

Run with: streamlit run dashboard.py
"""
import streamlit as st
import pandas as pd
import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()  # reads .env in this folder if present -- see .env.example

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from orchestrator import Orchestrator

st.set_page_config(page_title="SOC-Agent Dashboard", layout="wide", page_icon="🛡️")

# --- Visual polish: CSS only, no logic here ---
st.markdown("""
<style>
    .stApp { background-color: #0e1117; }
    h1, h2, h3 { color: #e6edf3 !important; }
    p, .stMarkdown, .stCaption { color: #c9d1d9; }

    [data-testid="stMetric"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 14px 16px;
    }
    [data-testid="stMetricLabel"] { color: #8b949e !important; }
    [data-testid="stMetricValue"] { color: #58a6ff !important; }

    .stButton>button {
        background-color: #238636;
        color: white;
        border-radius: 8px;
        border: none;
        font-weight: 600;
    }
    .stButton>button:hover { background-color: #2ea043; }

    [data-testid="stExpander"] {
        background-color: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
    }
    hr { border-color: #30363d !important; }

    /* Sidebar: broad, reliable overrides */
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    [data-testid="stSidebar"] * { color: #e6edf3 !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] { background-color: #0e1117 !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] { background-color: #ffffff !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] * { background-color: #ffffff !important; color: #000000 !important; }  
    /* Any inline code or <pre>/<code> block anywhere (used for the raw-record
       viewer below, replacing st.json which had an untouchable white background) */
    code, pre { background-color: #0d1117 !important; color: #79c0ff !important; }
    [data-testid="stSidebar"] code { background-color: #30363d; }

    /* Custom bar chart (replaces st.bar_chart -- see module docstring) */
    .custom-bar-row { display: flex; align-items: center; margin-bottom: 8px; }
    .custom-bar-label { width: 110px; color: #c9d1d9; font-size: 14px; }
    .custom-bar-track { flex-grow: 1; background-color: #0d1117; border-radius: 4px; height: 22px; position: relative; }
    .custom-bar-fill { background-color: #58a6ff; height: 100%; border-radius: 4px; }
    .custom-bar-value { margin-left: 10px; color: #8b949e; font-size: 13px; width: 80px; }
        [data-testid="stSidebar"] [data-baseweb="select"] input {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        opacity: 1 !important;
    }
</style>
""", unsafe_allow_html=True)


def render_bar_chart(stage_ms: dict):
    """Renders a simple horizontal bar per stage, fully our own colors --
    replaces st.bar_chart (see module docstring for why)."""
    if not stage_ms:
        return
    max_val = max(stage_ms.values()) or 1
    html = ""
    for stage, ms in stage_ms.items():
        pct = (ms / max_val) * 100
        html += f"""
        <div class="custom-bar-row">
            <div class="custom-bar-label">{stage}</div>
            <div class="custom-bar-track"><div class="custom-bar-fill" style="width:{pct:.1f}%"></div></div>
            <div class="custom-bar-value">{ms:.2f} ms</div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)


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
    category = st.sidebar.radio("Ground-truth category", sorted(df["category"].unique()))
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
    preview = {k: v for k, v in list(record.items())[:15]}
    st.code(json.dumps(preview, indent=2), language="json")

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
    badge = "✅ matches ground truth" if correct else f"⚠️ MISCLASSIFIED (real model limitation on '{ground_truth}' — see confusion matrix in docs/)"
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
        st.markdown(f"**Narrative** ({inv.get('narrative_source', 'rule_based')}): {inv['narrative']}")
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

    # --- Timings breakdown (custom bar, not st.bar_chart -- see docstring) ---
    st.subheader("⏱️ Stage Timings")
    timings = result["timings"]
    stage_ms = {k.replace("_sec", ""): v * 1000 for k, v in timings.items() if k != "total_sec"}
    render_bar_chart(stage_ms)
else:
    st.info("👈 Select an alert in the sidebar and click **Run through pipeline** to see it processed live.")

st.divider()
with st.expander("ℹ️ About this project"):
    st.markdown("""
    - **Dataset:** NSL-KDD (public academic benchmark for network intrusion detection)
    - **Triage Agent:** XGBoost classifier with per-class threshold tuning, real measured accuracy 81.1% on held-out test data (macro F1: 0.682)
    - **Known limitation:** r2l/u2r recall (24.8% / 46.3%) is much better than an earlier baseline model (0.2% / 1.5%) but still misses a majority of r2l attacks — a partially-fixable, documented property of this benchmark's harder test set. See `docs/confusion_matrix.png`.
    - **Guardrails:** tiered human-approval gates, rate limiting, rollback on rejection — all tested in `tests/test_guardrails.py`, not just designed.
    - **Real integrations:** Slack notifications and Groq/Anthropic LLM-written investigation narratives, both verified working end-to-end (see `docs/ARCHITECTURE_DECISIONS.md`, Decisions 020-021).
    - **What's still mocked:** human approval response (simulated in this dashboard; real in `live_demo.py`), real firewall/IAM execution, live threat intel API calls.
    - Full architecture reasoning: `docs/ARCHITECTURE_DECISIONS.md`
    """)