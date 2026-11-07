#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="${REPO_URL:-}"
BASE_DIR="${BASE_DIR:-/home/administrator}"
[[ -n "$REPO_URL" ]] || { echo "Define REPO_URL" >&2; exit 1; }
command -v git >/dev/null || { echo "git no está instalado" >&2; exit 1; }
command -v docker >/dev/null || { echo "docker no está instalado" >&2; exit 1; }

deploy_env() {
  local env_name="$1" branch="$2" domain="$3" project="$4" api_port="$5" frontend_port="$6" dir_name="${7:-$env_name}"
  local dir="${BASE_DIR}/${dir_name}"
  mkdir -p "$BASE_DIR"
  if [[ -d "$dir/.git" ]]; then
    git -C "$dir" fetch origin "$branch"
    git -C "$dir" checkout "$branch"
    git -C "$dir" pull --ff-only origin "$branch"
  else
    git clone --branch "$branch" --single-branch "$REPO_URL" "$dir"
  fi
  ( cd "$dir" && DOMAIN="$domain" APP_ENV="$env_name" PROJECT_NAME="$project" \
      LICITAIA_API_PORT="$api_port" LICITAIA_FRONTEND_PORT="$frontend_port" ./scripts/deploy.sh )
}

deploy_env development "${DEV_BRANCH:-develop}" "${DEV_DOMAIN:-dev.mysecop.co}" licitaia-dev 8002 3001 licitaia-development
deploy_env staging "${STG_BRANCH:-staging}" "${STG_DOMAIN:-stg.mysecop.co}" licitaia-stg 8003 3002 licitaia-staging
# La instalación existente de producción usa /home/administrator/licitaia y
# el proyecto Compose licitaia; conservar ambos evita crear una base vacía.
deploy_env production "${PRD_BRANCH:-main}" "${PRD_DOMAIN:-mysecop.co}" licitaia 8001 3000 licitaia
