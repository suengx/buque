ARG DOCKER_REGISTRY_PREFIX=
ARG DEBIAN_APT_MIRROR=
ARG NPM_REGISTRY=

FROM ${DOCKER_REGISTRY_PREFIX}node:22-bookworm-slim AS build

COPY docker/setup-apt-mirror.sh /tmp/setup-apt-mirror.sh

RUN DEBIAN_APT_MIRROR="$DEBIAN_APT_MIRROR" sh /tmp/setup-apt-mirror.sh \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npm ci

COPY . .

ARG VITE_API_BASE_URL
ARG VITE_GOOGLE_CLIENT_ID
ARG VITE_AUTH_PASSWORD_ENABLED

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID \
    VITE_AUTH_PASSWORD_ENABLED=$VITE_AUTH_PASSWORD_ENABLED

RUN npm run build

ARG DOCKER_REGISTRY_PREFIX=
ARG DEBIAN_APT_MIRROR=
ARG NPM_REGISTRY=
FROM ${DOCKER_REGISTRY_PREFIX}node:22-bookworm-slim

COPY docker/setup-apt-mirror.sh /tmp/setup-apt-mirror.sh

RUN DEBIAN_APT_MIRROR="$DEBIAN_APT_MIRROR" sh /tmp/setup-apt-mirror.sh \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY package.json package-lock.json ./
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npm ci --omit=dev

COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["node", "dist/server/server.js"]
