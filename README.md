# Mousetrap
Heuristic Behavioral Biometrics for Sensitive Web Interfaces

Behavioral-biometric step-up auth layer, demoed on a fictional carrier portal ("Nimbus Mobile"). See [ARCHITECTURE.md](ARCHITECTURE.md) and [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

## Quick start

```sh
cp .env.example .env
docker compose up --build
```

- Portal: http://localhost:3000 (shows DB and ML health)
- ML health from inside the network: `docker compose exec web node -e "fetch('http://ml:8000/healthz').then(r=>r.text()).then(console.log)"`

## Host development

```sh
pnpm install
docker compose up -d postgres
DATABASE_URL=postgresql://mousetrap:mousetrap@localhost:5432/mousetrap pnpm --filter web prisma migrate dev
DATABASE_URL=postgresql://mousetrap:mousetrap@localhost:5432/mousetrap pnpm dev
```

## Layout

- `apps/web`: Nuxt 3 + Tailwind + Prisma (+ Better Auth from Stage 2)
- `packages/collector`: `@mousetrap-auth/collector`, zero-dependency telemetry SDK
- `services/ml`: FastAPI + scikit-learn scoring service (internal only)
