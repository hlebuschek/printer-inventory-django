# ── Stage 1: сборка Vue-фронтенда (Vite → static/dist) ──────────────────────
FROM node:22-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json vite.config.js ./
RUN npm ci
COPY frontend/ frontend/
RUN npm run build

# ── Stage 2: приложение + модифицированный glpi-agent ───────────────────────
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GLPI_PATH=/usr/bin

# Не запускать сервисы при установке deb-пакетов внутри контейнера
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d

# Актуальный официальный glpi-agent (+ task-network: glpi-netinventory/netdiscovery).
# Версию узнаём по редиректу releases/latest — без GitHub API (у него анонимный rate limit).
# Зафиксировать версию можно build-аргументом: --build-arg GLPI_AGENT_VERSION=1.19
ARG GLPI_AGENT_VERSION=latest
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && if [ "$GLPI_AGENT_VERSION" = "latest" ]; then \
         GLPI_AGENT_VERSION=$(curl -fsSLI -o /dev/null -w '%{url_effective}' \
             https://github.com/glpi-project/glpi-agent/releases/latest | sed 's|.*/tag/||'); \
       fi \
    && echo "glpi-agent version: $GLPI_AGENT_VERSION" \
    && mkdir /tmp/glpi-debs && cd /tmp/glpi-debs \
    && base="https://github.com/glpi-project/glpi-agent/releases/download/$GLPI_AGENT_VERSION" \
    && curl -fsSLO "$base/glpi-agent_${GLPI_AGENT_VERSION}-1_all.deb" \
    && curl -fsSLO "$base/glpi-agent-task-network_${GLPI_AGENT_VERSION}-1_all.deb" \
    && apt-get install -y --no-install-recommends ./glpi-agent_*.deb ./glpi-agent-task-network_*.deb \
    && cd / && rm -rf /tmp/glpi-debs /var/lib/apt/lists/* \
    && glpi-agent --version

# Наложить модифицированные MibSupport-модули (раздельные A3/A4 счётчики).
# apply-patches.sh уронит сборку, если апстрим изменил патчируемые файлы.
COPY docker/glpi-agent /opt/glpi-agent-patches
RUN sh /opt/glpi-agent-patches/apply-patches.sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /build/static/dist static/dist

# collectstatic не требует БД; SECRET_KEY — временный, только для команды
RUN SECRET_KEY=collectstatic-dummy python manage.py collectstatic --noinput

RUN chmod +x docker/entrypoint.sh
ENTRYPOINT ["docker/entrypoint.sh"]
CMD ["web"]
