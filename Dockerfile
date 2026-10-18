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

# Build identification, captured on the host by scripts/build-env.sh. Declared after
# the dependency layers so a new commit does not invalidate the pip cache.
ARG GIT_COMMIT
ARG BUILD_TIME
ENV GIT_COMMIT=$GIT_COMMIT BUILD_TIME=$BUILD_TIME
LABEL org.opencontainers.image.revision=$GIT_COMMIT \
      org.opencontainers.image.created=$BUILD_TIME

EXPOSE 8000

# Trust the reverse proxy path used on this host so generated URLs keep HTTPS.
CMD ["python", "-m", "app.server"]
