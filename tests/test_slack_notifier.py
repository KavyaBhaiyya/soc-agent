"""
Automated test for SlackNotifier's failure handling -- this was verified
manually earlier in the project's history (see ARCHITECTURE_DECISIONS.md
Decision 014), but a manual test isn't repeatable. This makes it a real,
re-runnable test using a local mock HTTP server (since slack.com isn't
reachable from a restricted network, and shouldn't be required just to run
the test suite).
"""
import sys
import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.slack_notifier import SlackNotifier


class MockSlackHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers["Content-Length"])
        body = self.rfile.read(length)
        MockSlackHandler.received.append(json.loads(body))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


def test_successful_notification():
    print("=== TEST: Slack notification succeeds against a valid endpoint ===")
    MockSlackHandler.received = []
    server = HTTPServer(("127.0.0.1", 8098), MockSlackHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    notifier = SlackNotifier(webhook_url="http://127.0.0.1:8098/mock")
    sent = notifier.notify_approval_needed("test1", "isolate_host", 2, {"severity": "critical"})
    server.shutdown()

    assert sent is True, "Expected successful send to return True"
    assert len(MockSlackHandler.received) == 1, "Expected exactly one message received"
    assert "test1" in MockSlackHandler.received[0]["text"], "Expected incident ID in message text"
    print("  PASSED\n")


def test_unreachable_webhook_fails_gracefully():
    print("=== TEST: Slack notification fails gracefully when unreachable ===")
    notifier = SlackNotifier(webhook_url="http://127.0.0.1:1/unreachable")
    result = notifier.notify_approval_needed("test2", "isolate_host", 2, {})
    assert result is False, "Expected False on unreachable webhook, not an exception"
    print("  PASSED (no exception raised, returned False as expected)\n")


def test_disabled_when_no_url():
    print("=== TEST: Notifier is disabled with no webhook URL configured ===")
    notifier = SlackNotifier(webhook_url=None)
    assert notifier.enabled is False
    result = notifier.notify_approval_needed("test3", "isolate_host", 2, {})
    assert result is False
    print("  PASSED\n")


if __name__ == "__main__":
    test_disabled_when_no_url()
    test_unreachable_webhook_fails_gracefully()
    test_successful_notification()
    print("All Slack notifier tests passed.")
