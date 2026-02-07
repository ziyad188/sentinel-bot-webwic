FROM python:3.11-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive

# ── System deps: only Playwright Chromium runtime libraries ──────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    fonts-noto-color-emoji \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# ── App user ─────────────────────────────────────────────────────────────
RUN useradd -m -s /bin/bash sentinel
USER sentinel
WORKDIR /home/sentinel

# ── Python deps ──────────────────────────────────────────────────────────
COPY --chown=sentinel:sentinel sentinel/requirements-sentinel.txt /home/sentinel/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt && \
    python -m playwright install chromium

# ── App code ─────────────────────────────────────────────────────────────
COPY --chown=sentinel:sentinel sentinel/ /home/sentinel/sentinel/
COPY --chown=sentinel:sentinel image/entrypoint_sentinel.sh /home/sentinel/entrypoint.sh
RUN chmod +x /home/sentinel/entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
