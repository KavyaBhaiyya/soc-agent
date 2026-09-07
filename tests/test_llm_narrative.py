"""
Automated tests for InvestigationAgent's LLM provider selection and fallback.
Uses real (invalid) API keys against the REAL Groq and Anthropic endpoints --
both are reachable from this environment, so these test the real network
path's error handling, not just a mock. A valid key would produce
narrative_source starting with "llm_" instead -- not testable here without
paying for a real key, but the fallback path (the part that must never
break the pipeline) is fully covered.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _clear_llm_env():
    os.environ.pop("GROQ_API_KEY", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)


def test_no_keys_is_rule_based():
    _clear_llm_env()
    from agents.investigation_agent import InvestigationAgent
    agent = InvestigationAgent()
    assert agent.provider is None
    assert agent.use_llm is False
    r = agent.investigate({"num_failed_logins": 1}, {"category": "r2l", "severity": "critical"})
    assert r["narrative_source"] == "rule_based"
    print("test_no_keys_is_rule_based: PASSED")


def test_groq_preferred_when_both_set():
    _clear_llm_env()
    os.environ["GROQ_API_KEY"] = "fake-for-testing"
    os.environ["ANTHROPIC_API_KEY"] = "fake-for-testing"
    from agents.investigation_agent import InvestigationAgent
    agent = InvestigationAgent()
    assert agent.provider == "groq", "Groq (free) should be preferred when both keys are present"
    print("test_groq_preferred_when_both_set: PASSED")


def test_invalid_groq_key_falls_back_gracefully():
    _clear_llm_env()
    os.environ["GROQ_API_KEY"] = "fake-for-testing"
    from agents.investigation_agent import InvestigationAgent
    agent = InvestigationAgent()
    r = agent.investigate({"num_failed_logins": 1}, {"category": "r2l", "severity": "critical"})
    assert r["narrative_source"] == "rule_based", "Invalid key must degrade to rule_based, never crash"
    print("test_invalid_groq_key_falls_back_gracefully: PASSED")


def test_invalid_anthropic_key_falls_back_gracefully():
    _clear_llm_env()
    os.environ["ANTHROPIC_API_KEY"] = "fake-for-testing"
    from agents.investigation_agent import InvestigationAgent
    agent = InvestigationAgent()
    r = agent.investigate({"num_failed_logins": 1}, {"category": "r2l", "severity": "critical"})
    assert r["narrative_source"] == "rule_based"
    print("test_invalid_anthropic_key_falls_back_gracefully: PASSED")


if __name__ == "__main__":
    test_no_keys_is_rule_based()
    test_groq_preferred_when_both_set()
    test_invalid_groq_key_falls_back_gracefully()
    test_invalid_anthropic_key_falls_back_gracefully()
    print("\nAll LLM provider tests passed.")
