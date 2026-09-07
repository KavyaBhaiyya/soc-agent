# Runs the full data pipeline (preprocess + train) at build time, then
# serves the dashboard by default. Build once, run anywhere -- no local
# Python/venv setup needed (this exists specifically because of the real
# Windows Python-install pain hit earlier in this project -- see README).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python data/preprocess.py && python agents/triage_agent.py

EXPOSE 8501 8000

# Default: run the dashboard. Override at `docker run` time to run something
# else instead, e.g.:
#   docker run -p 8000:8000 soc-agent uvicorn api:app --host 0.0.0.0 --port 8000
CMD ["streamlit", "run", "dashboard.py", "--server.address=0.0.0.0"]
