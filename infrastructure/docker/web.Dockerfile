# Frontend Next.js. Construir desde la raíz del repositorio:
#   docker build -f infrastructure/docker/web.Dockerfile --target dev -t reclutamiento-web .
#
# NO VERIFICADO: esta imagen todavía no se ha construido (ver docs/estado_proyecto.md).

FROM node:22-slim AS deps
WORKDIR /srv/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

# Desarrollo: recarga en caliente; /api se reenvía a API_INTERNAL_URL.
FROM deps AS dev
COPY apps/web ./
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0"]

# Producción: /api lo atiende el proxy inverso, no Next.js.
FROM deps AS build
COPY apps/web ./
RUN npm run build

FROM node:22-slim AS production
ENV NODE_ENV=production
WORKDIR /srv/web
COPY --from=build /srv/web ./
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
