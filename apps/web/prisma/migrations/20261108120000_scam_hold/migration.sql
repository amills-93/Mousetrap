-- CreateTable
CREATE TABLE "ScamHold" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "route" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'pending',
    "reasons" TEXT NOT NULL DEFAULT '',
    "releaseAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ScamHold_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "ScamHold_userId_route_idx" ON "ScamHold"("userId", "route");
