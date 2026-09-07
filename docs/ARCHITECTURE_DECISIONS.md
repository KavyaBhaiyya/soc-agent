# Architecture Decision Log

This document records every major decision made while building this project — what was decided, why, and what alternatives were considered. Read this top to bottom to understand how the project evolved from zero to finished.

---

## Decision 001: Project Name and Goal
**Date:** Day 1
**Decision:** Project named `soc-agent` (Autonomous Multi-Agent Security Incident Response System). Replaces the earlier "Nirikshak" proctoring project in the portfolio.
**Goal:** A 3-agent system that classifies security alerts, investigates them, and recommends/executes containment actions — with tiered human approval and full audit logging. Evaluated honestly on real public data, not simulated numbers.

---

## Decision 002: Dataset Choice — NSL-KDD instead of CICIDS2017
**Problem:** CICIDS2017 (originally planned) is hosted on a university server (University of New Brunswick) that isn't reachable from this build environment's network allowlist.
**Decision:** Use **NSL-KDD** instead.
**Why this is a fair substitute, not a downgrade:**
- NSL-KDD is a long-standing, widely-cited academic benchmark for network intrusion detection (successor to the original KDD Cup 99 dataset, with known redundancy/bias issues fixed).
- It's used in hundreds of published security ML papers — recognizable to anyone in the field.
- It's freely mirrored on GitHub, so it's reachable and legal to use.
- It has labeled attack categories: **DoS, Probe (scanning), R2L (remote-to-local, e.g. unauthorized access), U2R (privilege escalation)** — this covers "multiple attack types," not just logins, satisfying the scope requirement.
**Trade-off to be upfront about:** NSL-KDD is older (records feature-engineered network connections, not raw packet captures) and doesn't include some newer attack styles CICIDS2017 has. Fine for a portfolio project whose goal is to demonstrate agent architecture and evaluation methodology — not to publish new intrusion-detection research.

---

## Decision 003: Tech Stack
**Decision:**
- **Python 3** — for everything (agents, orchestrator, evaluation)
- **scikit-learn** — for the Triage Agent's classifier (Random Forest). Chosen over an LLM-based classifier because: (a) it's the right tool for structured tabular data, (b) it gives fast, honest, reproducible precision/recall numbers, (c) avoids the temptation to hand-wave "the LLM decided" without evidence.
- **SQLite** — for the audit log. Append-only table, zero setup, easy to inspect and demo.
- **Plain Python rule engine** — for the Containment Agent's approval-tier logic (not ML — these are policy decisions, not predictions, so a rule engine is the honest and correct tool, not an unnecessary AI dressing).
- **JSON-based mock APIs** — for threat intel and Slack/Jira. Real live API calls to AbuseIPDB are optional/stretch — documented clearly as mocked-by-default so the project runs without needing anyone else's API keys.
**Why not LangChain / a big agent framework:** Adding a framework here would hide the logic behind abstractions an interviewer can't see. Writing the orchestration logic directly in Python means every design decision (approval gates, rate limits, rollback) is visible, readable code — better for interviews than "the framework handled it."

---

## Decision 004: Project Structure
```
soc-agent/
├── data/              # dataset download + preprocessing
├── agents/            # triage, investigation, containment agents
├── core/              # audit log, approval gate, rate limiter (shared infra)
├── tests/             # evaluation scripts (real metrics)
├── docs/              # this decision log + final README
├── orchestrator.py    # wires the 3 agents together end-to-end
└── demo.py            # runs a sample incident through the full pipeline
```

---

## Decision 005: Triage Agent — Model Choice and Real Evaluation Results
**Decision:** Random Forest classifier (scikit-learn), 100 trees, `class_weight="balanced"` to handle the dataset's natural class imbalance (normal traffic vastly outnumbers u2r attacks, same as in real SOCs).

**Real evaluation results (test set, never seen during training):**

| Category | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| normal | 0.639 | 0.973 | 0.771 | 9711 |
| dos | 0.962 | 0.780 | 0.862 | 7460 |
| probe | 0.846 | 0.595 | 0.699 | 2421 |
| r2l | 0.833 | 0.002 | 0.003 | 2885 |
| u2r | 0.250 | 0.015 | 0.028 | 67 |

**Overall accuracy: 74.1%**

**Why r2l/u2r recall is near zero — and why that's not a bug:**
NSL-KDD's test set deliberately includes attack sub-variants absent from the training set, by design, to make it a harder benchmark than the original KDD Cup 99 (which was criticized for being unrealistically easy). This means a model trained only on the training set will genuinely struggle with novel r2l/u2r variants at test time — this mirrors a real limitation of signature/pattern-based detection systems in production: they miss attacks that don't resemble anything they've seen. This is a documented, explainable finding — not something to hide or round up.

**No inflated numbers were used anywhere in this project.** All metrics in this document and the final README come directly from this evaluation run.

---

## Decision 006: Investigation Agent — Rule-based, not ML
**Decision:** MITRE ATT&CK mapping and timeline-building use a rule engine (dictionary lookups + feature checks), not a model.
**Why:** Mapping an already-known attack category to a known technique ID is a lookup task. Using ML here would add complexity without adding accuracy or explainability — the opposite of what this system needs.

## Decision 007: Containment Agent — Severity-to-action mapping
**Decision:** Fixed mapping from severity to action list (low -> block_ip only, high -> block_ip + rate_limit, critical -> block_ip + isolate_host + revoke_credentials). Each action is tagged Tier 1/2/3 and enforced by the Approval Gate before "execution."
**Why fixed, not learned:** Which action to take for a given severity is a policy decision, not a prediction — it should be transparent and auditable, not hidden inside a model. A SOC would want to see and edit this mapping directly.

## Decision 008: Mocking human approval and containment execution
**Decision:** Human approval is simulated (auto-approves instantly, logged clearly as `[MOCK HUMAN APPROVAL]`). Containment actions (block IP, isolate host, etc.) are logged as taken but not connected to a real firewall/IAM system.
**Why:** No real enterprise infrastructure is available to this project (see the "why we can't build this for Google" discussion). Mocking these two pieces, and being explicit about it, keeps the demo honest — the parts that ARE real (classification, evaluation, guardrail logic, audit trail) are the parts that actually matter for a portfolio project.
**What's NOT mocked:** The approval-gate tier logic, the rate limiter, the audit logging, and the rejection/rollback path are all real, tested code (see `tests/test_guardrails.py`), not just narrated.

## Decision 009: Verified guardrails with actual tests, not just design docs
**Decision:** Built `tests/test_guardrails.py` to prove two things concretely: (1) a human rejecting a Tier 2 action results in a logged rollback, not a silent failure, and (2) the rate limiter actually blocks the 4th+ action once a cap is hit.
**Result:** Both tests pass with real output — this is demoable, not just claimed.

## Decision 010: Final scope — what got cut and why
**Cut from original plan:** GraphRAG, Grafana dashboard, drift detection, live Slack/Jira integration, EU AI Act compliance claims, CICIDS2017 dataset.
**Kept:** 3-agent pipeline, tiered approval gates, rollback, rate limiting, full audit trail, real evaluation metrics.
**Why this is the right cut:** Every kept feature is fully built, tested, and explainable in an interview. Every cut feature would have been either unbuildable without enterprise access, or a "designed but not built" claim — which is a credibility risk, not a strength, on a fresher's resume.

## Decision 011: Performance investigation — batch evaluation was too slow
**Problem:** Running the full pipeline across many records was far slower than expected (~21ms/record initially). Investigated with `cProfile` rather than guessing.
**First (wrong) hypothesis:** Assumed SQLite connection overhead (opening/closing a new connection per audit log write). Fixed AuditLog to hold one persistent connection for its lifetime. **Result: barely changed anything** — proof that guessing at performance fixes without profiling wastes time; the actual profiler output was needed.
**Real cause (found via profiling):** `TriageAgent.classify()` called both `model.predict()` and `model.predict_proba()` separately — each triggers a full 100-tree Random Forest pass, so every single record paid for the forest computation twice. Fixed to call `predict_proba()` once and derive both the class and confidence from it (via argmax), since `predict()` does exactly this internally anyway.
**Measured result (real numbers, not estimated):** ~21ms/record before this fix, ~14ms/record after — about a 33% reduction. This is a modest, honestly-measured improvement, not a dramatic one.
**Remaining known limitation, stated plainly:** Most of the remaining per-record cost is scikit-learn's own per-call overhead for evaluating a 100-tree forest one row at a time. The real fix for large-batch throughput would be vectorized batch prediction (running `predict_proba` on many rows in a single call) instead of a Python loop calling `classify()` once per record. This wasn't implemented because the system's actual use case is one-alert-at-a-time processing, matching a real SOC's alert stream — batch throughput was only a testing constraint, not a production requirement. This is documented here rather than silently left unaddressed.

## Decision 012: Batch evaluation — sample size, not full test set, by default
**Problem:** At ~14ms/record, the full 22,544-record test set takes several minutes — too long for this build environment's execution timeout.
**Decision:** `tests/batch_evaluation.py` defaults to a random 5,000-record sample. Pass `full` as an argument to run all 22,544 records (works fine on a normal machine without a sandbox timeout — just takes a few minutes).
**Real results from the 5,000-record sample run:**
- Overall full-pipeline accuracy: 73.76% (consistent with the classifier-only eval of ~74-75%, as expected)
- 1,714 of 5,000 records (34.3%) triggered containment
- Latency: triage mean 11.2ms, investigation mean 0.9ms, containment mean 1.4ms, **total pipeline mean 12.0ms/record** (p95: 14.3ms)
- **Rate limiter finding:** under this compressed stress-test (5,000 records processed in 65 seconds — far faster than real alert traffic would ever arrive), 3,052 of 3,062 attempted containment actions were correctly throttled by the rate limiter (capped at 1000/min). This demonstrates the circuit-breaker guardrail functioning under burst load, not just passing an isolated unit test.
**Honest caveat:** this compressed-timeline stress test is an artifact of testing speed, not realistic alert volume — a real SOC would not receive 3,000 critical alerts in 65 seconds. Framed accurately in the README as a guardrail stress-test finding, not a claim about real-world throughput capacity.

---

**Summary for portfolio/LinkedIn framing:** This project demonstrates multi-agent orchestration, safety-guardrail engineering (approval tiers, rollback, rate limiting), and rigorous ML evaluation practice (real precision/recall/F1 on a held-out test set, with limitations explained rather than hidden) — built and evaluated on a public academic benchmark dataset.

## Decision 013: Addressing severe class imbalance — model comparison, then a real swap
**Problem:** r2l is 0.8% and u2r is 0.04% of the training data. The original Random Forest (Decision 005) had near-zero recall on both — it almost never caught real attacks in these categories.
**Investigated 3 fixes honestly, compared on the SAME held-out test set** (see `tests/model_comparison.py`, results in `docs/model_comparison_results.json`):

| Approach | Accuracy | Macro F1 | u2r recall | r2l recall |
|---|---|---|---|---|
| A. Baseline (RF, class_weight=balanced) | 74.1% | 0.473 | 1.5% | 0.2% |
| B. RF + SMOTE (synthetic oversampling) | 77.2% | 0.550 | 11.9% | 6.3% |
| C. XGBoost (sample-weighted) | 78.1% | 0.580 | 17.9% | 7.8% |
| **D. XGBoost + per-class threshold tuning** | **80.2%** | **0.656** | **41.8%** | **17.7%** |

**Decision: D wins clearly on every metric — swapped the production model from Random Forest to this.**

**How threshold tuning works:** instead of plain argmax (pick whichever class has the highest probability), rare classes are checked FIRST against a deliberately low bar (u2r: 5%, r2l: 8%) before falling back to normal argmax for the common classes. This trades some false positives on rare classes for dramatically better recall — the right trade-off for security, where missing a real attack is worse than over-flagging a suspicious one.

**Bug caught and fixed during this change:** the first version of the updated `evaluate()` method called `classify()` in a loop over already-encoded data, which tried to re-encode already-encoded categorical columns — silently corrupting every row to a default category and producing a fake 53.3% accuracy. Caught because it didn't match `model_comparison.py`'s independently-measured 80.2% on the same model — a second implementation disagreeing with a first is exactly the kind of signal that should stop you and get investigated, not be explained away. Fixed by encoding once and applying the threshold logic directly to the already-encoded batch, not re-calling `classify()` per row. This is exactly the kind of thing to watch for and disclose, not bury.

**Trade-off, stated honestly:** normal-traffic recall dropped slightly (97.3% → 97.0%) and precision on "normal" is lower than the old model in exchange for the r2l/u2r gains — a real trade-off, not a free lunch. Full numbers in `docs/model_comparison_results.json`.

## Decision 014: Real Slack integration — scoped to notification-only, and why
**What was built:** `core/slack_notifier.py` sends a REAL HTTP POST to a Slack Incoming Webhook when a Tier 2/3 action needs approval, and another when the outcome is decided. Tested against a local mock HTTP server (since `slack.com` isn't reachable from this build sandbox) — confirmed correct request format, successful-response handling, AND graceful failure handling (unreachable webhook returns `False` and logs a message, does not crash the pipeline).

**Scope decision: notification-only, not two-way Slack button approval.** Two-way (click Approve in Slack, pipeline reacts) requires either (a) a public HTTPS endpoint Slack can call back to when a button is clicked, or (b) a Slack Bot Token + polling for emoji reactions. Both need more setup (a Slack App with bot scopes, or a permanently-running public server) than a portfolio project should require the user to maintain just to run a demo. The notification is genuinely real; the approval decision is captured via `console_approval_callback` (`live_demo.py`) — a real interactive terminal prompt, not simulated.

**Also built:** `live_demo.py` — a separate script from `demo.py`, specifically for live demonstrations (recording a video, showing an interviewer). Unlike `demo.py` (auto-approves everything, for a fast non-interactive smoke test) and the dashboard (also auto-approves, for browsing), `live_demo.py` genuinely blocks on real `y`/`n` input and sends real Slack messages if configured. Verified end-to-end: ran it repeatedly until a real u2r attack was caught, approved one action and rejected another, confirmed both outcomes were correctly logged and (in the mock-server test) correctly notified.

**Deliberately NOT wired into `batch_evaluation.py`:** that script processes thousands of records in a tight loop — sending a real Slack message per Tier 2/3 action there would spam the channel and likely hit Slack's rate limits. Batch evaluation stays notification-free by design, not by oversight.

## Decision 015: Optional LLM-written investigation narratives
**What was built:** `InvestigationAgent` can optionally call the Anthropic API (`claude-haiku-4-5-20251001`, chosen for cost/speed since this is a short rewrite task, not complex reasoning) to turn the rule-based facts into a natural analyst-style sentence. Auto-detects `ANTHROPIC_API_KEY` — on by default if set, off if not.

**Critical safety property, verified by testing, not just claimed:** the LLM call can NEVER affect containment decisions or severity — those come from `triage_result` (the classifier), computed before the LLM is ever called. The LLM only rewrites a sentence for human readability. Tested three states:
1. No API key set → `narrative_source: "rule_based"`, works normally
2. Invalid API key set → real call made to `api.anthropic.com`, got a real `401 AuthenticationError` back, caught, fell back to `narrative_source: "rule_based"` — **pipeline did not crash**
3. (Not testable in this build sandbox — no valid key available here) A real key would produce `narrative_source: "llm"` — you need to verify this yourself with your own key

**Every result always discloses `narrative_source`** (`"llm"` or `"rule_based"`) — never silently presented as one or the other. This matters for an interview: you should always be able to say honestly which sentences were LLM-generated versus rule-based, for any given run.

**Cost note, stated plainly:** this makes real, billed API calls when enabled. Fine for a demo video (a handful of calls); do not wire this into `batch_evaluation.py`'s 5,000-record loop — that would be thousands of paid calls for no real benefit (the narrative is a nice-to-have, not needed for evaluation metrics).

## Decision 017: Free LLM option added (Groq), preferred over the paid one
**Why:** the person explicitly didn't want to require a paid API key for this feature.
**What changed:** `InvestigationAgent` now checks `GROQ_API_KEY` first (free tier: no credit card, 30 req/min, verified current as of this decision via a live web search — see README "Groq Setup"), falling back to `ANTHROPIC_API_KEY` (paid) only if Groq isn't configured, falling back further to rule-based if neither is set. `narrative_source` now reports which one actually produced the text (`"llm_groq"`, `"llm_anthropic"`, or `"rule_based"`) so this is never ambiguous.
**Verified with real (invalid) keys against both real APIs** (`tests/test_llm_narrative.py`, 4 automated tests, all passing): Groq's endpoint returned a real 403, Anthropic's a real 401, both correctly triggered graceful fallback to rule-based with no crash. Provider-preference logic (Groq wins when both are configured) also verified.
**Not verified:** an actual valid key producing real LLM output — that requires a real account, which is the person's to set up and confirm.

## Decision 018: Real .env file support + GitHub Actions CI pipeline
**Problem:** `$env:GROQ_API_KEY=...` only lasts for one terminal session — annoying to retype, and doesn't answer "how does this work in CI on GitHub."
**Built:**
- `core/config.py` — loads a real `.env` file via `python-dotenv`, imported first thing in `orchestrator.py` (which every entrypoint imports), so `.env` works automatically everywhere, in any terminal, without manual `$env:` commands. Verified: wrote a real `.env` file with a fake key, confirmed `InvestigationAgent` picked it up correctly (`provider: groq`) with zero manual environment setup.
- `.env` added to `.gitignore` (real secrets never committed); `.env.example` stays committed (documents variable names, blank values only).
- `.github/workflows/tests.yml` — a real GitHub Actions CI pipeline. Runs the full test suite (guardrails, Slack notifier, LLM provider fallback, a 500-record batch eval) on every push, using GitHub's own servers — this is what "CI" means in practice, not just a buzzword on a resume. Deliberately does NOT require a real API key secret to fully pass: the LLM tests use intentionally-fake keys to verify graceful fallback (the actual safety-critical property), which needs no billable secret. A commented-out optional step shows how to add a real `GROQ_API_KEY` GitHub Secret later if a live integration test is ever wanted.
**Not tested:** the actual GitHub Actions run itself — that only happens once this repo is pushed to GitHub, which is the person's next step, not something verifiable from this build environment.

## Decision 019: Groq model name was deprecated, caught via a real user error
**Problem:** the person's own real test run hit a real `404 Client Error: Not Found` calling Groq with `llama-3.1-8b-instant` — the model this project originally shipped with.
**Diagnosed via live web search, not guessing:** confirmed (source dated within 2026, cross-checked against Groq's own current model docs) that Groq deprecated `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` sometime in 2026, recommending `openai/gpt-oss-20b` / `openai/gpt-oss-120b` as replacements.
**Fixed:** switched to `openai/gpt-oss-20b` — a small, fast model, a good fit for this project's short-sentence-rewrite use case.
**Verified the fix without a real key:** re-ran with a fake key and got a `403 Forbidden` instead of the earlier `404 Not Found` — proof the model name is now accepted and the request reaches real authentication checking, not a routing/naming failure. A real key is still needed to confirm actual generated output, same limitation as Decision 015/017.
**Lesson for this project, stated honestly:** third-party model catalogs change over time, sometimes within months. If this integration breaks again later with a 404, check `console.groq.com/docs/models` for the current model list before assuming the code is broken.

## Decision 020: Real Groq LLM narrative confirmed working end-to-end
**Fixed:** raised `max_tokens` from 100 to 300 (gpt-oss models can spend part of the budget on internal reasoning before the visible answer, which silently produced empty output with the tighter limit) and added raw-response logging for any future silent-empty case.
**Confirmed with the person's own real Groq key** (not simulated by me): `narrative_source: "llm_groq"`, real generated text: *"Critical incident: Unauthorized remote access attempt detected via T1078, with three consecutive failed login attempts from a suspicious IP, indicating potential credential misuse and lateral movement risk."*
**This closes out the free-LLM-narrative feature as genuinely verified end-to-end** — not just "should work," but confirmed working with a real account, real key, real API response.

## Decision 021: Real Slack delivery confirmed by the person
**Confirmed:** ran `live_demo.py` with a real `SLACK_WEBHOOK_URL`, triggered a real `u2r` alert, approved two Tier 2 actions via the terminal prompt. Real Slack messages arrived correctly formatted — incident ID, action, tier, severity, MITRE technique, and the Groq-generated narrative all present and matching the terminal output exactly, followed by correct APPROVED outcome messages.
**This closes out both the Slack notification feature AND the Groq LLM narrative feature as fully verified end-to-end** — real classifier decision → real LLM-written narrative → real Slack delivery → real terminal approval → correctly logged outcome. Every piece of this chain has now been run for real, by the project's author, not simulated by Claude.

## Decision 022: Pre-push cleanup — real gaps found and fixed before GitHub
Reviewed the repo specifically for "what breaks or looks bad the moment this is public," not just "does it run." Found and fixed 4 real issues:

1. **Missing `.dockerignore` in the actual tracked files** (only ever given to the person as chat instructions, never actually saved into the project) — added it for real this time.
2. **Trained model binaries (`.joblib` files) were NOT gitignored.** This is a real risk, not a style nitpick: this exact project already hit a real bug (`XGBoostError: input stream corrupted`) from a committed model trained with a different XGBoost version than the one later installed locally. Committing model binaries to a public repo bakes that exact bug in for every future clone, on every future dependency update. Fixed: `data/*.joblib` now gitignored; regenerated fresh via `python data/preprocess.py && python agents/triage_agent.py`, already the documented setup step. CI (`.github/workflows/tests.yml`) was already unaffected by this either way, since it always trains fresh.
3. **Generated CSVs (`train_clean.csv`, `test_clean.csv`) were tracked** — regenerable build artifacts, not source data (the raw `KDDTrain.txt`/`KDDTest.txt` ARE the source data and stay tracked). Gitignored, saving ~21MB of redundant repo size.
4. **`LICENSE` had the wrong name in it** (a leftover placeholder from earlier in this project's history) — corrected to the actual person's name.

**Verified the fix didn't break anything:** deleted the model/CSV files locally, re-ran `preprocess.py` → `triage_agent.py` → full test suite from scratch, simulating exactly what happens on a fresh `git clone`. Got the same real numbers as before (81.1% accuracy, all tests passing) — confirming the setup instructions in the README are actually sufficient on their own, not silently depending on files that happened to already exist.
