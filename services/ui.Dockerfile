# UI service — Streamlit visualization. STRETCH (Phase 6) — build only once the
# coach logic is solid. Expects ui/app.py (not created yet). Build from repo root:
#   docker build -f services/ui.Dockerfile -t coach-ui .
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["streamlit", "run", "ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
