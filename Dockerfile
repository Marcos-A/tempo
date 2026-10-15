# Lightweight Python image is enough for FastAPI + SQLite and keeps rebuilds fast.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Pango and HarfBuzz are the system libraries WeasyPrint needs for the PDF export.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Trust the reverse proxy path used on this host so generated URLs keep HTTPS.
CMD ["python", "-m", "app.server"]
