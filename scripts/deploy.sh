#!/usr/bin/env bash
set -Eeuo pipefail

# Deploy LicitaIA without stopping or recreating containers from other projects.
# Usage: DOMAIN=mysecop.co APP_ENV=production PROJECT_NAME=licitaia-prd ./scripts/deploy.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DOMAIN="${DOMAIN:-}"
API_PORT="${LICITAIA_API_PORT:-8001}"
FRONTEND_PORT="${LICITAIA_FRONTEND_PORT:-3000}"
APP_ENV="${APP_ENV:-production}"
PROJECT_NAME="${PROJECT_NAME:-licitaia-${APP_ENV}}"
PREBUILT_IMAGES="${PREBUILT_IMAGES:-false}"
COMPOSE=(docker compose -p "$PROJECT_NAME" -f docker-compose.yml -f docker-compose.prod.yml)

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '\n==> %s\n' "$*"; }

[[ -n "$DOMAIN" ]] || die "Define DOMAIN, por ejemplo: DOMAIN=licitaia.centralspike.com $0"
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]] || die "DOMAIN no parece un dominio válido: $DOMAIN"
[[ "$API_PORT" =~ ^[0-9]+$ && "$FRONTEND_PORT" =~ ^[0-9]+$ ]] || die "Los puertos deben ser numéricos"
command -v docker >/dev/null || die "Docker no está instalado"
docker compose version >/dev/null || die "Docker Compose no está disponible"

set_env() {
  local key="$1" value="$2"
  if grep -qE "^${key}=" .env; then
    sed -i "s|^${key}=.*|${key}=${value}|" .env
  else
    printf '%s=%s\n' "$key" "$value" >> .env
  fi
}

info "Preparando .env (no se imprimen secretos)"
if [[ ! -f .env ]]; then
  cp .env.example .env
fi
chmod 600 .env

current_secret="$(grep -E '^SECRET_KEY=' .env | cut -d= -f2- || true)"
[[ -n "$current_secret" && "$current_secret" != "cambiar-por-una-clave-larga-y-aleatoria" ]] || set_env SECRET_KEY "$(openssl rand -hex 32)"
current_db_password="$(grep -E '^POSTGRES_PASSWORD=' .env | cut -d= -f2- || true)"
[[ -n "$current_db_password" && "$current_db_password" != "licitaia_dev" ]] || set_env POSTGRES_PASSWORD "$(openssl rand -hex 16)"
set_env ENVIRONMENT "$APP_ENV"
set_env ALLOW_DEMO_SEED false
set_env DEBUG_ENDPOINT_ENABLED false
set_env CORS_ORIGINS "https://${DOMAIN}"
set_env NEXT_PUBLIC_API_URL "https://${DOMAIN}"
set_env FRONTEND_URL "https://${DOMAIN}"
set_env MERCADOPAGO_BACK_URL "https://${DOMAIN}/app/plan"
set_env LICITAIA_API_PORT "$API_PORT"
set_env LICITAIA_FRONTEND_PORT "$FRONTEND_PORT"

info "Validando configuración Compose"
"${COMPOSE[@]}" config --quiet

info "Liberando caché e imágenes no utilizadas"
# No se eliminan volúmenes: contienen la base de datos y el almacenamiento.
info "Iniciando únicamente la infraestructura de LicitaIA"
"${COMPOSE[@]}" up -d db redis

info "Ejecutando migraciones"
"${COMPOSE[@]}" run --rm migrate

info "Construyendo imágenes de LicitaIA"
# Construir antes de crear contenedores evita una condición de carrera de
# BuildKit cuando varios servicios se levantan simultáneamente.
if [[ "$PREBUILT_IMAGES" == "true" ]]; then
  info "Usando imÃ¡genes construidas por GitHub Actions"
else
for intento in 1 2 3; do
  if "${COMPOSE[@]}" build api worker beat frontend; then
    break
  fi
  if [[ "$intento" -eq 3 ]]; then
    die "No fue posible construir las imÃ¡genes tras 3 intentos; revisa el acceso del daemon a Docker Hub"
  fi
  info "El build fallÃ³; reintentando en $((intento * 10)) segundos..."
  sleep $((intento * 10))
done
fi

info "Levantando LicitaIA"
"${COMPOSE[@]}" up -d --remove-orphans api worker beat frontend

info "Limpiando caché e imágenes antiguas"
# Conserva la caché reciente para que el siguiente despliegue no reinstale
# todas las dependencias; elimina únicamente caché con más de 7 días.

info "Esperando healthcheck de la API"
for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -fsS "http://127.0.0.1:${API_PORT}/health" || die "La API no respondió; revisa los logs del servicio api"

info "Estado final"
"${COMPOSE[@]}" ps
cat <<EOF

Despliegue terminado.
Dominio esperado: https://${DOMAIN}
API local para Nginx: http://127.0.0.1:${API_PORT}
Frontend local para Nginx: http://127.0.0.1:${FRONTEND_PORT}

Nginx debe enviar /api/ a la API y el resto al frontend.
EOF
