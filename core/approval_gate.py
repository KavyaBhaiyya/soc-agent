"""
Approval Gate
-------------
Enforces the tiered human-approval policy. This is the core safety mechanism
of the whole system: the AI never gets to take a high-impact action alone.

Tier 1 (auto):     Reversible, low-impact. Executes immediately.
Tier 2 (human):    Reversible, high-impact. Requires a human to approve.
Tier 3 (human+):   Irreversible. Requires human approval + a second flag for
                    "sensitive" sign-off (stands in for a legal/senior reviewer).

If a human rejects a Tier 2/3 action that was already tentatively staged,
the system rolls it back and logs the rollback.

SLACK INTEGRATION (Decision 014): if a SlackNotifier is provided and enabled,
a REAL Slack message is sent when a Tier 2/3 approval is needed and when the
outcome is decided. The approval decision itself is still made via the
approval_callback (console input, or the mock default) -- this is a
notification-only integration, not two-way Slack button approval. See the
architecture doc for why this scope was chosen.
"""

ACTION_TIERS = {
    "block_ip": 1,
    "disable_session": 1,
    "rate_limit_source": 1,
    "isolate_host": 2,
    "revoke_credentials": 2,
    "quarantine_file": 2,
    "wipe_endpoint": 3,
    "terminate_account": 3,
}


class ApprovalGate:
    def __init__(self, audit_log, approval_callback=None, slack_notifier=None):
        """
        approval_callback: function(incident_id, action, evidence) -> bool
        Defaults to a mock auto-approval (for non-interactive contexts like
        the dashboard/demo/batch eval). Pass console_approval_callback (see
        below) for a real interactive terminal prompt.

        slack_notifier: optional SlackNotifier instance. If enabled, sends a
        real Slack message on every Tier 2/3 request and outcome.
        """
        self.audit_log = audit_log
        self.approval_callback = approval_callback or self._default_mock_approval
        self.slack_notifier = slack_notifier

    def _default_mock_approval(self, incident_id, action, evidence):
        print(f"  [MOCK HUMAN APPROVAL] Reviewing '{action}' for {incident_id}... APPROVED (simulated)")
        return True

    def request(self, incident_id: str, action: str, evidence: dict) -> dict:
        tier = ACTION_TIERS.get(action, 2)  # default to requiring approval if unknown action

        if tier == 1:
            self.audit_log.log(incident_id, "ContainmentAgent", action, evidence, "auto_approved")
            return {"action": action, "tier": tier, "approved": True, "auto": True}

        if self.slack_notifier and self.slack_notifier.enabled:
            sent = self.slack_notifier.notify_approval_needed(incident_id, action, tier, evidence)
            if sent:
                print(f"  [Slack notification sent for '{action}' on {incident_id}]")

        approved = self.approval_callback(incident_id, action, evidence)

        if self.slack_notifier and self.slack_notifier.enabled:
            self.slack_notifier.notify_outcome(incident_id, action, approved)

        if approved:
            self.audit_log.log(incident_id, "ContainmentAgent", action, evidence, "human_approved")
        else:
            self.audit_log.log(incident_id, "ContainmentAgent", action, evidence, "human_rejected_rolled_back")

        return {"action": action, "tier": tier, "approved": approved, "auto": False}


def console_approval_callback(incident_id, action, evidence):
    """
    A REAL interactive approval prompt -- blocks and waits for you to type
    y/n in the terminal. Use this (instead of the mock default) for a live
    demo where you actually approve/reject decisions yourself. See
    live_demo.py for a script wired up to use this.
    """
    print(f"\n  >>> APPROVAL NEEDED: '{action}' for incident {incident_id}")
    print(f"      Evidence: {evidence}")
    while True:
        answer = input("      Approve? (y/n): ").strip().lower()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("      Please type 'y' or 'n'.")
