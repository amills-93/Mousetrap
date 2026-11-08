// The customer's text inbox with scam verdicts (ARCHITECTURE.md 7.6). Every message is synthetic.
import { mlClassify } from "./ml";
import { prisma } from "./prisma";

export const SCAM_CONTACT_WINDOW_MS = 24 * 60 * 60 * 1000;

// The demo inbox each user starts with (minutes ago, sender, text). It includes the story the demo tells: a fake
// Nimbus security text that sets up a phone call asking for the transfer PIN.
const DEMO_INBOX: [number, string, string][] = [
  [6, "(469) 555-0142", "Nimbus Security: a SIM change was requested on your line. If this wasn't you, stay by your phone: an agent will call you shortly to verify your account. Have your transfer PIN ready."],
  [42, "Nimbus", "Nimbus: your bill of $86.40 is ready. View it in the Nimbus app. Reply STOP to opt out."],
  [95, "Jordan", "Running 10 min late, save me a seat"],
  [180, "(214) 555-0117", "SwiftShip: your package B482019334 is held at our depot. Pay $2.99 redelivery fee: https://parcel-redeliver.test/k2x9"],
  [260, "Nimbus", "Nimbus: your verification code is 604118. Don't share it with anyone. Nimbus will never ask for it."],
  [600, "(800) 555-0163", "MetroPass Tolls: you have an unpaid toll of $4.15. Pay by Friday to avoid a $50 penalty: https://toll-settle.example/p7"],
  [1500, "Cedar Bank", "Cedar Bank: your direct deposit of $1,240.00 has arrived."],
  [2900, "(972) 555-0108", "Hi, is this Taylor? We met at the conference last week"],
];

// Classify and store one message. If ML is down the text is still delivered, marked unchecked ("suspicious" at 0),
// so the customer sees it was not screened rather than a false "ok".
export async function receive(userId: string, sender: string, body: string, receivedAt = new Date()) {
  const v = await mlClassify(body).catch(() => null);
  return prisma.message.create({
    data: {
      userId,
      sender,
      body,
      receivedAt,
      verdict: v?.verdict ?? "suspicious",
      scamProbability: v?.scamProbability ?? 0,
      category: v?.category ?? null,
      categoryLabel: v ? v.categoryLabel : "Not checked (scam filter unavailable)",
      advice: v?.advice ?? null,
      accountRisk: v?.accountRisk ?? false,
      redFlags: JSON.stringify(v?.redFlags ?? []),
    },
  });
}

// First visit: fill the inbox. Idempotent per user (only when the inbox is empty).
export async function ensureInbox(userId: string) {
  if (await prisma.message.count({ where: { userId } })) return;
  const now = Date.now();
  for (const [minsAgo, sender, body] of DEMO_INBOX) await receive(userId, sender, body, new Date(now - minsAgo * 60_000));
}

// Coaching input (7.5): a recent scam text of a kind that ends in an account action, unless the customer marked it
// "not a scam". Reporting it still counts: the scammer may still be on the phone.
export async function recentScamContact(userId: string) {
  const since = new Date(Date.now() - SCAM_CONTACT_WINDOW_MS);
  const n = await prisma.message.count({
    where: { userId, accountRisk: true, receivedAt: { gte: since }, NOT: { customerVerdict: "not_scam" } },
  });
  return n > 0;
}
