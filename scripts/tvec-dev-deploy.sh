#!/usr/bin/env bash
# Called only by the existing development deployment, never by STG/production.
set -Eeuo pipefail
umask 077
mode="${1:?mode}"; release="${2:?commit}"
[[ "$release" =~ ^[a-f0-9]{40}$ ]] || exit 2
[[ "$PWD" == /home/administrator/licitaia-development ]] || exit 2
project=licitaia-dev
compose=(docker compose -p "$project" -f docker-compose.yml -f docker-compose.prod.yml)
backup="$PWD/backups/tvec-$release"
if [[ "$mode" == preflight ]]; then
  mkdir -p "$backup"
  cp -p .env "$backup/environment.before"
  for service in api db redis; do
    container="$("${compose[@]}" ps -q "$service")"
    [[ -n "$container" ]]
    [[ "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$container")" == "$project" ]]
  done
  api="$("${compose[@]}" ps -q api)"
  db="$("${compose[@]}" ps -q db)"
  redis="$("${compose[@]}" ps -q redis)"
  # Reject any shared database volume or shared application network with another project.
  docker inspect $(docker ps -aq) | python3 -c '
import json,sys
containers=json.load(sys.stdin); project="licitaia-dev"
own=[c for c in containers if (c["Config"].get("Labels") or {}).get("com.docker.compose.project")==project]
db=next(c for c in own if (c["Config"].get("Labels") or {}).get("com.docker.compose.service")=="db")
volumes={m["Source"] for m in db["Mounts"]}
networks={n for c in own for n in c["NetworkSettings"]["Networks"]}
for c in containers:
    if (c["Config"].get("Labels") or {}).get("com.docker.compose.project")==project:continue
    if volumes & {m["Source"] for m in c["Mounts"]}:raise SystemExit("Shared DEV database volume: abort")
    if networks & set(c["NetworkSettings"]["Networks"]):raise SystemExit("Shared DEV network: abort")
print("DEV Docker project, networks and database volume isolated")'
  docker exec -i "$api" python - <<'PY'
from app.core.config import get_settings
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from redis import Redis
s=get_settings(); u=make_url(s.database_url); r=make_url(s.redis_url)
assert s.environment=='development' and s.frontend_url.rstrip('/')=='https://dev.mysecop.co'
assert u.get_backend_name()=='postgresql' and u.host=='db' and not u.query
assert r.host=='redis' and r.database=='0' and not r.query
assert len(s.secret_key)>=32 and not getattr(s,'tvec_ingest_enabled',False)
with create_engine(s.database_url).connect() as c:
    assert c.execute(text('select current_database()')).scalar_one()==u.database
    assert c.execute(text('select version_num from alembic_version')).scalar_one() in {'0014_evaluation_platform','0015_tvec_orders'}
assert Redis.from_url(s.redis_url).ping()
print('DEV API, PostgreSQL revision/destination and Redis verified; ingestion disabled')
PY
  curl -fsS http://127.0.0.1:8002/health | python3 -c 'import json,sys; assert json.load(sys.stdin)["environment"]=="development"'
  # A full logical dump is retained on the server, never printed or uploaded to GitHub.
  docker exec "$db" sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$backup/database.dump"
  [[ -s "$backup/database.dump" ]]
  docker exec -i "$db" pg_restore --list < "$backup/database.dump" > "$backup/database.list"
  restore="licitaia-dev-tvec-restore-${release:0:12}"
  cleanup() { docker rm -fv "$restore" >/dev/null 2>&1 || true; }
  trap cleanup EXIT
  # Only this disposable container and its anonymous volume are removed.
  docker run -d --name "$restore" --network none -e POSTGRES_PASSWORD="$(openssl rand -hex 32)" "$(docker inspect -f '{{.Image}}' "$db")" > /dev/null
  ready=false
  for _ in {1..30}; do
    if docker exec "$restore" pg_isready -U postgres > /dev/null 2>&1; then ready=true; break; fi
    sleep 1
  done
  [[ "$ready" == true ]]
  docker exec -i "$restore" pg_restore --exit-on-error --no-owner --no-privileges -U postgres -d postgres < "$backup/database.dump"
  docker exec "$restore" psql -U postgres -d postgres -Atqc 'select version_num from alembic_version' > "$backup/restored-revision.txt"
  sha256sum "$backup/database.dump" > "$backup/database.sha256"
  date -u +%FT%TZ > "$backup/RESTORE_VERIFIED"
  echo "DEV backup restored successfully in disposable PostgreSQL; backup retained: $backup"
elif [[ "$mode" == activate ]]; then
  [[ -s "$backup/RESTORE_VERIFIED" ]]
  rollback_activation() {
    status=$?
    trap - ERR
    cp -p "$backup/environment.before" .env
    "${compose[@]}" up -d --no-deps api worker beat || true
    echo 'TVEC activation failed: previous DEV configuration restored; additive schema retained' >&2
    exit "$status"
  }
  trap rollback_activation ERR
  api="$("${compose[@]}" ps -q api)"
  # The allowlist contains destination identities without passwords.
  docker exec -i "$api" python - > "$backup/tvec-target.json" <<'PY'
import json,uuid
from app.core.config import get_settings
from sqlalchemy.engine import make_url
s=get_settings()
from sqlalchemy import create_engine,select
from app.db.models import EvaluationEnvironmentIdentity
from app.services.evaluation_guard import database_identity,broker_identity
from app.services.match_versions import digest
assert s.environment=='development' and s.frontend_url.rstrip('/')=='https://dev.mysecop.co'
identity=str(uuid.uuid5(uuid.NAMESPACE_URL,'https://dev.mysecop.co/tvec-isolated-development'))
fingerprint=digest([database_identity(s.database_url),broker_identity(s.redis_url),'https://dev.mysecop.co'])
with create_engine(s.database_url).connect() as c:
    row=c.execute(select(EvaluationEnvironmentIdentity.id,EvaluationEnvironmentIdentity.purpose).where(EvaluationEnvironmentIdentity.fingerprint==fingerprint)).first()
    if row:
        assert row.purpose=='isolated-development'
        identity=row.id
print(json.dumps([dict(database=make_url(s.database_url).set(password=None).render_as_string(hide_password=False),broker=make_url(s.redis_url).set(password=None).render_as_string(hide_password=False),api_origin='https://dev.mysecop.co',identity=identity)]))
PY
  python3 - "$backup/tvec-target.json" <<'PY'
import json,sys
from pathlib import Path
target=json.loads(Path(sys.argv[1]).read_text())
updates={'TVEC_ENABLED':'true','TVEC_INGEST_ENABLED':'false','TVEC_API_ORIGIN':'https://dev.mysecop.co','TVEC_DEV_TARGETS':"'"+json.dumps(target,separators=(',',':'))+"'"}
p=Path('.env'); lines=p.read_text().splitlines()
lines=[line for line in lines if line.split('=',1)[0] not in updates]
p.write_text('\n'.join(lines+[f'{k}={v}' for k,v in updates.items()])+'\n')
PY
  identity="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))[0]["identity"])' "$backup/tvec-target.json")"
  "${compose[@]}" run --rm --no-deps -T api python scripts/tvec_admin.py --register-identity "$identity" --acknowledge-isolated-dev < /dev/null
  "${compose[@]}" up -d --no-deps api worker beat
  "${compose[@]}" exec -T api python scripts/tvec_admin.py --verify-database < /dev/null
  "${compose[@]}" exec -T api python -c 'from app.core.config import get_settings;s=get_settings();assert s.tvec_enabled and not s.tvec_ingest_enabled;print("TVEC DEV enabled; ingestion remains disabled; no sync scheduled")' < /dev/null
else
  exit 2
fi
