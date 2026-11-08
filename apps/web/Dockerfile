# Build context is the repo root (pnpm workspace).
FROM node:22-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends openssl && rm -rf /var/lib/apt/lists/*
RUN corepack enable
WORKDIR /repo

FROM base AS build
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/
COPY packages/collector/package.json packages/collector/
COPY apps/web/prisma apps/web/prisma
RUN pnpm install --frozen-lockfile --ignore-scripts
COPY . .
RUN pnpm --filter @mousetrap-auth/collector build \
 && pnpm --filter web exec prisma generate \
 && pnpm --filter web exec nuxt build

FROM base AS runtime
RUN npm install -g prisma@6.19.3
ENV NODE_ENV=production HOST=0.0.0.0 PORT=3000
WORKDIR /app
COPY --from=build /repo/apps/web/.output ./.output
COPY --from=build /repo/apps/web/prisma ./prisma
EXPOSE 3000
CMD ["sh", "-c", "prisma migrate deploy && node .output/server/index.mjs"]
