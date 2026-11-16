#!/usr/bin/env bash
# First deploy on the VPS (docs/RUNBOOK.md "VPS deploy"). Run from the repo root:
#   bash infra/setup_vps.sh <public-domain>
# Writes .env once (random internal secrets; asks for the Groq key, the optional OpenRouter key
# and the reviewer password, so no secret goes through a terminal log), then starts the stack.
set -euo pipefail
domain="${1:?usage: bash infra/setup_vps.sh <public-domain>}"

set_var() {  # replace KEY=... in .env, or append it
  if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi
}
rand() { openssl rand -hex 24; }
per_user() { echo "ai_ml_engineer=$(rand),fullstack_dev=$(rand),data_analyst=$(rand)"; }

if [ ! -f .env ]; then
  read -rsp "Groq API key: " groq; echo
  read -rsp "OpenRouter API key (Enter to skip): " openrouter; echo
  read -rsp "Password for the reviewer login: " password; echo
  [ -n "$groq" ] && [ -n "$password" ] || { echo "The Groq key and the password are required."; exit 1; }
  cp .env.example .env
  set_var APP_ENV production
  set_var APP_SECRET_KEY "$(rand)"
  set_var APP_USERS "$(python3 -m apps.api.auth.users reviewer "$password")"
  set_var PRELOAD_PERSONAS reviewer=ai_ml_engineer
  set_var POSTGRES_PASSWORD "$(rand)"
  set_var GIGSIM_API_TOKEN "$(rand)"
  set_var GIGSIM_ADMIN_TOKEN "$(rand)"
  set_var GIGSIM_TOKENS "$(per_user)"
  for server in MARKETPLACE PORTFOLIO WORKSPACE; do set_var "${server}_MCP_TOKENS" "$(per_user)"; done
  set_var TOKEN_ENCRYPTION_KEY "$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  set_var GROQ_API_KEY "$groq"
  set_var OPENROUTER_API_KEY "$openrouter"
  chmod 600 .env
fi
set_var PUBLIC_DOMAIN "$domain"

# --env-file: compose reads ${POSTGRES_PASSWORD} and ${PUBLIC_DOMAIN} from the repo-root .env
docker compose -f infra/docker-compose.yml --env-file .env --profile public up -d --build
docker compose -f infra/docker-compose.yml --env-file .env ps
echo "Open https://$domain and sign in as reviewer."
