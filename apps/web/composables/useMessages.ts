// Inbox with Scam Shield verdicts (ARCHITECTURE.md 7.6). One cached request shared by the nav badge,
// the overview card and the /messages page; call refresh() after feedback.
export type InboxMessage = {
  id: string;
  sender: string;
  body: string;
  receivedAt: string;
  verdict: "scam" | "suspicious" | "ok";
  scamProbability: number;
  categoryLabel: string | null;
  advice: string | null;
  redFlags: { id: string; label: string }[];
  customerVerdict: "reported" | "not_scam" | null;
};

export const useMessages = () => useFetch<InboxMessage[]>("/api/messages", { key: "messages" });

// Flagged texts the customer has not yet reported or dismissed.
export const needsReview = (m: InboxMessage) => m.verdict !== "ok" && !m.customerVerdict;
