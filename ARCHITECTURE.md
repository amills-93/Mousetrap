# Mousetrap: Behavioral Biometric Step-Up Auth Layer

Hackathon build spec (HackUTD 2026, ~21 hours). This document is the source of truth for Claude Code. Build in the phase order at the bottom. Keep the codebase small and readable.

## 1. Goal

A demo telecom account portal for a **fictional carrier, "Nimbus Mobile"** (original name, logo, and color palette; do not use any real carrier's branding). While a signed-in user interacts with the portal, a collector streams keystroke and mouse telemetry to a Python ML service that scores how closely the behavior matches the account owner. When the user attempts a sensitive action, the backend checks the live risk score and either allows it, demands TOTP step-up, or revokes the session and redirects to login.

Headline claim for judges: the collector is a framework-agnostic core with thin adapters, so the layer can sit in front of any web app.

## 2. Non-negotiable principles

1. **Browser collects, server decides.** The client never computes or reports a trust decision. All enforcement happens in Nuxt server routes.
2. **The client never names the user.** Telemetry is tied to user and session server-side from the Better Auth session cookie.
3. **Capture timing and motion, never content.** No key values, no field values. Key events record only timing plus a coarse key class (letter, digit, modifier, nav, backspace).
4. **Missing telemetry on a sensitive action is treated as high risk.**
5. **Templates are only updated after strong auth** (successful step-up), never from unverified sessions.

## 3. Tech stack

| Layer | Choice |
|---|---|
| Web app | Nuxt 3 (Vue 3, TypeScript, Nitro server routes), Tailwind CSS |
| Auth | Better Auth, self-hosted inside Nuxt server, plugins: `twoFactor`, `multiSession` |
| ORM / DB | Prisma + PostgreSQL 16 |
| ML service | Python 3.12, FastAPI, scikit-learn, numpy, pandas, joblib, uvicorn |
| Collector | TypeScript package, zero dependencies, ESM build |
| Local orchestration | Docker Compose (postgres, web, ml) |
| Hosting | See section 12 |

## 4. Repository layout

```
mousetrap/
├─ docker-compose.yml
├─ .env.example
├─ packages/
│  └─ collector/              # framework-agnostic SDK
│     ├─ src/core.ts          # listeners, buffering, batching, transport
│     ├─ src/schema.ts        # event schema v1 types
│     ├─ src/adapters/vue.ts  # Vue/Nuxt plugin adapter
│     ├─ src/adapters/vanilla.ts
│     └─ package.json
├─ apps/
│  └─ web/                    # Nuxt app
│     ├─ prisma/schema.prisma
│     ├─ prisma/seed.ts
│     ├─ server/
│     │  ├─ lib/auth.ts       # Better Auth instance
│     │  ├─ lib/prisma.ts
│     │  ├─ lib/ml.ts         # typed client for ML service
│     │  ├─ lib/policy.ts     # requireTrust(event, tier)
│     │  ├─ api/auth/[...all].ts
│     │  ├─ api/telemetry.post.ts
│     │  ├─ api/risk.get.ts
│     │  ├─ api/stepup/verify.post.ts
│     │  ├─ api/enroll/*.ts
│     │  └─ api/account/*.ts  # lines, billing, sim, security actions
│     ├─ plugins/collector.client.ts
│     ├─ composables/useAuth.ts
│     ├─ components/          # RiskMeter, AccountSwitcher, StepUpModal, etc.
│     └─ pages/
└─ services/
   └─ ml/
      ├─ app/main.py          # FastAPI routes
      ├─ app/features.py      # window -> feature vector
      ├─ app/model.py         # per-user IsolationForest, calibration
      ├─ app/scoring.py       # rolling EWMA risk per session
      ├─ app/schemas.py       # pydantic models mirroring schema v1
      ├─ models/              # persisted per-user models (volume)
      ├─ requirements.txt
      └─ Dockerfile
```

## 5. Request flows

### 5.1 Telemetry

```
Browser (collector) --POST /api/telemetry (cookie)--> Nuxt
Nuxt: resolve Better Auth session -> {userId, sessionId}
Nuxt --POST {ML_URL}/ingest (X-Internal-Key)--> ML service
ML: append events to session buffer -> build windows -> score -> update EWMA
```

- Collector flushes every 3 s or 200 events, whichever first, plus `navigator.sendBeacon` on `pagehide`.
- Each batch carries `seq` (monotonic per page load) and `pageId` (random UUID per load). Nuxt drops batches with non-increasing `seq` for a `pageId` (basic replay guard).
- Nuxt rejects telemetry with no valid session (401). Unauthenticated pages (login) do not collect.

### 5.2 Sensitive action

```
Browser --POST /api/account/sim-swap--> Nuxt
Nuxt: requireTrust(event, "critical")
  -> GET {ML_URL}/risk/{sessionId}
  -> policy decision
     allow    -> perform action
     step_up  -> 403 {action:"step_up", challengeId}
     deny     -> revoke session, 401 {action:"logout"}
Browser: on step_up show StepUpModal -> POST /api/stepup/verify -> retry original action
```

### 5.3 Step-up success

- Mark session `stepUpUntil = now + 5 min` (stored in `SessionTrust` table, keyed by Better Auth session id).
- Call `{ML_URL}/feedback` with `{userId, sessionId, label: "genuine"}`. ML may append the last N windows of this session to the user's training set and retrain asynchronously.
- Within the `stepUpUntil` window, `requireTrust` returns `allow` for tiers up to `critical`.

### 5.4 Step-up failure

- 3 failed TOTP attempts -> revoke session, write `RiskEvent(type: "stepup_failed")`, redirect to login.

## 6. Collector SDK (packages/collector)

Package name: `@mousetrap-auth/collector` (scoped; the unscoped `mousetrap` npm name belongs to an existing keyboard-shortcut library, so never install or import `mousetrap` itself).

### 6.1 Event schema v1

```ts
type KeyClass = "letter" | "digit" | "space" | "backspace" | "enter" | "modifier" | "nav" | "other";

type CollectorEvent =
  | { k: "kd"; t: number; kc: KeyClass; code_hash: number }  // keydown
  | { k: "ku"; t: number; kc: KeyClass; code_hash: number }  // keyup
  | { k: "mm"; t: number; x: number; y: number }             // mousemove, throttled
  | { k: "md"; t: number; x: number; y: number; b: number }  // mousedown
  | { k: "mu"; t: number; x: number; y: number; b: number }  // mouseup
  | { k: "wh"; t: number; dy: number }                       // wheel
  | { k: "fc"; t: number; role: string }                     // focus change: input role/type, never value
  | { k: "nv"; t: number; route: string };                   // route change

interface TelemetryBatch {
  v: 1;
  pageId: string;
  seq: number;
  vw: number; vh: number;     // viewport size for normalizing coordinates
  synthetic?: number;         // count of ignored untrusted events
  events: CollectorEvent[];
}
```

- `t` is `performance.now()` rounded to 0.1 ms.
- `code_hash` is a small stable hash of `KeyboardEvent.code` (not `key`), used only to pair keydown/keyup and compute digraph timing per physical key pair. Never send `key` or input values.
- Ignore synthetic events (`event.isTrusted === false`) but count them; send a `synthetic` counter in the batch for bot detection.

> Note: the tail of the `KeyClass` union and the `mm`/`fc` comments were truncated in the source PDF; `"nav" | "other"` and the comment text above are reconstructed from principle 3.

### 6.2 API

```ts
const c = createCollector({ endpoint: "/api/telemetry", flushMs: 3000, maxBatch: 200 });
c.start(); c.stop(); c.flush(); c.setRoute(path);
```

- Vue adapter: Nuxt client plugin that calls `start()` after auth, `stop()` on sign-out, and hooks `router.afterEach` to `setRoute`.
- Vanilla adapter: auto-start script tag for non-framework pages (used to prove modularity).

## 7. Nuxt app (apps/web)

### 7.1 Better Auth

`server/lib/auth.ts`:

```ts
import { betterAuth } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { twoFactor, multiSession } from "better-auth/plugins";
import { prisma } from "./prisma";

export const auth = betterAuth({
  database: prismaAdapter(prisma, { provider: "postgresql" }),
  emailAndPassword: { enabled: true },
  plugins: [
    twoFactor({ issuer: "Nimbus Mobile Demo" }),
    multiSession({ maximumSessions: 5 }),
  ],
});
```

- Handler: `server/api/auth/[...all].ts` returns `auth.handler(toWebRequest(event))`.
- Generate Better Auth tables into `schema.prisma` with the Better Auth CLI, then add app models below.
- Client: `createAuthClient` from `better-auth/vue` with `twoFactorClient()` and `multiSessionClient()`.
- **Multi-user / multi-session features to expose in UI:**
  - Account switcher in the header (multiSession: list device sessions, switch active, sign out one or all).
  - "Signed-in devices" page under Security: list sessions with user agent, IP, created time, current risk score; revoke individual sessions.
- **Step-up TOTP:** first try verifying with the Better Auth `twoFactor` plugin against an active session. If the plugin's verify endpoint only works during the sign-in flow, fall back to `otplib` verification against a separate per-user `stepUpSecret` stored in `SessionTrust`-adjacent table `StepUpFactor`. Seed users get known secrets and the seed script prints QR codes/otpauth URIs.

### 7.2 Prisma app models (in addition to Better Auth's generated models)

```prisma
model CustomerAccount {
  id            String  @id @default(cuid())
  userId        String  @unique
  accountNumber String  @unique   // fake, e.g. "NM-" + 9 digits
  portPin       String            // fake demo value
  autopay       Boolean @default(false)
  lines         Line[]
  bills         Bill[]
}

model Line {
  id         String          @id @default(cuid())
  accountId  String
  account    CustomerAccount @relation(fields: [accountId], references: [id])
  phone      String          // fake 555 numbers only
  nickname   String
  plan       String          // "Nimbus Unlimited", "Nimbus Essentials", ...
  simIccid   String          // fake
  deviceName String
  dataUsedGb Float           @default(0)
}

model Bill {
  id        String          @id @default(cuid())
  accountId String
  account   CustomerAccount @relation(fields: [accountId], references: [id])
  period    String
  amount    Decimal         @db.Decimal(10, 2)
  dueDate   DateTime
  paid      Boolean         @default(false)
}

model BiometricProfile {
  userId       String   @id
  status       String   // "none" | "enrolling" | "active"
  windowCount  Int      @default(0)
  modelVersion Int      @default(0)
  updatedAt    DateTime @updatedAt
}

model SessionTrust {
  sessionId    String    @id        // Better Auth session id
  userId       String
  stepUpUntil  DateTime?
  failedStepUp Int       @default(0)
  updatedAt    DateTime  @updatedAt
}

model StepUpFactor {
  userId String @id
  secret String              // demo only; fallback path
}

model RiskEvent {
  id        String   @id @default(cuid())
  userId    String
  sessionId String
  type      String   // "score" | "allow" | "step_up" | "deny" | "stepup_ok" | "stepup_failed"
  tier      String?
  risk      Float?
  route     String?
  createdAt DateTime @default(now())
  @@index([sessionId, createdAt])
}
```

All seeded data is fictional: 555 phone numbers, fake account numbers, fake ICCIDs.

### 7.3 Pages (Nimbus Mobile account portal)

| Route | Content | Sensitivity tier |
|---|---|---|
| `/login` | email + password, TOTP if prompted | n/a |
| `/` (Overview) | balance due, lines summary, data usage bars | `view` |
| `/lines` | per-line cards: plan, device, usage | `view` |
| `/lines/:id` | rename line, change plan | `standard` |
| `/billing` | bill history, pay bill, toggle autopay | pay/autopay: `elevated` |
| `/profile` | name, email, address | edit: `elevated` |
| `/security` | change password, port-out PIN reveal, signed-in devices | `critical` |
| `/security/sim` | SIM swap / eSIM transfer to new device | `critical` |
| `/security/authorized-users` | add authorized user | `critical` |
| `/enroll` | biometric enrollment flow | n/a |
| `/admin/risk` | demo-only live view of all sessions and scores | demo flag |

UI: Nuxt + Tailwind, original Nimbus brand (suggested palette: deep indigo `#2B2D7C` primary, cyan `#22C3E6` accent, neutral grays). Persistent **RiskMeter** widget in the corner (polls `/api/risk` every 2 s) showing score, tier thresholds, and current status. Toggle it off for a "production" view.

### 7.4 Policy (`server/lib/policy.ts`)

```ts
type Tier = "view" | "standard" | "elevated" | "critical";

const THRESHOLDS: Record<Tier, { stepUp: number; deny: number }> = {
  view:     { stepUp: 1.01, deny: 1.01 },   // never blocks
  standard: { stepUp: 0.75, deny: 0.95 },
  elevated: { stepUp: 0.55, deny: 0.90 },
  critical: { stepUp: 0.35, deny: 0.80 },
};
```

`requireTrust(event, tier)`:

1. Resolve session; if none, 401.
2. If `SessionTrust.stepUpUntil > now`, allow.
3. Fetch `/risk/{sessionId}` from ML (timeout 300 ms).
4. If ML unreachable or `windows < MIN_WINDOWS (3)`, treat risk as `0.6` for `elevated`/`critical` (forces step-up), `0` otherwise.
5. If user's `BiometricProfile.status !== "active"`, require step-up for `critical`, allow others.
6. Compare risk to thresholds; on `deny` call Better Auth to revoke the session.
7. Write a `RiskEvent` for every decision.

Thresholds are env-overridable (`POLICY_THRESHOLDS_JSON`) for live tuning during the demo.

## 8. ML service (services/ml)

### 8.1 Endpoints (all require `X-Internal-Key`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest` | `{userId, sessionId, batch}`; buffer, window, score |
| GET | `/risk/{sessionId}` | `{risk, windows, lastUpdated, components}` |
| POST | `/enroll/{userId}/start` | reset enrollment buffer |
| POST | `/enroll/{userId}/finish` | train model, return `{windowCount, ok}` |
| POST | `/feedback` | `{userId, sessionId, label}`; on `genuine`, add recent windows and retrain in background |
| GET | `/users/{userId}/status` | enrolled?, window count, model version |
| GET | `/healthz` | liveness |

During enrollment (`/enroll` page), `/ingest` routes that user's windows to the enrollment buffer instead of scoring.

### 8.2 Windowing

- Window = 5 s of events or 60 events, whichever first, sliding with 50% overlap.
- Discard windows with fewer than 15 events (idle).

### 8.3 Features (per window)

Keystroke (if ≥ 4 key pairs):

- dwell time: mean, std, median, p90
- flight time (keyup to next keydown): mean, std, median, p90
- digraph latency for top recurring pairs (by `code_hash` pair): mean
- backspace ratio, typing rate (keys/s)

Mouse (if ≥ 10 move points):

- speed: mean, std, p90 (coordinates normalized by viewport)
- acceleration: mean, std
- curvature / path straightness ratio (euclidean distance / path length) per movement segment
- angle change distribution: mean absolute, std
- pause count and mean pause duration (>150 ms gaps)
- click hold time (md to mu): mean, std
- wheel: scroll rate, direction changes

Missing modality features are imputed with the user's enrollment median, plus a binary `has_keys` / `has_mouse` flag.

Log every feature vector to `models/{userId}/features.parquet` for debugging and plotting.

### 8.4 Model

- Per-user `StandardScaler` + `IsolationForest(n_estimators=200, contamination="auto", random_state=42)` trained on enrollment windows (minimum 20 windows; target 40+).
- **Calibration:** at train time, compute decision scores on the training windows; store their empirical distribution. Map a new window's score to risk via its percentile (lower IF score = more anomalous): `risk = 1 - percentile_of_score_in_training_distribution`, clipped to [0, 1].
- Persist with joblib at `models/{userId}/model.joblib` plus `meta.json` (version, window count, feature list).
- Stretch: replace with a global embedding model (small 1D-CNN or GRU over event sequences, triplet loss) and score by cosine distance to a per-user template. Keep the same `/risk` contract so Nuxt does not change.

### 8.5 Session risk

- `risk_t = alpha * window_risk + (1 - alpha) * risk_{t-1}`, `alpha = 0.3`.
- Track in memory: `{sessionId: {risk, windows, lastUpdated, components:{keys, mouse}}}`. Expire after 30 min idle.
- Bot heuristics add to risk: `synthetic > 0` in batch (+0.3), mouse paths with near-zero curvature variance (+0.2), inter-key intervals with std < 5 ms over 20+ keys (+0.3).

## 9. Security notes (demo scope)

- ML service is not exposed publicly; only Nuxt calls it, with `X-Internal-Key`.
- CSRF: Better Auth defaults; telemetry endpoint accepts only same-origin `fetch` with JSON content type plus `sendBeacon` (text/plain JSON) from same origin.
- Rate limit `/api/telemetry` per session (e.g. 5 req/s).
- No real personal data. Seed users and data are fictional.
- Show a consent banner on `/enroll` explaining what is collected (timing and motion only) and that it is a demo.

## 10. Environment variables

```
DATABASE_URL=postgresql://mousetrap:mousetrap@postgres:5432/mousetrap
BETTER_AUTH_SECRET=...
BETTER_AUTH_URL=http://localhost:3000
ML_URL=http://ml:8000
ML_INTERNAL_KEY=...
POLICY_THRESHOLDS_JSON=
DEMO_MODE=true          # enables RiskMeter and /admin/risk
```

## 11. Seed data

Three users, each with a `CustomerAccount`, 2 to 4 lines, 6 months of bills, and a TOTP secret (printed by seed as otpauth URIs):

- `alex@nimbus.demo` / `Password123!`
- `jordan@nimbus.demo` / `Password123!`
- `sam@nimbus.demo` / `Password123!`

Each teammate enrolls as one of these users before the demo.

## 12. Hosting and platform choices

**Rule: everything runs from one `docker-compose.yml`.** Services: `postgres`, `web` (Nuxt, port 3000), `ml` (FastAPI, port 8000, internal only), plus `caddy` (port 443, automatic HTTPS, reverse proxy to `web`). Because the stack is portable, moving hosts is a `git pull && docker compose up -d`. Develop locally on laptops; deploy the same compose file to the demo host.

| Platform (credit) | Use | Notes |
|---|---|---|
| 639Cloud ($150) | **Primary demo host.** One Linux VM (4 vCPU / 8 GB is plenty) running the full compose stack. | IaaS VM; install Docker, open 80/443 only. Point a domain or use the VM IP with Caddy. |
| NVIDIA Brev ($60) | **Stretch only:** GPU instance to train the global embedding model (section 8.4). | Train, export to ONNX or TorchScript, copy the artifact to `services/ml/models/global/`, and run inference on CPU in the `ml` container. Shut the instance down after training. Not needed for the Isolation Forest MVP. |
| Hugging Face ($10) | Private model repo for the embedding-model artifact (and optionally the anonymized feature dataset). | `ml` service downloads the artifact at startup via `huggingface_hub` with `HF_TOKEN`. Free tier is enough; credits are optional. |
| Azure (own account) | **Fallback host** if 639Cloud has issues: one Azure VM with the same compose file, or Container Apps (`web` external ingress, `ml` internal) plus Azure Database for PostgreSQL Flexible Server (Burstable B1ms). | Keep as a warm backup; do not split the stack across providers. |
| Lovable (1 month) | Optional: fast visual mockups of the Nimbus portal pages to agree on layout. | Lovable generates React, not Nuxt. Use output as a design reference only; do not import its code. |
| Deepspace, Alsa, Photon, Anakin, Scale Maritime, Carbon Forge | Not used in core architecture. | If one offers an LLM API, it may power the optional "why was this flagged" explanation in `/admin/risk` (input: feature z-scores vs. enrollment; output: one sentence). Never in the auth decision path. |

Additional env vars for these:

```
HF_TOKEN=               # only if pulling the embedding model from Hugging Face
HF_MODEL_REPO=          # e.g. <org>/mousetrap-embed
LLM_API_URL=            # optional explanation feature
LLM_API_KEY=
```

## 13. Build phases (do in order; each phase ends with something runnable)

1. **Scaffold:** monorepo, docker-compose, Nuxt + Tailwind, Prisma + Postgres, FastAPI healthz. `docker compose up` works.
2. **Auth:** Better Auth with email/password, twoFactor, multiSession; login page, account switcher, signed-in devices page; seed script.
3. **Portal UI:** Nimbus Mobile pages from 7.3 with seeded data; account actions implemented without policy.
4. **Collector:** core + Vue adapter; `/api/telemetry` forwarding to `/ingest`; ML logs received batches.
5. **Features + enrollment:** windowing, features, `/enroll` page, training, feature parquet logging.
6. **Scoring + RiskMeter:** EWMA risk, `/api/risk`, RiskMeter widget.
7. **Policy + step-up:** `requireTrust`, StepUpModal, verify endpoint, session revoke, RiskEvent audit, `/admin/risk`.
8. **Modularity proof:** vanilla adapter on a plain HTML page served from `public/` using the same backend.
9. **Polish + stretch:** bot heuristics, feedback retraining, threshold tuning via env, then optional embedding model.

## 14. Demo script (90 s)

1. Alex signs in, browses, pays a bill; RiskMeter stays green.
2. Show account switcher: second session (Jordan) in same browser.
3. Switch back to Alex's session; a teammate takes the keyboard and mouse; meter climbs.
4. Teammate opens SIM swap: step-up TOTP modal appears.
5. Teammate keeps pushing / fails TOTP: session revoked, back to login.
6. Show `/admin/risk` timeline and the vanilla-adapter page to prove the front end is swappable.
