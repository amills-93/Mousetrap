// Client half of step-up (ARCHITECTURE.md 5.2): trustedFetch() runs a request; on 403 {action:"step_up"} it
// opens the StepUpModal, waits for a verified code, and retries once. On 401 {action:"logout"} it sends the
// browser to /login with the server's reason. The server decides; this only reacts to its answers.
type FetchOptions = { method?: "GET" | "POST" | "PATCH"; body?: Record<string, unknown> };
// Untyped on purpose: Nitro's typed-route inference blows the TS stack on a generic url.
const rawFetch = $fetch as unknown as (url: string, opts?: FetchOptions) => Promise<unknown>;

interface StepUpState {
  open: boolean;
  tier: string | null;
}

let pending: ((ok: boolean) => void) | null = null;

export const useStepUpState = () => useState<StepUpState>("stepup", () => ({ open: false, tier: null }));

function requestStepUp(tier: string | null): Promise<boolean> {
  const state = useStepUpState();
  pending?.(false); // a second gated request supersedes the first prompt
  state.value = { open: true, tier };
  return new Promise((resolve) => (pending = resolve));
}

// Called by StepUpModal.
export function finishStepUp(ok: boolean) {
  useStepUpState().value = { open: false, tier: null };
  const resolve = pending;
  pending = null;
  resolve?.(ok);
}

export class StepUpCancelled extends Error {
  constructor() {
    super("Verification cancelled");
  }
}

const actionOf = (e: any): { action?: string; tier?: string; reason?: string } => e?.data?.data ?? {};

export function signedOut(reason?: string) {
  const q = reason ? `?reason=${encodeURIComponent(reason)}` : "";
  window.location.assign(`/login${q}`); // full reload: drop all client state of the revoked session
}

export async function trustedFetch<T = unknown>(url: string, opts: FetchOptions = {}): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try {
      return (await rawFetch(url, opts)) as T;
    } catch (e) {
      const { action, tier, reason } = actionOf(e);
      if (action === "logout") {
        signedOut(reason);
        throw e;
      }
      if (action === "step_up" && attempt === 0) {
        if (!(await requestStepUp(tier ?? null))) throw new StepUpCancelled();
        continue;
      }
      throw e;
    }
  }
}
