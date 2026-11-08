# Mousetrap — Devpost draft

## Tagline
Step-up authentication that notices when someone else is at the keyboard.

## Inspiration
SIM-swap fraud and account takeover usually start with a password that's already been phished or reused. Once an attacker is signed in, a carrier portal treats them like the owner: they can move the line to a new SIM, reveal the port-out PIN, and take over every account that texts a code to that number. A password proves that someone knew a secret once. It says nothing about who is using the session right now.

## What it does
Mousetrap is a behavioral-biometric layer that sits in front of sensitive actions. We demo it on **Nimbus Mobile**, a fictional carrier portal.

- While you use the portal, a tiny collector records **how** you type and move: key hold and gap timing, pointer and touch motion. It never records **what** you type: no key values, no input text.
- A per-user model scores each few seconds of activity against that user's enrolled behavior and keeps a running session risk score.
- Every sensitive route asks the server's policy for a decision before it runs. The owner sails through. Someone else on the owner's session gets a TOTP prompt before a SIM swap. If they keep failing, or the risk is very high, the session is revoked and they're back at the login screen.
- Missing telemetry counts as risky. If the ML service is down, critical actions require step-up instead of being allowed.

## How we built it
- **Collector** (`@mousetrap-auth/collector`): a zero-dependency TypeScript SDK with Vue and vanilla adapters. It batches events every 3 s (with `sendBeacon` on page hide) and carries a per-page sequence number as a replay guard.
- **Portal**: Nuxt 3 + Tailwind + Prisma/Postgres, with Better Auth for email/password, TOTP, and multiple sessions per browser. The browser never names the user; the server resolves the user from the session cookie.
- **ML service**: FastAPI + scikit-learn. It cuts events into 5 s sliding windows and extracts keystroke, mouse, and touch features. Each user gets one Isolation Forest per modality, percentile-calibrated against their own enrollment. The session risk is an EWMA, plus bot heuristics for synthetic events, ruler-straight mouse paths, and metronome typing.
- **Policy**: one pure `decide()` function shared by enforcement and the live risk meter, so what the demo overlay shows is exactly what the server enforces. There are four tiers (view, standard, elevated, critical) with tunable thresholds.
- **Feedback**: after a successful step-up, that session's recent windows become training data. The model only learns from verified sessions, so an attacker can't train it to accept them.
- **Swappable front end**: a plain HTML page using the vanilla adapter is protected by the same backend, with the same step-up behavior.
- One `docker compose` stack (Postgres, web, ML, Caddy for HTTPS) deploys to a single VM.

## Challenges we ran into
- **Calibration.** Mapping risk as "1 − percentile" makes the genuine user's own windows uniform on 0–1, with a mean of 0.5, which is above the step-up threshold. We changed the mapping so a typical genuine window scores 0 and risk rises only below the user's 25th percentile.
- **Enrollment ≠ browsing.** Mouse speed and acceleration from the enrollment click game didn't carry over to normal browsing. The owner's own browsing looked anomalous. We split the model per modality, dropped task-dependent mouse features, and treat mouse as weak evidence. On our data, keystroke timing separates people best. That is also why enrollment is now passive: the template is learned from the first few minutes of normal portal use, with no exercise and nothing shown to the user.
- Keeping trust decisions entirely server-side, while still showing a live meter that can't drift from enforcement.

## Accomplishments we're proud of
- An end-to-end step-up flow: live score → policy → TOTP modal → retry, or session revoke.
- Privacy by construction: the event schema has no field that can hold a key value.
- On replayed real data, the owner's browsing settled around 0.13, under the 0.35 step-up line.

## What we learned
Behavioral signals are strong for typing and weak for casual mouse use unless enrollment looks like real use. Calibration matters as much as the model. "Unknown" has to mean "verify", never "allow".

## What's next
- A global embedding model (sequence model with triplet loss) scored against per-user templates, behind the same `/risk` contract.
- A React adapter, and a one-sentence "why was this flagged" explanation for support agents.

## Built with
TypeScript, Nuxt 3, Vue, Tailwind CSS, Prisma, PostgreSQL, Better Auth, Python, FastAPI, scikit-learn, pandas, Docker Compose, Caddy

---

# Pitch outline (3–4 slides)

1. **Problem.** A stolen password gets an attacker a fully trusted session. On a carrier portal, one SIM swap hands over every account tied to that number.
2. **How it works.** Collector (timing and motion only) → per-user model → session risk → server policy per action tier → allow / TOTP step-up / sign out. One diagram: browser → Nuxt `/api/telemetry` → ML; sensitive route → `requireTrust` → decision.
3. **Demo** (live, 90 s, ARCHITECTURE.md §14). The owner browses (green) → a second person takes over (meter climbs) → SIM swap asks for TOTP → wrong codes sign them out → `/admin/risk` timeline → vanilla page, same protection.
4. **What's next.** A global embedding model, more adapters. Privacy stance: never key values, and templates update only after verified step-up.
