# Mousetrap Implementation Plan

Companion to `ARCHITECTURE.md`. Work stage by stage. Do not start a stage until the previous stage's **Done when** checks pass. Each stage lists a prompt to paste into Claude Code.

Time boxes assume the clock started at 4:00 PM Saturday and submission is around noon Sunday. Times are targets; if a stage overruns by more than 50%, cut scope from that stage rather than pushing everything later.

Parallel tracks (if you have teammates):
- **Track A (platform):** Stages 1, 2, 7
- **Track B (portal UI):** Stage 3, then the DevOverlay risk meter and StepUpModal UI in 6 and 7
- **Track C (ML):** Stages 4 (ML side), 5, 6 (ML side)

Agree on the event schema (ARCHITECTURE.md 6.1) and the ML API contract (8.1) before splitting up. Those two contracts let the tracks work independently.

---

## Stage 0: Setup (4:00 to 4:30 PM)

**Goal:** everyone can run the repo.

Tasks
- Create GitHub repo `mousetrap`, add `ARCHITECTURE.md` and this file.
- Install Docker, Node 20+, pnpm, Python 3.12 locally.
- Provision the 639Cloud VM now (Docker installed, ports 80/443 open) so hosting is not a surprise later.
- Install an authenticator app on each phone for TOTP.

**Done when:** repo cloned on every laptop; `ssh` into the VM works.

---

## Stage 1: Scaffold (4:30 to 5:30 PM)

**Goal:** empty but running stack.

Tasks
- pnpm workspace with `apps/web`, `packages/collector`, `services/ml`.
- Nuxt 3 + Tailwind + TypeScript in `apps/web`.
- Prisma initialized against Postgres.
- FastAPI app with `/healthz`, Dockerfile, `requirements.txt`.
- `docker-compose.yml` with `postgres`, `web`, `ml`; `.env.example`.

**Done when**
- `docker compose up` starts all three.
- `http://localhost:3000` shows a Nuxt page.
- `curl localhost:8000/healthz` returns OK from inside the compose network.
- `pnpm prisma migrate dev` runs cleanly.

**Claude Code prompt**
> Read ARCHITECTURE.md. Implement Stage 1 from IMPLEMENTATION_PLAN.md: the repository layout in section 4, docker-compose with postgres, web, and ml, Nuxt 3 with Tailwind, Prisma connected to Postgres, and a FastAPI service with /healthz. Use the env vars in section 10. Stop when the Done-when checks pass and tell me how to verify.

---

## Stage 2: Auth and sessions (5:30 to 7:30 PM)

**Goal:** real login with multiple users and multiple sessions.

Tasks
- Better Auth in `server/lib/auth.ts` with Prisma adapter, email/password, `twoFactor`, `multiSession`.
- Generate Better Auth tables into `schema.prisma`; add the app models from 7.2.
- `/api/auth/[...all].ts` handler; Vue auth client.
- `/login` page with TOTP step if 2FA is enabled.
- Header account switcher (list device sessions, switch, sign out one or all).
- `/security` "Signed-in devices" list with revoke.
- Global route middleware: unauthenticated users go to `/login`.
- Seed script: 3 users, accounts, lines, bills, TOTP secrets printed as otpauth URIs.

**Done when**
- All three seed users can sign in.
- Two users signed in at once in one browser; switching works without re-entering a password.
- Same user in two browsers shows two sessions on the devices page; revoking one logs that browser out.
- TOTP from the phone app works at login.

**Claude Code prompt**
> Implement Stage 2 from IMPLEMENTATION_PLAN.md using ARCHITECTURE.md sections 7.1, 7.2, and 11. Use Better Auth with the Prisma adapter and the twoFactor and multiSession plugins. Build login, the account switcher, the signed-in devices page with revoke, auth middleware, and the seed script. Check the Better Auth docs for the current Nuxt integration and plugin APIs rather than guessing.

---

## Stage 3: Nimbus Mobile portal (7:30 to 9:30 PM)

**Goal:** a believable fictional carrier account portal, no security layer yet.

Tasks
- Layout: header with Nimbus logo (simple original SVG), nav, account switcher.
- Pages from ARCHITECTURE.md 7.3: Overview, Lines, Line detail, Billing, Profile, Security, SIM swap, Authorized users.
- Server routes under `server/api/account/` that perform each action against Prisma.
- Data usage bars, bill history table, pay bill button, autopay toggle, plan change, port-out PIN reveal, SIM swap form.

**Done when**
- Every page renders seeded data for the signed-in user only.
- Every action works and persists (pay bill, change plan, SIM swap, add authorized user, change password).
- No real carrier names, logos, or colors anywhere.

**Claude Code prompt**
> Implement Stage 3: the Nimbus Mobile portal pages and account action routes from ARCHITECTURE.md 7.3, using the seeded data. Use the palette in 7.3 and an original simple logo. Keep components small. Do not add the policy layer yet; leave a clear TODO where requireTrust will go on each sensitive route.

---

## Stage 4: Collector and telemetry pipe (9:30 to 11:00 PM)

**Goal:** behavior data flows from browser to ML service.

Tasks
- `packages/collector`: core (listeners, throttling, buffering, batching, sendBeacon on pagehide), schema types, Vue adapter, vanilla adapter.
- Nuxt client plugin: start after auth, stop on sign-out, `setRoute` on navigation.
- `/api/telemetry.post.ts`: resolve session, replay guard on `pageId` + `seq`, rate limit, forward to ML `/ingest` with `X-Internal-Key`.
- ML `/ingest`: validate with pydantic, buffer per session, log batch counts.

**Done when**
- Typing and moving the mouse in the portal produces ML logs every ~3 s.
- No key values or input text appear anywhere in payloads (inspect the network tab).
- Signed-out pages send nothing; telemetry with no session returns 401.

**Claude Code prompt**
> Implement Stage 4: the collector package per ARCHITECTURE.md section 6 (core, Vue adapter, vanilla adapter), the Nuxt client plugin, /api/telemetry with session resolution, replay guard, and rate limit, and the ML /ingest endpoint with pydantic validation. Never capture KeyboardEvent.key or input values.

**Checkpoint (~11:00 PM):** full pipe working. If not, stop adding features and fix this first.

---

## Stage 5: Features and enrollment (11:00 PM to 1:30 AM)

**Goal:** each user has a trained behavioral model.

Tasks
- `features.py`: windowing (8.2) and features (8.3), with imputation and modality flags.
- Write each window's feature vector to `models/{userId}/features.parquet`.
- `/enroll` page: consent banner, typing passage, click-target game, progress bar to 40 windows.
- Nuxt `/api/enroll/*` routes calling ML `/enroll/{userId}/start` and `/finish`.
- `model.py`: scaler + IsolationForest, percentile calibration, joblib persistence, `meta.json`.
- Update `BiometricProfile` status.

**Done when**
- Each teammate enrolls as one seed user and gets a saved model.
- A quick notebook or script plots a few features per user and they visibly differ (if not, fix features before moving on).

**Claude Code prompt**
> Implement Stage 5 from ARCHITECTURE.md sections 8.2 to 8.4: windowing, feature extraction, enrollment endpoints, per-user IsolationForest with percentile calibration and persistence, and the /enroll page with consent, a typing passage, and a click-target exercise. Also write scripts/plot_features.py that loads the parquet files and plots key features per user.

**Sleep window:** 1:30 to 5:30 AM is the best time to sleep. Leave stages 1 to 5 committed and working.

---

## Stage 6: Live scoring and risk meter (5:30 to 7:00 AM)

**Goal:** a live risk score that reacts to who is at the keyboard.

Tasks
- `scoring.py`: per-window risk, EWMA, session state, idle expiry, bot heuristics (8.5).
- ML `/risk/{sessionId}` and `/users/{userId}/status`.
- `server/lib/policy.ts`: thresholds plus the pure `decide()` (ARCHITECTURE.md 7.4). Stage 7 wraps it in `requireTrust`.
- Nuxt `/api/risk` (current session only): `{risk, windows, lastUpdated, components, thresholds, decisions}`, with `decisions` from `decide()` for each tier.
- Risk meter as the top section of the existing `DevOverlay` (ARCHITECTURE.md 7.3), not a separate widget: poll `/api/risk` every 2 s while the collector is running, score bar with `stepUp`/`deny` markers per tier, status label from `decisions.critical`, window count, per-modality components. Color the collapsed pill's dot by risk. No client-side thresholds or decision logic.

**Done when**
- Owner uses their own account: meter stays low after ~30 s.
- Teammate takes over: meter rises noticeably within ~30 to 60 s.
- Record rough numbers for both cases; you need them for thresholds.

**Claude Code prompt**
> Implement Stage 6: session scoring with EWMA and bot heuristics per ARCHITECTURE.md 8.5, the ML /risk and /users/{id}/status endpoints, the pure decide() in server/lib/policy.ts, Nuxt /api/risk returning server-computed decisions per tier, and the risk meter as the top section of the existing DevOverlay showing score and the tier thresholds from 7.4. The overlay only displays what /api/risk returns.

---

## Stage 7: Policy, step-up, and enforcement (7:00 to 9:00 AM)

**Goal:** the actual product. Sensitive actions are gated by behavior.

Tasks
- `server/lib/policy.ts`: add `requireTrust(event, tier)` exactly per 7.4 around the Stage 6 `decide()` (session revoke on deny, `RiskEvent` write), env-overridable thresholds.
- Apply it to every sensitive route from 7.3.
- StepUpModal: shows on a `step_up` response, verifies TOTP, retries the original request.
- `/api/stepup/verify`: Better Auth TOTP if it works with an active session, otherwise the `otplib` fallback.
- `SessionTrust`: `stepUpUntil` and failed-attempt counting; 3 failures revoke the session.
- Deny path: revoke the Better Auth session, client redirects to `/login` with a message.
- ML `/feedback` on step-up success.
- `RiskEvent` written for every decision; `/admin/risk` page lists sessions, scores, and a decision timeline.

**Done when**
- Owner can do a SIM swap with no prompt (or one prompt early in the session).
- Teammate on the owner's account gets the TOTP prompt on SIM swap.
- Wrong TOTP 3 times, or very high risk, logs them out.
- Killing the ML container makes critical actions require step-up rather than allowing them.

**Claude Code prompt**
> Implement Stage 7 from ARCHITECTURE.md sections 5.2 to 5.4 and 7.4: requireTrust on every sensitive route, the StepUpModal with retry, the step-up verify endpoint (try Better Auth twoFactor against the active session; fall back to otplib with StepUpFactor if needed), SessionTrust handling, session revocation on deny, ML feedback, RiskEvent logging, and the /admin/risk page.

**Checkpoint (~9:00 AM):** the demo script in ARCHITECTURE.md section 14 works end to end locally. This is the minimum submittable product.

---

## Stage 8: Deploy and modularity proof (9:00 to 10:15 AM)

**Goal:** public URL and evidence that the front end is swappable.

Tasks
- Add `caddy` to compose; deploy to the 639Cloud VM; run migrations and seed there.
- Re-enroll on the deployed instance (or copy `models/` over).
- Vanilla adapter demo: a plain HTML page in `public/demo-vanilla.html` with a sensitive button hitting the same backend.
- Smoke-test the full demo on the deployed URL.

**Done when**
- Demo works over HTTPS on the public URL.
- The vanilla page triggers step-up the same way the Nuxt portal does.

**Claude Code prompt**
> Implement Stage 8: add Caddy for HTTPS to docker-compose, write a deploy script for a single Linux VM, and build public/demo-vanilla.html using the vanilla collector adapter against the same backend.

---

## Stage 9: Tune, record, rehearse (10:15 AM to submission)

Tasks
- Tune thresholds with `POLICY_THRESHOLDS_JSON` using the numbers from Stage 6.
- Record a backup demo video of the full script.
- Write the Devpost description and a 3 to 4 slide pitch: problem (account takeover, SIM swap fraud), how it works, demo, what's next.
- Rehearse the 90 s demo at least twice.

**Done when:** video recorded, submission filed, demo rehearsed.

---

## Stretch goals (only after Stage 7 checkpoint)

Pick one, in this order of value:
1. React adapter page (strongest proof of "swappable front end").
2. LLM one-sentence "why flagged" explanation on `/admin/risk`.
3. Global embedding model trained on NVIDIA Brev, artifact on Hugging Face, same `/risk` contract.

## Cut list (if behind schedule)

Cut in this order: stretch goals, `/admin/risk` timeline (keep the table), bot heuristics, feedback retraining, Authorized users page, vanilla adapter page (mention it instead), public deployment (demo from a laptop).
Never cut: enrollment, live risk meter in the DevOverlay, step-up on SIM swap, logout on deny.
