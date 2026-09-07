"""
Investigation Agent
--------------------
Job: Given a triaged alert (already classified as a threat), build a short
attack narrative and map it to a known MITRE ATT&CK technique.

MITRE mapping is rule-based (not ML) -- lookup task, not prediction, Decision 003.
The NARRATIVE has an optional LLM upgrade (Decision 015, extended in Decision 017):
prefers GROQ_API_KEY (FREE tier -- no credit card, see README) over
ANTHROPIC_API_KEY (paid) if both are set. Falls back to the rule-based
narrative if neither is set or the call fails for any reason -- this NEVER
breaks the pipeline, since it's a presentation enhancement, not a decision
input. Containment decisions are made from triage_result/severity, computed
before this is ever called -- an LLM error can't cause a wrong containment action.
"""
import os
import requests

ATTACK_TECHNIQUE_MAP = {
    "dos": {
        "technique_id": "T1498",
        "technique_name": "Network Denial of Service",
        "narrative": "High-volume traffic pattern consistent with a denial-of-service attempt against the target host, aiming to exhaust resources or bandwidth."
    },
    "probe": {
        "technique_id": "T1595",
        "technique_name": "Active Scanning",
        "narrative": "Sequential connection attempts across multiple ports/services consistent with reconnaissance scanning ahead of a targeted attack."
    },
    "r2l": {
        "technique_id": "T1078",
        "technique_name": "Valid Accounts / Unauthorized Remote Access",
        "narrative": "Remote connection pattern consistent with an attacker attempting to gain unauthorized access using stolen or guessed credentials."
    },
    "u2r": {
        "technique_id": "T1068",
        "technique_name": "Exploitation for Privilege Escalation",
        "narrative": "Local activity pattern consistent with an attempt to escalate privileges after initial access was gained."
    },
}


class InvestigationAgent:
    def __init__(self, use_llm=None):
        """
        Provider preference (Decision 017): GROQ_API_KEY (free) checked first,
        ANTHROPIC_API_KEY (paid) as a fallback if Groq isn't configured. Set
        either, both, or neither -- neither means rule-based narratives only,
        which is a fully complete, honest mode, not a degraded one.
        """
        self.groq_key = os.environ.get("GROQ_API_KEY")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self.provider = "groq" if self.groq_key else ("anthropic" if self.anthropic_key else None)
        self.use_llm = use_llm if use_llm is not None else bool(self.provider)
        self._anthropic_client = None

    def investigate(self, record: dict, triage_result: dict) -> dict:
        category = triage_result["category"]

        if category == "normal":
            return {"skipped": True, "reason": "Triage classified as normal traffic; no investigation needed."}

        technique = ATTACK_TECHNIQUE_MAP.get(category, {
            "technique_id": "UNKNOWN",
            "technique_name": "Unmapped",
            "narrative": "Attack category recognized but no ATT&CK mapping defined."
        })

        timeline = self._build_timeline(record, category)
        narrative = technique["narrative"]
        narrative_source = "rule_based"

        if self.use_llm:
            llm_narrative = self._try_llm_narrative(category, technique, timeline, triage_result)
            if llm_narrative:
                narrative = llm_narrative
                narrative_source = f"llm_{self.provider}"  # e.g. "llm_groq" or "llm_anthropic" -- always disclosed

        return {
            "category": category,
            "mitre_technique_id": technique["technique_id"],
            "mitre_technique_name": technique["technique_name"],
            "narrative": narrative,
            "narrative_source": narrative_source,
            "timeline": timeline,
            "asset": {
                "protocol": record.get("protocol_type"),
                "service": record.get("service"),
                "src_bytes": record.get("src_bytes"),
                "dst_bytes": record.get("dst_bytes"),
            }
        }

    def _build_prompt(self, category, technique, timeline, triage_result):
        return (
            f"You are a SOC analyst writing a one-sentence incident summary. "
            f"Attack category: {category}. MITRE technique: {technique['technique_id']} "
            f"({technique['technique_name']}). Severity: {triage_result['severity']}. "
            f"Observed signals: {'; '.join(timeline)}. "
            f"Write ONE concise, professional sentence (max 35 words) an analyst "
            f"would read in an incident ticket. No preamble, just the sentence."
        )

    def _try_llm_narrative(self, category, technique, timeline, triage_result):
        """
        Returns an LLM-written narrative, or None on ANY failure. Never raises.
        """
        prompt = self._build_prompt(category, technique, timeline, triage_result)
        try:
            if self.provider == "groq":
                return self._call_groq(prompt)
            elif self.provider == "anthropic":
                return self._call_anthropic(prompt)
        except Exception as e:
            print(f"  [LLM narrative failed ({self.provider}), using rule-based fallback: {type(e).__name__}: {e}]")
            return None

    def _call_groq(self, prompt):
        """
        Groq's API is OpenAI-compatible -- a plain REST call, no special SDK
        needed. Free tier: no credit card, 30 req/min. Get a key at
        console.groq.com (see README "Groq Setup").

        max_tokens raised to 300 (Decision 020): gpt-oss models can spend part
        of the token budget on internal reasoning before writing the final
        answer -- 100 was too tight and silently produced empty output with
        no error, which is worse than a visible failure. If content is STILL
        empty, the raw response is printed so the real cause is visible
        instead of a silent, unexplained fallback.
        """
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"},
            json={
                "model": "openai/gpt-oss-20b",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
            },
            timeout=8.0,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        if not text:
            print(f"  [Groq call succeeded but returned empty content -- raw response: {data}]")
            return None
        return text

    def _call_anthropic(self, prompt):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_key)
        response = self._anthropic_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
            timeout=8.0,
        )
        text = response.content[0].text.strip()
        return text if text else None

    def _build_timeline(self, record: dict, category: str) -> list:
        events = []
        if record.get("num_failed_logins", 0) and record["num_failed_logins"] > 0:
            events.append(f"{int(record['num_failed_logins'])} failed login attempt(s) observed")
        if record.get("logged_in", 0) == 1:
            events.append("Successful login/session established")
        if record.get("num_compromised", 0) and record["num_compromised"] > 0:
            events.append(f"{int(record['num_compromised'])} compromised-state indicator(s) detected")
        if record.get("root_shell", 0) == 1:
            events.append("Root shell obtained")
        if record.get("num_file_creations", 0) and record["num_file_creations"] > 0:
            events.append(f"{int(record['num_file_creations'])} file creation event(s)")
        if record.get("count", 0) and record["count"] > 50:
            events.append(f"High connection count to same host ({int(record['count'])}) -- scanning-like behavior")

        if not events:
            events.append(f"Connection pattern flagged as '{category}' by classifier; no additional granular signals in this record.")

        return events
