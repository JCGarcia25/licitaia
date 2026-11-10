#!/usr/bin/env bash
set -u

RECIPIENT="${1:-}"
if [[ -z "$RECIPIENT" ]]; then
  echo "Uso: $0 correo_destino@example.com" >&2
  exit 1
fi

test_env() {
  local name="$1" dir="$2" project="$3"
  echo
  echo "========== $name =========="
  if [[ ! -f "$dir/.env" ]]; then
    echo "ERROR: no existe $dir/.env" >&2
    return 1
  fi
  cd "$dir" || return 1
  if ! docker compose -p "$project" -f docker-compose.yml -f docker-compose.prod.yml ps --status running api | grep -q api; then
    echo "ERROR: el contenedor api no está activo" >&2
    return 1
  fi
  docker compose -p "$project" -f docker-compose.yml -f docker-compose.prod.yml exec -T -e TEST_RECIPIENT="$RECIPIENT" api python - <<'PY'
import os
import smtplib
import ssl
from email.message import EmailMessage

host = os.getenv("SMTP_HOST", "")
port = int(os.getenv("SMTP_PORT", "587"))
user = os.getenv("SMTP_USER", "")
password = os.getenv("SMTP_PASSWORD", "")
sender = os.getenv("ALERTS_FROM_EMAIL") or user
recipient = os.environ["TEST_RECIPIENT"]

print(f"SMTP_HOST={host}")
print(f"SMTP_PORT={port}")
print(f"SMTP_USER={user}")
print(f"ALERTS_FROM_EMAIL={sender}")
print("SMTP_PASSWORD=" + ("configurada" if password else "vacía"))

if not host:
    raise RuntimeError("SMTP_HOST está vacío")
if not sender:
    raise RuntimeError("ALERTS_FROM_EMAIL y SMTP_USER están vacíos")
if user and not password:
    raise RuntimeError("SMTP_USER existe pero SMTP_PASSWORD está vacía")

message = EmailMessage()
message["Subject"] = "Prueba SMTP LicitaIA"
message["From"] = sender
message["To"] = recipient
message.set_content("Este es un correo de prueba enviado por LicitaIA mediante SMTP.")

with smtplib.SMTP(host, port, timeout=20) as server:
    server.ehlo()
    server.starttls(context=ssl.create_default_context())
    server.ehlo()
    if user:
        server.login(user, password)
    server.send_message(message)

print(f"OK: correo enviado a {recipient}")
PY
  local result=$?
  if [[ "$result" -eq 0 ]]; then
    echo "RESULTADO: $name OK"
  else
    echo "RESULTADO: $name FALLÓ"
  fi
  return "$result"
}

ok=0
test_env "DEVELOPMENT" "/home/administrator/licitaia-development" "licitaia-dev" || ok=1
test_env "STAGING" "/home/administrator/licitaia-staging" "licitaia-stg" || ok=1
test_env "PRODUCTION" "/home/administrator/licitaia" "licitaia" || ok=1

echo
if [[ "$ok" -eq 0 ]]; then
  echo "Todos los ambientes enviaron el correo correctamente."
else
  echo "Uno o más ambientes fallaron. Revisa el error mostrado arriba." >&2
  exit 1
fi
