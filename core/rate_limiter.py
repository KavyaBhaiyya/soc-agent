"""
Rate Limiter
------------
Circuit-breaker style guardrail: caps how many containment actions can fire
in a rolling 60-second window. This exists to catch a malfunctioning or
manipulated agent before it does something like isolating 100 hosts at once.
"""
import time
from collections import deque


class RateLimiter:
    """
    Cap chosen (5/minute, Decision 016): NSL-KDD's test set peaks at roughly
    2-3 severity-triggering records per second in the batch-eval stress test
    (Decision 012) -- i.e. real attack traffic can spike far above 5/min.
    5/min is intentionally conservative: it's meant to catch a MALFUNCTIONING
    or MANIPULATED agent taking many actions in a burst (the circuit-breaker's
    actual job, per Decision 010's guardrail design), not to size for peak
    legitimate throughput. A real deployment would tune this per-environment
    against expected legitimate alert volume -- this default favors "obviously
    safe" over "obviously sized for production load," which is the right
    default for a portfolio project's safety-critical component.

    OBSERVED INTERACTION (worth knowing, not a bug): after the Decision 016
    threshold tuning improved recall, demo.py's small 5-alert run can now hit
    this cap within itself (more alerts correctly flagged as threats -> more
    actions requested -> 5/min cap reached faster). Seeing
    "blocked_by_rate_limiter" on later demo.py alerts is the guardrail
    correctly doing its job on a low, deliberately conservative cap -- not a
    malfunction. A real deployment would tune this cap against real expected
    alert volume.
    """
    def __init__(self, max_actions_per_minute=5):
        self.max_actions = max_actions_per_minute
        self.timestamps = deque()

    def allow(self) -> bool:
        now = time.time()
        while self.timestamps and now - self.timestamps[0] > 60:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.max_actions:
            return False

        self.timestamps.append(now)
        return True
