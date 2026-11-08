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
│     ├─ components/          # DevOverlay (risk meter + telemetry), AccountSwitcher, StepUpModal, etc.
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

- Collector flushes every 3 s or 200 events, whichever first, plus `navigator.sendBeacon` on `pagehide`. `trustedFetch()` also awaits `flush()` (capped at 1 s) before every gated request, so the typing on the form itself reaches ML first.
- Each batch carries `seq` (monotonic per page load) and `pageId` (random UUID per load). Nuxt drops batches with non-increasing `seq` for a `pageId` (basic replay guard).
- Nuxt rejects telemetry with no valid session (401). Unauthenticated pages (login) do not collect.

### 5.2 Sensitive action

```
Browser --POST /api/account/sim-swap--> Nuxt
Nuxt: requireTrust(event, "critical")
  -> POST {ML_URL}/risk/{sessionId}/close   (scores the open window, then returns risk)
  -> policy decision
     allow    -> perform action
     step_up  -> 403 {action:"step_up", challengeId}
     pause    -> create ScamHold, 403 {action:"pause", holdId, holdMs}   (7.5)
     deny     -> revoke session, 401 {action:"logout"} with no reason (the user is not told why)
Browser: on step_up show StepUpModal -> POST /api/stepup/verify -> retry original action
         on pause show ScamPauseModal -> POST /api/holds/{holdId} {choice} -> action not performed
```

### 5.3 Step-up success

- `/api/stepup/verify` checks the code with Better Auth's own `verifyTOTP` against the active session (same authenticator entry as sign-in; with a session it creates no new session and applies no lockout). The `otplib` / `StepUpFactor` fallback is unused.
- Mark session `stepUpUntil = now + 60 s` (stored in `SessionTrust` table, keyed by Better Auth session id).
- If ML had scored at least `MIN_WINDOWS` (3) windows of the session, call `{ML_URL}/feedback` with `{userId, sessionId, label: "genuine"}`. A step-up forced only by missing telemetry sends no feedback: it is passed with the same TOTP used to sign in, so it says nothing about whose windows those are. ML appends the session's last 20 bot-free windows to the user's training set (`training.parquet`, capped at 300 windows), retrains in the background, and resets that session's score to 0. Feedback never creates a template for a user who has not enrolled.
- Within the `stepUpUntil` window, `requireTrust` skips step-up for every tier, but a risk at or above a tier's `deny` threshold still revokes the session.

### 5.3b Step-up typing challenge

A TOTP code alone proves little right after sign-in: the attacker just used the same code to sign in. So the prompt also asks the user to type a short phrase (paste is blocked), and its keystroke timing is judged against the owner's keys model.

- When `requireTrust` returns `step_up`, Nuxt calls ML `POST /challenge/{sessionId}/start {userId}`. ML scores the open window as usual, then records the keys risk (plus bot penalty) of every later window that has typing.
- `StepUpModal` awaits a collector flush before posting the code. `/api/stepup/verify` first calls `POST /challenge/{sessionId}/result`, which closes the open window and returns `{keysModeled, started, windows, risk}` (`risk` is the mean over the challenge windows). It starts a challenge if none is running, so calling verify without a prompt cannot skip the typing.
- `judgeTyping()` in `policy.ts` (pure, unit-tested): no ML or no keys model → `skip` (TOTP alone, as before); no typed windows yet → `retry` (400 `{action:"type_phrase"}`, not counted as a failed attempt); mean risk ≥ `TYPING_MAX_RISK` (0.5) → `fail`; otherwise `pass`.
- Every judged result is logged as `RiskEvent(type: "typing_ok" | "typing_failed", risk)` for `/admin/risk`.
- **Log-only for now (`TYPING_ENFORCE = false`).** On the Stage 5 data the free-text keys model, applied per phrase (two windows), fails the owner's own live typing 43–60% of the time at 0.5 (12–19% at 0.8) and fails the second person less often on one model, so it cannot decide this. The prompt still requires typed input, and the results are logged so a phrase-specific model can be calibrated later. With enforcement on, `fail` revokes the session silently, like a deny, before the code is checked, and `pass` allows ML feedback even when the session had fewer than `MIN_WINDOWS` scored windows.
- The phrase text never leaves the browser; only keystroke timing does, through the normal collector (principle 3).

### 5.4 Step-up failure

- Each wrong code writes `RiskEvent(type: "stepup_failed")` and increments `SessionTrust.failedStepUp`; the 3rd revokes the session and returns 401 `{action:"logout"}`, and the client redirects to `/login?reason=stepup_failed` (`/login` maps reason codes to fixed text).

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
  | { k: "ts"; t: number; id: number; x: number; y: number; r: number; f: number }  // touchstart
  | { k: "tm"; t: number; id: number; x: number; y: number; r: number; f: number }  // touchmove, throttled per touch
  | { k: "te"; t: number; id: number; x: number; y: number; r: number; f: number }  // touchend / touchcancel
  | { k: "fc"; t: number; role: string }                     // focus change: input role/type, never value
  | { k: "nv"; t: number; route: string }                    // route change
  | { k: "ps"; t: number; role: string }                     // a paste happened: target role/type only, never the text
  | { k: "vs"; t: number; hidden: boolean };                 // page hidden/shown or window blurred/focused

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
- Mouse events (`mm`/`md`/`mu`) come from pointer events with `pointerType === "mouse"`, so the emulated mouse events browsers fire after a tap never reach the mouse modality. Pen input is ignored.
- Touch events (`ts`/`tm`/`te`) come from `TouchEvent`, not pointer events, because the browser cancels pointer streams once it starts scrolling and swipes are most of the touch signal. One event per changed touch point: `id` is `Touch.identifier & 0xffff` (pairs start/move/end within a gesture), `r` is contact radius in px (max of `radiusX`/`radiusY`), `f` is `force` 0..1 (0 where unsupported, e.g. most iOS).

> Note: the tail of the `KeyClass` union and the `mm`/`fc` comments were truncated in the source PDF; `"nav" | "other"` and the comment text above are reconstructed from principle 3.

### 6.2 API

```ts
const c = createCollector({ endpoint: "/api/telemetry", flushMs: 3000, maxBatch: 200 });
c.start(); c.stop(); await c.flush(); c.setRoute(path); // flush() settles when all in-flight batches have
```

- Optional observability hooks `onEvent(e)` and `onBatch(info)` (seq, event count, counts per kind, bytes, transport, HTTP status, latency, response) see exactly what is sent and nothing more. The DevOverlay (7.3) uses them; production builds leave them unset.

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

model ScamHold {                       // 7.5
  id        String    @id @default(cuid())
  userId    String
  sessionId String
  route     String
  status    String    @default("pending") // pending | cancelled | held | used
  reasons   String    @default("")         // coachingScore() reasons, "|"-separated (admin only)
  releaseAt DateTime?
  createdAt DateTime  @default(now())
  @@index([userId, route])
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
| `/lines/:id` | rename line (`standard`), change plan (`critical`) | `standard` / `critical` |
| `/billing` | bill history, pay bill, toggle autopay | pay/autopay: `elevated` |
| `/profile` | name, email, address | edit: `elevated` |
| `/security` | change password, port-out PIN reveal, signed-in devices | `critical` |
| `/security/sim` | SIM swap / eSIM transfer to new device | `critical` |
| `/security/authorized-users` | add authorized user | `critical` |
| `/admin/risk` | demo-only live view of all sessions and scores | demo flag |

UI: Nuxt + Tailwind, original Nimbus brand (suggested palette: deep indigo `#2B2D7C` primary, cyan `#22C3E6` accent, neutral grays).

**DevOverlay** (`components/DevOverlay.vue`, rendered from `app.vue` only when `DEMO_MODE=true`, client-only): one persistent, collapsible panel in the bottom-left corner that shows the whole pipe. Collapse it (or set `DEMO_MODE=false`) for a "production" view. Sections, top to bottom:

1. **Risk meter** (Stage 6): polls `GET /api/risk` every 2 s while signed in. Shows the session risk as a 0–1 bar with a marker per tier at its `stepUp` and `deny` thresholds (7.4), a status label, the window count, and the per-modality components (`keys`, `mouse`, `touch`). Bar color is green below the lowest `stepUp` threshold, amber up to the lowest `deny` threshold, and red above it. When collapsed, the pill's dot takes the same color.
2. **Telemetry** (Stage 4): collector running/stopped and pending count, totals per modality plus `synthetic`, a feed of the latest events (key class and `code_hash` only), a trail of recent mouse/touch positions, and the latest batches (transport, bytes, HTTP status, latency, events buffered at ML).

The meter only displays; it never decides (principle 1). `/api/risk` returns `{risk, windows, lastUpdated, components, bot, thresholds, decisions, criticalRisk, mlAvailable, profileActive, stepUpActive}`, where `decisions` maps each tier to `allow | step_up | deny` as computed server-side by the same pure function `requireTrust` uses (7.4, steps 2–5, without side effects). The status label is the `critical` decision, e.g. "SIM swap would require step-up". The overlay draws the threshold markers from the `thresholds` the server returns, so `POLICY_THRESHOLDS_JSON` overrides show up live.

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
2. If `SessionTrust.stepUpUntil > now`, allow unless risk reaches the tier's `deny` threshold (checked in step 6).
3. Fetch `POST /risk/{sessionId}/close` from ML (timeout 300 ms): ML first scores the session's open window, so a fast attacker's last few seconds of input count. `/api/risk` uses the read-only `GET /risk/{sessionId}`.
4. If ML unreachable or `windows < MIN_WINDOWS (3)`, treat risk as `0.6` for `elevated`/`critical` (forces step-up), `0` otherwise.
5. If user's `BiometricProfile.status !== "active"`, require step-up for `critical`, allow others.
6. Compare risk to thresholds; on `deny` call Better Auth to revoke the session.
7. Write a `RiskEvent` for every decision.

Steps 2–5 and the threshold comparison live in a pure `decide({risk, windows, profileActive, stepUpActive}, tier)` that `requireTrust` and `/api/risk` both call, so the overlay's meter and the enforcement can never disagree.

Thresholds are env-overridable (`POLICY_THRESHOLDS_JSON`, any subset, e.g. `{"critical":{"stepUp":0.3}}`) for tuning during the demo; restart `web` to apply.

On the client, gated requests go through `trustedFetch()` (`composables/useStepUp.ts`): a 403 `step_up` opens the `StepUpModal`, and a verified code retries the request once; a 401 `logout` reloads to `/login`: plain, with no message, after a risk deny; `?reason=stepup_failed` after 3 wrong codes. Re-learning an active profile (`POST /api/enroll/start`, the DevOverlay's "re-learn") is gated at `critical` (principle 5). `/api/telemetry` writes a `score` RiskEvent at most every 5 s per session for the `/admin/risk` timeline.

### 7.5 Scam pause (coached customers)

Many carrier scams end with the real owner making the change: a caller posing as support talks them through revealing a transfer PIN or moving their SIM. Step-up does not help, because the owner passes it. So a critical action that looks coached gets a warning and a hold instead.

- **Signals.** ML's `coaching.py` counts these, all content-free, over the last 3 minutes: pastes into inputs (`ps`); leaving the page for 1.5 s or more and coming back (`vs`); silent pauses of 10 s or more; digits typed in spaced groups with 1.2–8 s gaps, as if read out. It also counts route changes this session. `/risk` returns the counts as `coaching`.
- **Score.** `coachingScore()` in `policy.ts` is hand-set rules, since there is no data on coached users. It is unit-tested.

  | Signal | Weight |
  |---|---|
  | tab switch | 0.3 each, up to 2 |
  | paste | 0.3 |
  | 2+ spaced digit groups | 0.25 |
  | long pause | 0.15 |
  | session < 5 min old with ≤ 2 route changes ("straight here after signing in") | 0.2 |
  | a scam text that ends in an account action, received in the last 24 h (7.6) | 0.3 |

  The score is capped at 1.
- **Decision.** `decide()` returns `pause` for `critical` when the score is 0.5 or more. Deny still wins. Pause applies with or without a profile and even inside a step-up window, because the coached owner can pass step-up.
- **Hold.** `requireTrust` creates a `ScamHold` (`pending`) and returns 403 `{action:"pause", holdId, holdMs}`. `ScamPauseModal` explains the scam, says Nimbus never asks for this, and offers two answers: "someone asked me to" (`cancelled`, logged `pause_reported`) or "I'm doing this myself" (`held` until `now + PAUSE_HOLD_MS`, 24 h by default, logged `pause_held`). The action is not performed either way. Once the hold has passed, that route skips the pause once (`used`).
- **What the customer is told.** The modal names no signals, since a scammer on the call would learn what to avoid. The reasons go only to the demo overlay and `/admin/risk`.

### 7.6 Screened messages (Scam Shield)

- `Message` rows hold the customer's texts with the verdict ML gave on arrival: `verdict`, `scamProbability`, `category`, `advice`, `accountRisk`, `redFlags`, and the customer's own `customerVerdict` (`reported` / `not_scam`).
- `GET /api/messages` fills a synthetic demo inbox on a user's first visit (`lib/messages.ts`; no reseed needed). The inbox includes the demo story's fake "Nimbus Security" text.
- `POST /api/messages/:id {action}` records the customer's feedback.
- `POST /api/messages/simulate` (DEMO_MODE) delivers a typed text so judges can try their own wording.
- `/messages` shows each verdict in words ("Scam very likely", "Be careful"), with the category, advice, and red flags. It also gives the percentage and says the filter can be wrong.
- If ML is down, a message is delivered marked "not checked", never shown as "ok".
- **Feeding the scam pause.** A recent `accountRisk` scam (fake carrier support, code theft, transfer-PIN request, SIM deactivation, bank alert) raises the coaching score, unless the customer marked it "not a scam". That ties the text to the account action it is setting up.
- **Privacy.** Every message is synthetic. Classification runs in the ML service; `/classify` scores a text and keeps nothing. Stored messages hold the text and its verdict for the inbox.

## 8. ML service (services/ml)

### 8.1 Endpoints (all require `X-Internal-Key`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/ingest` | `{userId, sessionId, batch}`; buffer, window, score |
| GET | `/risk/{sessionId}` | `{risk, windows, lastUpdated, components, bot}` |
| POST | `/risk/{sessionId}/close` `{userId}` | same; scores the open window first (gated actions) |
| POST | `/classify` `{text}` | scam verdict: `{verdict, scamProbability, category, categoryLabel, advice, accountRisk, redFlags}` (8.7) |
| GET | `/classifier/metrics` | held-out evaluation from training |
| POST | `/enroll/{userId}/start` | start (or restart) enrollment with an empty buffer |
| POST | `/enroll/{userId}/finish` | train model, return `{windowCount, ok}` |
| POST | `/feedback` | `{userId, sessionId, label}`; on `genuine`, add recent windows and retrain in background |
| GET | `/users/{userId}/status` | enrolled?, enrolling?, enrollment progress and targets, window count, model version |
| GET | `/healthz` | liveness |

Enrollment is passive: there is no enrollment page, and the user is never told it is happening.

- While a user is enrolling, `/ingest` routes their windows from normal portal use to the enrollment buffer instead of scoring. Windows completed by a batch with `synthetic > 0` are logged as `bot` and never enrolled.
- `/ingest` returns `enrolled`, `enrolling`, and `enrollReady`. Ready means 40 windows, at least 8 of them with typing (keys decide, 8.4); a user who never types stays enrolling.
- Nuxt (`server/lib/enroll.ts`, called after every telemetry batch, fire-and-forget): no model, not enrolling, and no active profile → `/enroll/{id}/start` and set the profile to `enrolling`. `enrollReady` → `/enroll/{id}/finish` and set the profile `active`. An active profile is never replaced passively (principle 5).
- Enrollment can span sessions, so it survives an ML restart: `models/{userId}/enrolling.json` records when it started, and the buffer is rebuilt from the `enroll` rows in `features.parquet` since then.
- Until the profile is active, policy treats the user as not enrolled (7.4: critical actions step up, others allow). Whoever uses the account first defines the template, so enrollment only ever runs inside a session that passed sign-in, including TOTP for 2FA accounts.

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

Touch (if ≥ 3 gestures, a gesture being one `id` from `ts` to `te`):

- tap duration (`ts` to `te` for gestures under ~10 px of travel): mean, std
- swipe: length, duration, speed mean/p90, straightness ratio, dominant direction share
- contact radius and force: mean, std (force skipped when always 0)
- inter-gesture gap: mean, std

Missing modality features are imputed with the user's enrollment median, plus binary `has_keys` / `has_mouse` / `has_touch` flags.

Log every feature vector to `models/{userId}/features.parquet` for debugging and plotting.

### 8.4 Model

- Per-user, per-modality `StandardScaler` + `IsolationForest(n_estimators=200, contamination="auto", random_state=42)`: one each for keys, mouse, and touch, trained only on the enrollment windows where that modality is present (minimum 20 windows overall, 8 per modality; target 40+). A modality below 8 windows is not scored for that user.
- Mouse uses shape and click features only (straightness, angle mean/std, pause mean, click hold mean/std). Speed, acceleration, and scroll depend on the task (click-target game vs. browsing) more than on the person; on the Stage 5 data they flagged the owner's own browsing.
- **Calibration:** at train time, store the sorted decision scores of the training windows. A new window's percentile `pct` in that distribution maps to `risk = clip((0.25 - pct) / 0.25, 0, 1)`: windows more typical than the user's 25th-percentile training window score 0, rising to 1 at the least typical. (Plain `1 - pct` makes genuine windows uniform on 0..1, mean 0.5, above the critical step-up threshold.)
- Persist with joblib at `models/{userId}/model.joblib` plus `meta.json` (version, format, window count, windows per modality). `scripts/retrain.py` rebuilds every model from the logged enrollment windows after a format change.
- Stretch: replace with a global embedding model (small 1D-CNN or GRU over event sequences, triplet loss) and score by cosine distance to a per-user template. Keep the same `/risk` contract so Nuxt does not change.

### 8.5 Session risk

- Window risk combines the modality risks present in the window: `sum(w_m * r_m) / max(1, sum(w_m))` with `w = {keys: 1.0, touch: 0.7, mouse: 0.4}`. Weights below 1 act as a zero prior, so a mouse-only window contributes at most 0.4 and any window with typing is judged mainly on keystrokes.
- `risk_t = alpha * window_risk + (1 - alpha) * risk_{t-1}`, `alpha = 0.3`; the first scored window sets the score.
- Track in memory: `{sessionId: {risk, windows, lastUpdated, components:{keys, mouse, touch}, bot}}`, where each component is its own EWMA. Expire after 30 min idle. `GET /risk/{sessionId}` returns these (`windows: 0` for an unknown session).
- Bot heuristics add to a window's risk: `synthetic > 0` in the batch that completed it (+0.3), mouse path angle-change std < 0.01 rad (+0.2), keydown interval std < 5 ms over 20+ keys (+0.3).
- `scripts/replay.py <modelUser> <dataUser>` replays logged windows through a model and the EWMA to check where a session would settle.

### 8.7 Scam classifier

- **Data** (`data/`):
  - `taxonomy.json` holds 13 scam categories, each with red flags, customer advice, and whether it ends in an account action. It also lists 7 kinds of legitimate message.
  - `messages.jsonl` holds 3,568 synthetic texts (1,456 scam) from `scripts/generate_messages.py`: fixed templates filled with fictional names, 555-01xx numbers, and `.example`/`.test` links, deterministic seed.
  - It includes hard negatives on purpose: real carrier notices that mention PINs, real verification codes, real delivery links.
- **Held-out wording.** Every fourth template of each category is held out, so evaluation measures wording the model never saw, not memorized templates.
- **Model** (`app/classifier.py`):
  - Scam vs not: logistic regression over TF-IDF word 1–2-grams, character 3–5-grams (lookalike domains, odd spellings), and one feature per red flag.
  - A second model picks the category for scams.
  - The red flags are rules that skip negated requests ("we will never ask for your PIN"). They explain verdicts to customers and are the rules-only baseline.
  - Verdict: `scam` at p ≥ 0.5, `suspicious` at 0.25 or more, otherwise `ok`.
  - Trained at image build by `scripts/train_classifier.py`, which writes `metrics.json`. A copy is kept in `data/classifier_metrics.json`.
- **Results on held-out templates** (892 rows):

  | | F1 | Precision | Recall | False positive rate |
  |---|---|---|---|---|
  | Model | 0.956 | 0.997 | 0.918 | 0.2% |
  | Rules-only baseline | 0.417 | | | |

  The model's ROC AUC is 0.996 and its category accuracy is 0.72. A random split scores 0.997, which shows how much seen templates inflate the number. The held-out figure is the one to quote.
- **Limits.** Every message comes from our own templates, so real-world accuracy is unknown. The most-missed kinds are short, link-free openers (family emergency, wrong number). Held-out errors were looked at twice during development: once leading to more varied legitimate messages and red-flag features, once to fix negated PIN warnings. So the held-out number is slightly optimistic.

## 9. Security notes (demo scope)

- ML service is not exposed publicly; only Nuxt calls it, with `X-Internal-Key`.
- CSRF: Better Auth defaults; telemetry endpoint accepts only same-origin `fetch` with JSON content type plus `sendBeacon` (text/plain JSON) from same origin.
- Rate limit `/api/telemetry` per session (e.g. 5 req/s).
- No real personal data. Seed users and data are fictional.
- `/login` carries a one-line notice that the portal looks at typing and motion timing (never what is typed) and that it is a demo. Enrollment itself is not surfaced.

## 10. Environment variables

```
DATABASE_URL=postgresql://mousetrap:mousetrap@postgres:5432/mousetrap
BETTER_AUTH_SECRET=...
BETTER_AUTH_URL=http://localhost:3000
ML_URL=http://ml:8000
ML_INTERNAL_KEY=...
POLICY_THRESHOLDS_JSON=
PAUSE_HOLD_MS=          # scam-pause hold (7.5); default 24 h, e.g. 60000 for the demo
DEMO_MODE=true          # enables DevOverlay (risk meter + telemetry) and /admin/risk
DOMAIN=localhost        # Caddy hostname (deploy profile)
TRUST_PROXY=false       # true behind Caddy: client IP from X-Forwarded-For
```

## 11. Seed data

Three users, each with a `CustomerAccount`, 2 to 4 lines, 6 months of bills, and a TOTP secret (printed by seed as otpauth URIs):

- `alex@nimbus.demo` / `Password123!`
- `jordan@nimbus.demo` / `Password123!`
- `sam@nimbus.demo` / `Password123!`

Each teammate enrolls as one of these users before the demo.

## 12. Hosting and platform choices

**Rule: everything runs from one `docker-compose.yml`.** Services: `postgres`, `web` (Nuxt, port 3000), `ml` (FastAPI, port 8000, internal only), plus `caddy` (`deploy` profile; ports 80/443, automatic HTTPS for `$DOMAIN`, reverse proxy to `web`, overwrites `X-Forwarded-For`; `web` trusts it only with `TRUST_PROXY=true`). Postgres and web bind to 127.0.0.1 on the host, so on the VM only Caddy is reachable. `deploy/deploy.sh` does the rest. Because the stack is portable, moving hosts is a `git pull && docker compose up -d`. Develop locally on laptops; deploy the same compose file to the demo host.

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
6. **Scoring + risk meter:** EWMA risk, `/api/risk`, risk meter section in the DevOverlay.
7. **Policy + step-up:** `requireTrust`, StepUpModal, verify endpoint, session revoke, RiskEvent audit, `/admin/risk`.
8. **Modularity proof:** vanilla adapter on a plain HTML page served from `public/` (`/demo-vanilla.html`) using the same backend; Nitro serves the built collector at `/collector/*`.
9. **Polish + stretch:** bot heuristics, feedback retraining, threshold tuning via env, then optional embedding model.

## 14. Demo script (90 s)

1. Alex signs in, browses, pays a bill; the overlay's risk meter stays green while its telemetry feed shows batches flowing.
2. Show account switcher: second session (Jordan) in same browser.
3. Switch back to Alex's session; a teammate takes the keyboard and mouse; meter climbs.
4. Teammate opens SIM swap: step-up TOTP modal appears.
5. Teammate keeps pushing / fails TOTP: session revoked, back to login.
6. Coached owner: Alex opens Messages. Scam Shield has flagged a fake "Nimbus Security" text about a SIM change, which says an agent will call and to have the transfer PIN ready. The "agent" (a teammate) calls and talks Alex through moving the line to a new SIM. Alex switches tabs and back, then types the ICCID as it is read out in groups. SIM swap shows the scam pause (recent scam text + tab switch + spaced digits), and Alex taps "someone asked me to". A judge can also type their own text into the demo "receive a text" box.
7. Show the `/admin/risk` timeline (decisions, the pause and the report, coaching score with reasons) and the vanilla-adapter page to prove the front end is swappable.
