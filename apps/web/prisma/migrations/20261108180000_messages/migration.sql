-- CreateTable
CREATE TABLE "Message" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "sender" TEXT NOT NULL,
    "body" TEXT NOT NULL,
    "receivedAt" TIMESTAMP(3) NOT NULL,
    "verdict" TEXT NOT NULL,
    "scamProbability" DOUBLE PRECISION NOT NULL,
    "category" TEXT,
    "categoryLabel" TEXT,
    "advice" TEXT,
    "accountRisk" BOOLEAN NOT NULL DEFAULT false,
    "redFlags" TEXT NOT NULL DEFAULT '[]',
    "customerVerdict" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "Message_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Message_userId_receivedAt_idx" ON "Message"("userId", "receivedAt");
