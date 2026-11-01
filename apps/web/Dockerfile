# syntax=docker/dockerfile:1
# Build context is the repository root, because the app imports packages/api-types.
FROM node:24-alpine AS deps
WORKDIR /repo/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:24-alpine AS build
WORKDIR /repo/apps/web
COPY --from=deps /repo/apps/web/node_modules ./node_modules
COPY apps/web ./
COPY packages /repo/packages
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_TRACE_ROOT=/repo
RUN npm run build

FROM node:24-alpine AS production
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /repo/apps/web/.next/standalone ./
COPY --from=build /repo/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /repo/apps/web/public ./apps/web/public
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
