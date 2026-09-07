"""
Slack Notifier
--------------
Sends a REAL HTTP POST to a Slack Incoming Webhook when a Tier 2/3 action
needs human approval. This is genuinely real -- not simulated -- once you
configure SLACK_WEBHOOK_URL. The approval DECISION itself is still typed in
the terminal (see Decision 014 in the architecture doc for why we scoped it
this way, not as full two-way Slack button approval).

Setup (you do this yourself -- see README "Slack Setup"):
  1. Go to https://api.slack.com/apps -> Create New App -> From scratch
  2. Enable "Incoming Webhooks", click "Add New Webhook to Workspace"
  3. Copy the webhook URL (looks like https://hooks.slack.com/services/T.../B.../xxx)
  4. Set it as an environment variable: SLACK_WEBHOOK_URL
"""
import os
import requests


class SlackNotifier:
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

    def notify_approval_needed(self, incident_id: str, action: str, tier: int, evidence: dict) -> bool:
        """
        Sends a real Slack message. Returns True if the message was sent
        successfully, False otherwise (e.g. not configured, or Slack rejected it).
        Never raises -- a notification failure should never crash the pipeline.
        """
        if not self.enabled:
            return False

        text = (
            f"*Security Incident Approval Needed*\n"
            f"*Incident:* `{incident_id}`\n"
            f"*Action requested:* `{action}` (Tier {tier})\n"
            f"*Severity:* {evidence.get('severity', 'unknown')}\n"
            f"*MITRE technique:* {evidence.get('mitre_technique', 'n/a')}\n"
            f"*Evidence:* {evidence.get('narrative', 'n/a')}\n\n"
            f"_Approve/reject in the SOC-Agent terminal._"
        )
        payload = {"text": text}

        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=5)
            return resp.status_code == 200
        except requests.RequestException as e:
            print(f"  [Slack notification failed: {e}]")
            return False

    def notify_outcome(self, incident_id: str, action: str, approved: bool) -> bool:
        if not self.enabled:
            return False
        status = "APPROVED" if approved else "REJECTED (rolled back)"
        text = f"*Incident `{incident_id}`:* `{action}` was {status}."
        try:
            resp = requests.post(self.webhook_url, json={"text": text}, timeout=5)
            return resp.status_code == 200
        except requests.RequestException as e:
            print(f"  [Slack notification failed: {e}]")
            return False
