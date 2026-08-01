FROM node:22-bookworm-slim

# MuseScore 3 + headless display for CLI SVG/MP3/timeline export.
# MuseScore 4 scores may not open; browser webmscore remains a fallback for older files.
RUN apt-get update && apt-get install -y --no-install-recommends \
    musescore3 \
    xvfb \
    unzip \
    ca-certificates \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY server.mjs ./
COPY public ./public

ENV NODE_ENV=production
ENV PORT=8080
ENV MSCORE_BIN=/usr/bin/mscore3
ENV QT_QPA_PLATFORM=offscreen

EXPOSE 8080
CMD ["node", "server.mjs"]
