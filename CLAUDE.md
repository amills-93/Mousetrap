# CLAUDE.md

Mousetrap: behavioral-biometric step-up auth layer demoed on a fictional carrier portal ("Nimbus Mobile"). HackUTD 2026.

- `ARCHITECTURE.md` is the source of truth for design, contracts, and schemas. `IMPLEMENTATION_PLAN.md` is the stage-by-stage build order. Read the relevant sections before changing behavior; do not start a stage until the previous stage's "Done when" checks pass.
- Keep the codebase small and readable. Hackathon scope: prefer the simplest thing that satisfies the spec.

## Non-negotiables (from ARCHITECTURE.md §2)

1. Browser collects, server decides. No trust decisions on the client.
2. The client never names the user; resolve user/session server-side from the Better Auth cookie.
3. Never capture `KeyboardEvent.key` or input values. Timing, motion, coarse key class only.
4. Missing telemetry on a sensitive action = high risk.
5. Templates update only after successful step-up.

Also: no real carrier branding, no real personal data (555 numbers, fake ICCIDs/account numbers). Never install or import the unscoped `mousetrap` npm package; the collector is `@mousetrap-auth/collector`.

## Layout

- `apps/web` — Nuxt 3 + Tailwind + Prisma + Better Auth (pnpm workspace member)
- `packages/collector` — zero-dependency TS collector SDK (pnpm workspace member)
- `services/ml` — FastAPI + scikit-learn (Python 3.12; runs in Docker, local system Python may be older)
- `docker-compose.yml` — postgres, web, ml (caddy added in Stage 8)

## Commands

- Full stack: `cp .env.example .env && docker compose up --build`
- Web dev on host: `pnpm install && pnpm --filter web dev` (needs Postgres; `docker compose up postgres`)
- Prisma: `pnpm --filter web prisma migrate dev` (host) — DATABASE_URL must point to `localhost:5432` when run outside Docker
- Seed demo users (idempotent; prints TOTP QR codes): `docker compose run --rm seed`
- Regenerate Better Auth models after changing plugins: `cd apps/web && npx auth@1.7.18 generate --config server/lib/auth.ts --output prisma/schema.prisma --yes`, then add a migration
- ML health: `docker compose exec web wget -qO- http://ml:8000/healthz`

## Git workflow

- Branches: `main` (release/demo), `staging` (pre-release integration), `dev` (active integration).
- Every feature/fix gets its own branch off `dev` (`feature/<name>`, `fix/<name>`, `docs/<name>`), merged back into `dev` via PR. Promote `dev` → `staging` → `main` via PRs.
- Within a branch, commit as you go: make multiple focused commits at logical checkpoints (e.g. schema + migration, server routes, UI, seed) rather than one large commit at the end.
- Commits and PRs are authored as the repo owner (repo-local git identity is set). Do not add Claude co-author trailers or "Generated with" footers.
- The owner approves and merges PRs; do not merge them yourself.
