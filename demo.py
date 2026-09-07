"""
Demo script: pulls a few real records from the test set (one of each attack
category, plus one normal) and runs each through the full pipeline, printing
the result and the audit trail.
"""
import json
import pandas as pd
from orchestrator import Orchestrator

def main():
    df = pd.read_csv("data/test_clean.csv")
    orchestrator = Orchestrator()

    # Grab one real example of each category from the actual test set
    samples = []
    for category in ["normal", "dos", "probe", "r2l", "u2r"]:
        row = df[df["category"] == category].iloc[0]
        samples.append((category, row))

    for expected_category, row in samples:
        record = row.drop(labels=["label", "category"]).to_dict()

        print(f"\n{'='*70}")
        print(f"Processing alert (ground truth category: {expected_category})")
        print('='*70)

        result = orchestrator.process_alert(record)

        print(f"Incident ID: {result['incident_id']}")
        print(f"Verdict: {result['verdict']}")
        print(f"Triage: {result['triage']}")

        if result["verdict"] == "threat_contained":
            print(f"\nInvestigation narrative: {result['investigation']['narrative']}")
            print(f"MITRE ATT&CK: {result['investigation']['mitre_technique_id']} - {result['investigation']['mitre_technique_name']}")
            print(f"Timeline: {result['investigation']['timeline']}")
            print(f"\nContainment actions:")
            for action in result["containment"]["actions"]:
                print(f"  - {action}")

        print(f"\nTimings: {result['timings']}")

        print(f"\nAudit trail for {result['incident_id']}:")
        trail = orchestrator.get_audit_trail(result["incident_id"])
        for event in trail:
            print(f"  [{event['agent']}] {event['action']} -> {event['outcome']}")

if __name__ == "__main__":
    main()
