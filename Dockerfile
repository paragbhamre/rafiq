FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RAFIQ_RUNTIME_DIR=/app/runtime
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY data ./data
COPY tests ./tests
# Fail the build (and keep the previous version live) if any scenario test breaks
RUN python -m pytest -q -p no:cacheprovider && find /app -name __pycache__ -prune -exec rm -rf {} +
RUN useradd -m rafiq && mkdir -p /app/runtime && chown -R rafiq /app/runtime
USER rafiq
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
