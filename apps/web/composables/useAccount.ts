// Shared account data for all portal pages (one request, cached under one key; call refresh() after actions).
export const useAccount = () => useFetch("/api/account", { key: "account" });

// POST/PATCH helper for gated account actions: handles step-up (trustedFetch), then returns an error
// message string, or null on success.
export async function accountAction(path: string, body: unknown, method: "POST" | "PATCH" = "POST") {
  try {
    await trustedFetch(path, { method, body: body as Record<string, unknown> });
    return null;
  } catch (e: any) {
    if (e instanceof StepUpCancelled) return "Verification cancelled. Nothing was changed.";
    if (e instanceof ActionPaused) return e.message;
    return e?.data?.statusMessage || e?.statusMessage || "Something went wrong";
  }
}

export const money = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
export const shortDate = (d: string | Date) => new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
