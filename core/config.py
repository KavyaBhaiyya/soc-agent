"""
Config Loader
-------------
Loads variables from a real .env file (if one exists) into the environment,
ONCE, so that GROQ_API_KEY / ANTHROPIC_API_KEY / SLACK_WEBHOOK_URL work the
same way in every terminal you open -- not just the one where you typed
`$env:GROQ_API_KEY=...`.

Import this at the top of any entrypoint (orchestrator.py, live_demo.py,
api.py, dashboard.py, demo.py) BEFORE anything reads os.environ. Safe to
import multiple times -- load_dotenv() is a no-op if already loaded.

.env itself is in .gitignore -- it must NEVER be committed to GitHub (it
holds real secrets). Only .env.example (with blank values) is committed.
For GitHub Actions / CI, secrets are provided a completely different way --
see .github/workflows/tests.yml and the README "CI / GitHub Actions Secrets"
section, not a committed .env file.
"""
from dotenv import load_dotenv

load_dotenv()
