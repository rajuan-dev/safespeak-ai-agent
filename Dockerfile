FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts
RUN python scripts/install_tessdata.py
RUN pip install .

RUN useradd --create-home --uid 10001 safespeak \
    && mkdir -p /app/storage \
    && chown -R safespeak:safespeak /app

USER safespeak
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
