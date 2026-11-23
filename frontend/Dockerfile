# VigilOps web image: production React build served by Caddy, which also
# reverse-proxies /api to the backend.
# Build context: repository root  ->  docker build -f frontend/Dockerfile .
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM caddy:2-alpine
COPY reverse-proxy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv/www
EXPOSE 80 443
