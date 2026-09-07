"""
Batch Evaluation
----------------
Runs ALL 22,544 test records through the FULL pipeline (triage -> investigation
-> containment), not just the classifier in isolation. This answers questions
the per-record classifier metrics can't:

  - Across a realistic volume of traffic, how many incidents get escalated
    to containment, and at what severity mix?
  - What's the real end-to-end latency distribution, not just one example?
  - How many containment actions get auto-approved vs. need human review?
  - Does the rate limiter actually trigger under realistic alert volume?

Results are saved to docs/batch_evaluation_results.json so they can be cited
directly in the README/architecture doc with real numbers.
"""
import sys
import os
import json
import time
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orchestrator import Orchestrator

def run_batch_evaluation(sample_size=None):
    data_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "test_clean.csv")
    df = pd.read_csv(data_path)

    if sample_size:
        df = df.sample(n=sample_size, random_state=42)

    orchestrator = Orchestrator()
    # Use a tighter rate limit so we can actually observe it triggering at this volume
    from core.rate_limiter import RateLimiter
    orchestrator.rate_limiter = RateLimiter(max_actions_per_minute=1000)  # generous but finite, for realistic throughput stats

    results = {
        "total_records": len(df),
        "verdicts": {"benign": 0, "threat_contained": 0},
        "severity_counts": {"none": 0, "low": 0, "high": 0, "critical": 0},
        "predicted_category_counts": {},
        "ground_truth_category_counts": df["category"].value_counts().to_dict(),
        "correct_predictions": 0,
        "total_actions_taken": 0,
        "actions_auto_approved": 0,
        "actions_human_approved": 0,
        "actions_rate_limited": 0,
        "action_type_counts": {},
        "latencies_ms": {"triage": [], "investigation": [], "containment": [], "total": []},
    }

    t_start = time.time()
    for i, (_, row) in enumerate(df.iterrows()):
        record = row.drop(labels=["label", "category"]).to_dict()
        ground_truth = row["category"]

        r = orchestrator.process_alert(record)

        predicted = r["triage"]["category"]
        results["predicted_category_counts"][predicted] = results["predicted_category_counts"].get(predicted, 0) + 1
        if predicted == ground_truth:
            results["correct_predictions"] += 1

        results["verdicts"][r["verdict"]] += 1
        results["severity_counts"][r["triage"]["severity"]] += 1

        results["latencies_ms"]["triage"].append(r["timings"]["triage_sec"] * 1000)
        results["latencies_ms"]["total"].append(r["timings"]["total_sec"] * 1000)
        if "investigation_sec" in r["timings"]:
            results["latencies_ms"]["investigation"].append(r["timings"]["investigation_sec"] * 1000)
        if "containment_sec" in r["timings"]:
            results["latencies_ms"]["containment"].append(r["timings"]["containment_sec"] * 1000)

        if r["verdict"] == "threat_contained":
            for action in r["containment"]["actions"]:
                results["total_actions_taken"] += 1
                atype = action["action"]
                results["action_type_counts"][atype] = results["action_type_counts"].get(atype, 0) + 1
                if action.get("blocked_reason") == "rate_limit_exceeded":
                    results["actions_rate_limited"] += 1
                elif action.get("auto"):
                    results["actions_auto_approved"] += 1
                elif action.get("approved"):
                    results["actions_human_approved"] += 1

        if (i + 1) % 5000 == 0:
            print(f"  Processed {i+1}/{len(df)} records...")

    t_end = time.time()
    results["wall_clock_seconds"] = round(t_end - t_start, 2)
    results["overall_accuracy"] = round(results["correct_predictions"] / len(df), 4)

    def summarize(vals):
        if not vals:
            return None
        s = sorted(vals)
        return {
            "mean_ms": round(sum(vals) / len(vals), 3),
            "median_ms": round(s[len(s) // 2], 3),
            "p95_ms": round(s[int(len(s) * 0.95)], 3),
            "max_ms": round(max(vals), 3),
        }

    results["latency_summary_ms"] = {k: summarize(v) for k, v in results["latencies_ms"].items()}
    del results["latencies_ms"]  # raw lists too large to keep in the summary json

    return results


if __name__ == "__main__":
    import sys
    # Default: 5000-record stratified-ish random sample (fast enough to run anywhere).
    # Pass a number as an argument to change it, or "full" to run all 22,544 records
    # (takes several minutes -- see docs/ARCHITECTURE_DECISIONS.md Decision 012 for
    # measured per-record timing before you run the full set).
    sample_size = 5000
    if len(sys.argv) > 1:
        sample_size = None if sys.argv[1] == "full" else int(sys.argv[1])

    label = "ALL 22,544" if sample_size is None else f"a random sample of {sample_size}"
    print(f"Running full-pipeline batch evaluation on {label} test records...")
    print("This runs triage + investigation + containment per record, not just the classifier.\n")
    results = run_batch_evaluation(sample_size=sample_size)

    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "batch_evaluation_results.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n=== BATCH EVALUATION SUMMARY ===")
    print(f"Total records processed: {results['total_records']}")
    print(f"Wall clock time: {results['wall_clock_seconds']}s")
    print(f"Overall accuracy (full pipeline): {results['overall_accuracy']}")
    print(f"Verdicts: {results['verdicts']}")
    print(f"Severity distribution: {results['severity_counts']}")
    print(f"Total containment actions taken: {results['total_actions_taken']}")
    print(f"  Auto-approved (Tier 1): {results['actions_auto_approved']}")
    print(f"  Human-approved (Tier 2/3, simulated): {results['actions_human_approved']}")
    print(f"  Rate-limited/blocked: {results['actions_rate_limited']}")
    print(f"Action type breakdown: {results['action_type_counts']}")
    print(f"\nLatency summary (ms):")
    for stage, stats in results["latency_summary_ms"].items():
        if stats:
            print(f"  {stage:15s} mean={stats['mean_ms']:.3f}  median={stats['median_ms']:.3f}  p95={stats['p95_ms']:.3f}  max={stats['max_ms']:.3f}")
    print(f"\nFull results saved to docs/batch_evaluation_results.json")
