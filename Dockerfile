FROM node:22-bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends python3 python3-venv python3-pip \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY agent/requirements.txt ./agent/requirements.txt
RUN python3 -m venv /app/agent/.venv \
  && /app/agent/.venv/bin/pip install --no-cache-dir -r agent/requirements.txt

COPY server.mjs ./
COPY public ./public
COPY agent ./agent
COPY scripts/start-prod.sh ./scripts/start-prod.sh
RUN chmod +x ./scripts/start-prod.sh \
  && find agent -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
  && find agent -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

ENV NODE_ENV=production
ENV PORT=8080
ENV COPLAND_AGENT_HOST=127.0.0.1
ENV COPLAND_AGENT_PORT=5178
ENV COPLAND_AGENT_URL=http://127.0.0.1:5178
ENV COPLAND_SEED_DIR=/app/public/seed

EXPOSE 8080
CMD ["./scripts/start-prod.sh"]
