# syntax=docker/dockerfile:1
FROM node:22-alpine AS builder
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1
COPY package.json tsconfig.json next.config.ts tailwind.config.ts postcss.config.mjs ./
COPY public ./public
COPY src ./src
RUN npm install --no-save --omit=optional --no-audit && \
    npm run build
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000
COPY --from=builder /app/package.json /app/next.config.ts /app/tsconfig.json ./
COPY --from=builder /app/.next/standalone ./.next/standalone
COPY --from=builder /app/public ./public
RUN adduser -D -u 10001 appuser
USER appuser
EXPOSE 3000
CMD ["node", ".next/standalone/server.js"]