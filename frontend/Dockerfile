ARG DOCKER_REGISTRY_PREFIX=
ARG NPM_REGISTRY=

FROM ${DOCKER_REGISTRY_PREFIX}node:22-bookworm-slim AS build

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
ARG NPM_REGISTRY=
FROM ${DOCKER_REGISTRY_PREFIX}node:22-bookworm-slim

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000

COPY package.json package-lock.json ./
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npm ci --omit=dev

COPY --from=build /app/dist ./dist

EXPOSE 3000

CMD ["node", "dist/server/server.js"]
