"""
Live Demo: unlike demo.py (which auto-approves everything for a quick
non-interactive run), this script uses REAL console approval prompts and
sends REAL Slack notifications (if SLACK_WEBHOOK_URL is set).

Use this one when you're recording a demo video or showing this live --
it's genuinely interactive, not simulated end-to-end.

Setup:
  export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."   (optional -- runs fine without it, just skips Slack)
  python live_demo.py
"""
import os
import sys
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # reads .env in this folder if present -- see .env.example

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents.triage_agent import TriageAgent
from agents.investigation_agent import InvestigationAgent
from agents.containment_agent import ContainmentAgent
from core.audit_log import AuditLog
from core.approval_gate import ApprovalGate, console_approval_callback
from core.rate_limiter import RateLimiter
from core.slack_notifier import SlackNotifier
from orchestrator import Orchestrator
import uuid
import time


def main():
    slack = SlackNotifier()
    if slack.enabled:
        print("Slack integration: ENABLED (SLACK_WEBHOOK_URL is set) -- real notifications will be sent.")
    else:
        print("Slack integration: disabled (no SLACK_WEBHOOK_URL set). Set it as an env var to enable.")
        print("See README 'Slack Setup' section for how to get a webhook URL.")

    orchestrator = Orchestrator()
    # Swap in the REAL console approval callback + Slack notifier for this live run
    orchestrator.approval_gate = ApprovalGate(
        orchestrator.audit_log,
        approval_callback=console_approval_callback,
        slack_notifier=slack,
    )
    orchestrator.containment_agent.approval_gate = orchestrator.approval_gate

    df = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "test_clean.csv"))

    print("\nPick a category to test: normal / dos / probe / r2l / u2r")
    category = input("Category: ").strip().lower()
    subset = df[df["category"] == category]
    if len(subset) == 0:
        print("Unknown category, defaulting to 'dos'")
        subset = df[df["category"] == "dos"]

    row = subset.sample(1).iloc[0]
    record = row.drop(labels=["label", "category"]).to_dict()

    print(f"\nProcessing alert (ground truth: {row['category']})...")
    t0 = time.time()
    result = orchestrator.process_alert(record)
    print(f"\nDone in {time.time()-t0:.1f}s (includes time you spent typing y/n, if any)")
    print(f"Verdict: {result['verdict']}")
    print(f"Triage: {result['triage']}")

    if result["verdict"] == "threat_contained":
        inv = result["investigation"]
        print(f"\nMITRE ATT&CK: {inv['mitre_technique_id']} - {inv['mitre_technique_name']}")
        print(f"Narrative source: {inv['narrative_source']}  <-- check this: 'llm_groq' means Groq wrote it, 'rule_based' means the key wasn't used")
        print(f"Narrative: {inv['narrative']}")
        print(f"\nContainment actions:")
        for action in result["containment"]["actions"]:
            print(f"  - {action}")


if __name__ == "__main__":
    main()
