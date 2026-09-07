"""
Containment Agent
------------------
Job: Given triage + investigation results, decide what containment action(s)
to take, and route each one through the approval gate and rate limiter before
"executing" (execution is simulated -- this is a demo/portfolio project, not
connected to real firewalls or identity systems).
"""

SEVERITY_ACTION_MAP = {
    "low": ["block_ip"],
    "high": ["block_ip", "rate_limit_source"],
    "critical": ["block_ip", "isolate_host", "revoke_credentials"],
}


class ContainmentAgent:
    def __init__(self, approval_gate, rate_limiter, audit_log):
        self.approval_gate = approval_gate
        self.rate_limiter = rate_limiter
        self.audit_log = audit_log

    def contain(self, incident_id: str, triage_result: dict, investigation_result: dict) -> dict:
        severity = triage_result["severity"]
        actions_to_take = SEVERITY_ACTION_MAP.get(severity, [])
        results = []

        for action in actions_to_take:
            if not self.rate_limiter.allow():
                self.audit_log.log(
                    incident_id, "ContainmentAgent", action,
                    {"reason": "rate_limit_exceeded"}, "blocked_by_rate_limiter"
                )
                results.append({"action": action, "approved": False, "blocked_reason": "rate_limit_exceeded"})
                continue

            evidence = {
                "severity": severity,
                "mitre_technique": investigation_result.get("mitre_technique_id"),
                "narrative": investigation_result.get("narrative"),
            }
            outcome = self.approval_gate.request(incident_id, action, evidence)
            results.append(outcome)

        return {
            "incident_id": incident_id,
            "actions_attempted": len(actions_to_take),
            "actions": results,
        }
