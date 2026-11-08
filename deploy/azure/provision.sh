#!/usr/bin/env bash
# Provision the Azure demo host and wire GitHub Actions to redeploy it (ARCHITECTURE.md 12, Azure row).
# Run once from a laptop that is signed in to both CLIs (`az login`, `gh auth login`):
#
#   ./deploy/azure/provision.sh
#
# Creates: resource group, one Ubuntu VM with a public DNS name (only 80/443 open, no SSH), and an Entra app
# that GitHub Actions signs in as through OIDC (no stored secrets), allowed only to run commands on VMs in
# this resource group. Then runs deploy/deploy.sh on the VM, which writes .env, starts the stack and seeds.
# Safe to re-run: existing resources are reused.
set -euo pipefail
cd "$(dirname "$0")/../.."

RG=${RG:-mousetrap-rg}
LOCATION=${LOCATION:-centralus}
VM=${VM:-mousetrap-vm}
SIZE=${SIZE:-Standard_D2as_v7}          # 2 vCPU / 8 GB: enough to build and run web + ml + postgres
DNS_LABEL=${DNS_LABEL:-mousetrap-demo}  # -> $DNS_LABEL.$LOCATION.cloudapp.azure.com
APP_NAME=${APP_NAME:-mousetrap-github-deploy}
GH_ENV=production
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
DOMAIN="$DNS_LABEL.$LOCATION.cloudapp.azure.com"

SUB=$(az account show --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
echo "Subscription $SUB, repo $REPO, host https://$DOMAIN"

az group create -n "$RG" -l "$LOCATION" -o none

if ! az vm show -g "$RG" -n "$VM" -o none 2>/dev/null; then
  echo "Creating VM $VM ($SIZE)"
  az vm create -g "$RG" -n "$VM" -l "$LOCATION" \
    --image Ubuntu2404 --size "$SIZE" --os-disk-size-gb 64 \
    --admin-username azureuser --generate-ssh-keys \
    --public-ip-sku Standard --public-ip-address-dns-name "$DNS_LABEL" \
    --nsg-rule NONE \
    --custom-data deploy/azure/cloud-init.yaml -o none
  az vm open-port -g "$RG" -n "$VM" --port 80 --priority 900 -o none
  az vm open-port -g "$RG" -n "$VM" --port 443 --priority 910 -o none
fi

# --- GitHub OIDC identity: may only run commands on VMs in this resource group ---
APP_ID=$(az ad app list --display-name "$APP_NAME" --query '[0].appId' -o tsv)
if [[ -z "$APP_ID" ]]; then
  APP_ID=$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)
fi
az ad sp show --id "$APP_ID" -o none 2>/dev/null || az ad sp create --id "$APP_ID" -o none
# GitHub sends either the plain subject or, for newer repos, one qualified with the owner and repo IDs
# (repo:owner@ownerId/name@repoId:...). Register both so either works.
OWNER_ID=$(gh api "repos/$REPO" -q .owner.id)
REPO_ID=$(gh api "repos/$REPO" -q .id)
ID_REPO="${REPO%%/*}@$OWNER_ID/${REPO#*/}@$REPO_ID"
for pair in "github-$GH_ENV|$REPO" "github-$GH_ENV-ids|$ID_REPO"; do
  name=${pair%%|*}
  subject="repo:${pair#*|}:environment:$GH_ENV"
  if ! az ad app federated-credential list --id "$APP_ID" --query "[?subject=='$subject']" -o tsv | grep -q .; then
    az ad app federated-credential create --id "$APP_ID" --parameters "{
      \"name\": \"$name\",
      \"issuer\": \"https://token.actions.githubusercontent.com\",
      \"subject\": \"$subject\",
      \"audiences\": [\"api://AzureADTokenExchange\"]
    }" -o none
  fi
done
RG_ID=$(az group show -n "$RG" --query id -o tsv)
az role assignment create --assignee "$APP_ID" --role "Virtual Machine Contributor" --scope "$RG_ID" -o none 2>/dev/null || true

gh api -X PUT "repos/$REPO/environments/$GH_ENV" --silent
for kv in "AZURE_CLIENT_ID=$APP_ID" "AZURE_TENANT_ID=$TENANT" "AZURE_SUBSCRIPTION_ID=$SUB" \
          "AZURE_RG=$RG" "AZURE_VM=$VM" "DEPLOY_DOMAIN=$DOMAIN"; do
  gh variable set "${kv%%=*}" --env "$GH_ENV" --body "${kv#*=}"
done

# --- First deploy (later ones come from .github/workflows/deploy.yml) ---
echo "Waiting for cloud-init, then running deploy.sh (first build takes several minutes)"
# Outbound network can be down for the first minutes of boot, so Docker and the checkout are retried here too.
out=$(az vm run-command invoke -g "$RG" -n "$VM" --command-id RunShellScript --query 'value[0].message' -o tsv \
  --scripts "cloud-init status --wait >/dev/null
    command -v docker >/dev/null || curl -fsSL --retry 10 --retry-all-errors https://get.docker.com | sh >/root/docker-install.log 2>&1
    [ -d /opt/mousetrap/.git ] || git clone https://github.com/$REPO.git /opt/mousetrap
    cd /opt/mousetrap && DOMAIN=$DOMAIN ./deploy/deploy.sh > /root/first-deploy.log 2>&1; echo exit=\$?
    grep -v '[▀▄█]' /root/first-deploy.log | tail -30")
echo "$out"
grep -q 'exit=0' <<< "$out" || { echo "deploy.sh failed on the VM (log: /root/first-deploy.log)" >&2; exit 1; }
# run-command returns only the last 4 KB, so the QR blocks are filtered out above; the otpauth:// URIs printed
# with them work as manual-entry keys (or paste one into any QR generator). Full log: /root/first-deploy.log.

echo
echo "Up: https://$DOMAIN"
echo "Add each otpauth:// URI above to an authenticator, then sign in and enroll each demo user at /enroll."
