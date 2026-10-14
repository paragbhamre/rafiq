FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 RAFIQ_RUNTIME_DIR=/app/runtime
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
COPY data ./data
COPY tests ./tests
COPY tools ./tools
COPY packs ./packs
# Fail the build (and keep the previous version live) if any test breaks: scenarios, the pack swap kit,
# and, when an official pack is present, the pack-independent checks run on that pack too
RUN python -m pytest -q -p no:cacheprovider \
 && if ls packs/official/*.csv >/dev/null 2>&1; then RAFIQ_PACK=official python -m pytest -q -p no:cacheprovider tests/test_any_pack.py; fi \
 && rm -rf /tmp/pytest-* && find /app -name __pycache__ -prune -exec rm -rf {} +
RUN useradd -m rafiq && mkdir -p /app/runtime && chown -R rafiq /app/runtime
USER rafiq
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
