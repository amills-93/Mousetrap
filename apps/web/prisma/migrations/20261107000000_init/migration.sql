-- CreateSchema
CREATE SCHEMA IF NOT EXISTS "public";

-- CreateTable
CREATE TABLE "CustomerAccount" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "accountNumber" TEXT NOT NULL,
    "portPin" TEXT NOT NULL,
    "autopay" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "CustomerAccount_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Line" (
    "id" TEXT NOT NULL,
    "accountId" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "nickname" TEXT NOT NULL,
    "plan" TEXT NOT NULL,
    "simIccid" TEXT NOT NULL,
    "deviceName" TEXT NOT NULL,
    "dataUsedGb" DOUBLE PRECISION NOT NULL DEFAULT 0,

    CONSTRAINT "Line_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Bill" (
    "id" TEXT NOT NULL,
    "accountId" TEXT NOT NULL,
    "period" TEXT NOT NULL,
    "amount" DECIMAL(10,2) NOT NULL,
    "dueDate" TIMESTAMP(3) NOT NULL,
    "paid" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "Bill_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "BiometricProfile" (
    "userId" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "windowCount" INTEGER NOT NULL DEFAULT 0,
    "modelVersion" INTEGER NOT NULL DEFAULT 0,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "BiometricProfile_pkey" PRIMARY KEY ("userId")
);

-- CreateTable
CREATE TABLE "SessionTrust" (
    "sessionId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "stepUpUntil" TIMESTAMP(3),
    "failedStepUp" INTEGER NOT NULL DEFAULT 0,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SessionTrust_pkey" PRIMARY KEY ("sessionId")
);

-- CreateTable
CREATE TABLE "StepUpFactor" (
    "userId" TEXT NOT NULL,
    "secret" TEXT NOT NULL,

    CONSTRAINT "StepUpFactor_pkey" PRIMARY KEY ("userId")
);

-- CreateTable
CREATE TABLE "RiskEvent" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "sessionId" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "tier" TEXT,
    "risk" DOUBLE PRECISION,
    "route" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "RiskEvent_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "CustomerAccount_userId_key" ON "CustomerAccount"("userId");

-- CreateIndex
CREATE UNIQUE INDEX "CustomerAccount_accountNumber_key" ON "CustomerAccount"("accountNumber");

-- CreateIndex
CREATE INDEX "RiskEvent_sessionId_createdAt_idx" ON "RiskEvent"("sessionId", "createdAt");

-- AddForeignKey
ALTER TABLE "Line" ADD CONSTRAINT "Line_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "CustomerAccount"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Bill" ADD CONSTRAINT "Bill_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "CustomerAccount"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

