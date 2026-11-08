// Client half of the scam pause (ARCHITECTURE.md 7.5). trustedFetch() opens ScamPauseModal on 403
// {action:"pause"}, sends the customer's answer to /api/holds/:id, and ends the request with ActionPaused.
// The server decided to pause and records the answer; nothing here changes what is allowed.
type Choice = "cancel" | "hold";

interface PauseState {
  open: boolean;
  holdMs: number;
}

let pending: ((c: Choice) => void) | null = null;

export const usePauseState = () => useState<PauseState>("scam-pause", () => ({ open: false, holdMs: 0 }));

// Called by ScamPauseModal. Closing it any other way counts as cancel.
export function finishPause(choice: Choice) {
  usePauseState().value = { open: false, holdMs: 0 };
  const resolve = pending;
  pending = null;
  resolve?.(choice);
}

export class ActionPaused extends Error {}

export const holdDuration = (ms: number) =>
  ms >= 3_600_000 ? `${Math.round(ms / 3_600_000)} hours` : ms >= 60_000 ? `${Math.round(ms / 60_000)} minutes` : `${Math.round(ms / 1000)} seconds`;

export async function handlePause(data: { holdId?: string; holdMs?: number }): Promise<never> {
  pending?.("cancel");
  usePauseState().value = { open: true, holdMs: data.holdMs ?? 0 };
  const choice = await new Promise<Choice>((resolve) => (pending = resolve));
  const res = await $fetch<{ status: string; releaseAt: string | null }>(`/api/holds/${encodeURIComponent(data.holdId ?? "")}`, {
    method: "POST",
    body: { choice },
  }).catch(() => null);
  if (choice === "hold" && res?.releaseAt) {
    const at = new Date(res.releaseAt).toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit" });
    throw new ActionPaused(`Held for your protection. You can finish this after ${at}. Nothing has been changed yet.`);
  }
  throw new ActionPaused("Stopped. Nothing was changed. If someone asked you to do this, hang up: Nimbus will never ask for your PIN or a code.");
}
