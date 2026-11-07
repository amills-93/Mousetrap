// Shared account data for all portal pages (one request, cached under one key; call refresh() after actions).
export const useAccount = () => useFetch("/api/account", { key: "account" });

// POST/PATCH helper: returns an error message string, or null on success.
export async function accountAction(path: string, body: unknown, method: "POST" | "PATCH" = "POST") {
  try {
    await $fetch(path, { method, body });
    return null;
  } catch (e: any) {
    return e?.data?.statusMessage || e?.statusMessage || "Something went wrong";
  }
}

export const money = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD" });
export const shortDate = (d: string | Date) => new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
