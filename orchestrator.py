"""
Orchestrator
------------
Wires the Triage -> Investigation -> Containment pipeline together and times
each stage. This is the entry point that turns 3 separate agents into one
end-to-end incident response system.
"""
import time
import uuid

import core.config  # loads .env once, before any agent reads env vars -- must be first

from agents.triage_agent import TriageAgent
from agents.investigation_agent import InvestigationAgent
from agents.containment_agent import ContainmentAgent
from core.audit_log import AuditLog
from core.approval_gate import ApprovalGate
from core.rate_limiter import RateLimiter


class Orchestrator:
    def __init__(self):
        self.triage_agent = TriageAgent()
        self.triage_agent.load()
        self.investigation_agent = InvestigationAgent()
        self.audit_log = AuditLog()
        self.rate_limiter = RateLimiter(max_actions_per_minute=5)
        self.approval_gate = ApprovalGate(self.audit_log)
        self.containment_agent = ContainmentAgent(self.approval_gate, self.rate_limiter, self.audit_log)

    def process_alert(self, record: dict) -> dict:
        incident_id = str(uuid.uuid4())[:8]
        timings = {}
        t0 = time.time()

        # --- Stage 1: Triage ---
        triage_result = self.triage_agent.classify(record)
        self.audit_log.log(incident_id, "TriageAgent", "classify", triage_result, "completed")
        timings["triage_sec"] = round(time.time() - t0, 4)

        if not triage_result["is_threat"]:
            timings["total_sec"] = round(time.time() - t0, 4)
            return {
                "incident_id": incident_id,
                "verdict": "benign",
                "triage": triage_result,
                "timings": timings,
            }

        # --- Stage 2: Investigation ---
        t1 = time.time()
        investigation_result = self.investigation_agent.investigate(record, triage_result)
        self.audit_log.log(incident_id, "InvestigationAgent", "investigate", investigation_result, "completed")
        timings["investigation_sec"] = round(time.time() - t1, 4)

        # --- Stage 3: Containment ---
        t2 = time.time()
        containment_result = self.containment_agent.contain(incident_id, triage_result, investigation_result)
        timings["containment_sec"] = round(time.time() - t2, 4)

        timings["total_sec"] = round(time.time() - t0, 4)

        return {
            "incident_id": incident_id,
            "verdict": "threat_contained",
            "triage": triage_result,
            "investigation": investigation_result,
            "containment": containment_result,
            "timings": timings,
        }

    def get_audit_trail(self, incident_id: str):
        return self.audit_log.get_incident_trail(incident_id)
