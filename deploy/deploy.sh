#!/usr/bin/env bash
# Deploy the full stack to a single Linux VM (ARCHITECTURE.md 12). Run from a checkout on the VM:
#
#   DOMAIN=demo.example.com ./deploy/deploy.sh
#
# Needs Docker with the compose plugin, and ports 80/443 open to the internet (Caddy gets the certificate).
# First run writes .env with fresh secrets and seeds the demo users; later runs pull and rebuild.
# Seed users get new ids on this host, so models from a laptop do not carry over: enroll again here.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v docker >/dev/null || { echo "Install Docker first: https://docs.docker.com/engine/install/" >&2; exit 1; }
docker compose version >/dev/null || { echo "Install the Docker compose plugin first." >&2; exit 1; }

if [[ ! -f .env ]]; then
  : "${DOMAIN:?Set DOMAIN to the public hostname, e.g. DOMAIN=demo.example.com $0}"
  echo "Writing .env for https://$DOMAIN"
  sed \
    -e "s|^BETTER_AUTH_SECRET=.*|BETTER_AUTH_SECRET=$(openssl rand -hex 32)|" \
    -e "s|^ML_INTERNAL_KEY=.*|ML_INTERNAL_KEY=$(openssl rand -hex 24)|" \
    -e "s|^BETTER_AUTH_URL=.*|BETTER_AUTH_URL=https://$DOMAIN|" \
    -e "s|^DOMAIN=.*|DOMAIN=$DOMAIN|" \
    -e "s|^TRUST_PROXY=.*|TRUST_PROXY=true|" \
    .env.example > .env
  chmod 600 .env
fi

if git rev-parse --git-dir >/dev/null 2>&1 && [[ -z "$(git status --porcelain --untracked-files=no)" ]]; then
  git pull --ff-only
fi

docker compose --profile deploy up -d --build

users=$(docker compose exec -T postgres psql -U mousetrap -tAc 'select count(*) from "user"' 2>/dev/null || echo 0)
if [[ "${users//[[:space:]]/}" == "0" ]]; then
  echo "Seeding demo users (scan the printed QR codes into an authenticator app)"
  docker compose --profile tools run --rm seed
fi

domain=$(grep -E '^DOMAIN=' .env | cut -d= -f2)
echo
echo "Up: https://$domain   (vanilla adapter page: https://$domain/demo-vanilla.html)"
echo "Next: sign in as each demo user and enroll at /enroll before the demo."
