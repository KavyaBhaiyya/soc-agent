"""
Demonstrates the two guardrails that don't show up in a normal happy-path demo:
1. A human REJECTING a Tier 2/3 action -> logged as rejected, action not taken.
2. The rate limiter BLOCKING an action once the per-minute cap is hit.
"""
import sys
sys.path.insert(0, "..")
from core.audit_log import AuditLog
from core.approval_gate import ApprovalGate
from core.rate_limiter import RateLimiter

def test_human_rejection():
    print("=== TEST: Human rejects a Tier 2 action ===")
    audit_log = AuditLog(db_path="test_audit.db")

    def always_reject(incident_id, action, evidence):
        print(f"  [MOCK HUMAN] Reviewing '{action}'... REJECTED")
        return False

    gate = ApprovalGate(audit_log, approval_callback=always_reject)
    result = gate.request("test-incident-1", "isolate_host", {"reason": "test"})

    assert result["approved"] is False
    assert result["tier"] == 2
    trail = audit_log.get_incident_trail("test-incident-1")
    assert trail[-1]["outcome"] == "human_rejected_rolled_back"
    print(f"  Result: {result}")
    print(f"  Audit trail confirms rollback logged: {trail[-1]['outcome']}")
    print("  PASSED\n")

def test_rate_limiter():
    print("=== TEST: Rate limiter blocks after cap ===")
    limiter = RateLimiter(max_actions_per_minute=3)

    allowed = [limiter.allow() for _ in range(5)]
    print(f"  5 rapid requests, cap=3 -> allowed sequence: {allowed}")
    assert allowed == [True, True, True, False, False]
    print("  PASSED\n")

if __name__ == "__main__":
    test_human_rejection()
    test_rate_limiter()
    print("All guardrail tests passed.")
