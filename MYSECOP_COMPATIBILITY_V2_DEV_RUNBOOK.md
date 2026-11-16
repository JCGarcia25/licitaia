# MySECOP Compatibility V2 — Runbook DEV RC1

Preparado el 16 de noviembre de 2026. **Este documento no autoriza ejecutarlo en DEV operativo.** Requiere segunda orden explícita con destino y alcance. No se ha ejecutado ningún paso de despliegue. Publicar un commit/push/tag requiere además autorización Git; push a develop dispara el workflow de auto-deploy existente.

## 1. Prerrequisitos y límites

Operador con acceso autorizado únicamente al proyecto DEV, ventana de mantenimiento y contacto de recuperación. Confirmar servidor, dominio API/frontend, base/usuario PostgreSQL, broker/DB Redis, proyecto Compose, volúmenes y almacenamiento privado. Ninguno puede apuntar a producción o compartir credenciales/volúmenes empresariales. Confirmar también SMTP/pagos/schedulers de DEV: no heredar destinatarios, llaves ni tareas operativas de otro entorno.

Revisar `MYSECOP_COMPATIBILITY_V2_RELEASE_MANIFEST.md` y `...RELEASE_VALIDATION.json`. El código completo está en un tar local con hashes; **HEAD cac56d0 no contiene el RC**. Antes de transferir/publicar, autorización separada y referencia Git/artefacto aprobada. En destino, verificar SHA-256 del archivo y cada miembro contra manifest.json. No extraer sobre un checkout sucio ni sobre `.env`/uploads; usar un directorio de release nuevo sin secretos, comprobar rutas relativas y ausencia de enlaces, y conservar el directorio anterior.

Necesarios: Python 3.12, PostgreSQL compatible 16 (QA 16.2), Redis (QA real temporal; imagen propuesta Redis7), Docker/Compose con soporte de `!override` y profiles, Node22 para imagen frontend; host con recursos y permisos de volumen. **En esta preparación no había Docker: imagen Linux, Compose resuelto y digest OCI están pendientes.** El build local usó Node20.11.0/npm10.2.4. No instalar servicios globales durante QA.

Detener la operación si falta backup, identidad verificable, versiones de rollback o coherencia de config. Los comandos siguientes son plantillas para el operador autorizado, no scripts de ejecución automática.

## 2. Preparación local ya ejecutada y reproducción QA

Se ejecutaron backend, PG aislado, Redis/Celery aislados, build/TS y E2E con fixtures. Para repetir en una máquina de QA con dependencias ya provisionadas, desde la raíz:

```bash
cd backend
.venv/bin/python -m pytest -q
/ruta/venv-qa/bin/python scripts/test_isolated_postgresql.py
/ruta/venv-qa/bin/python scripts/test_isolated_phase13.py
cd ../frontend
npm ci --no-audit --no-fund
npm run build
npx --no-install tsc --noEmit
cd ../backend
PLAYWRIGHT_BROWSERS_PATH=/ruta/chromium-qa MYSECOP_E2E_V2=1 MYSECOP_E2E_EVALUATION=1 /ruta/venv-qa/bin/python scripts/e2e_phase13.py
```

Crear los venvs de QA de forma aislada con `-c constraints-release-candidate.txt -r requirements-isolated-tests.txt`; Chromium requiere provisión explícita. Los arneses crean bases mysecop_test_* y procesos propios, y comprueban los destinos descartables antes de provocar interrupciones. No inyectar URLs de DEV operativo en esas pruebas. Los nombres mysecop_test_* solos no acreditan que una instancia externa sea descartable; usar los runners que la crean.

## 3. Configuración protegida del futuro DEV

Crear/provisionar fuera del repositorio un env file DEV con permisos 0600 y respaldo seguro. No copiar el `.env.example` sin revisar cada valor. No imprimir `docker compose config` sin `--quiet`, `env`, URLs, JWTs ni secrets. No cargar archivos arbitrarios con `source`. Inyectar el entorno desde el gestor de secretos o el mecanismo del operador. El secreto JWT debe tener al menos 32 caracteres aleatorios y ser propio de DEV; no cambiarlo en una instalación sin considerar que invalida sesiones.

| Variable | Configuración requerida |
|---|---|
| ENVIRONMENT | development |
| DATABASE_URL | URL PostgreSQL explícita del DEV confirmado; usuario, host/base y opciones revisados; password fuera del informe |
| REDIS_URL | Redis DEV dedicado y DB explícita; mismo broker y result backend en todos los procesos |
| POSTGRES_DB/USER/PASSWORD | Sólo si se usa el servicio db de este proyecto; concordantes con DATABASE_URL y volumen existente |
| SECRET_KEY | Gestor de secretos, nunca literal en comandos/logs |
| EVALUATION_API_ORIGIN | Origen externo exacto de la API, esquema+host+puerto cuando aplique |
| FRONTEND_URL/CORS_ORIGINS | Origen frontend DEV; CORS no wildcard |
| NEXT_PUBLIC_API_URL | API DEV fijada durante build; cambiar variable del contenedor no reescribe bundle ya construido |
| LICITAIA_API_PORT/FRONTEND_PORT | Puertos DEV libres, publicados sólo en loopback por override prod; proxy TLS confirmado |
| ALLOW_DEMO_SEED/DEBUG_ENDPOINT_ENABLED | false |
| EMBEDDING_PROVIDER/EMBEDDING_DIM/LLM_PROVIDER | fake/dimensión compatible con DEV/heuristic; no cambiar datos reales o proveedor externo implícitamente |
| BILLING_PROVIDER | manual para este RC DEV; no introducir llaves/SMTP reales por defecto |
| COMPATIBILITY_V2_SHADOW_ENABLED/EVALUATION_ENABLED | false inicialmente |
| EVALUATION_DEV_TARGETS | [] inicialmente; autorización de tupla+UUID en el piloto posterior |
| EVALUATION_SEMANTIC_ENABLED/EVALUATION_EXTERNAL_MAX_CALLS | false / 0; no API externa |
| MATCH_GLOBAL_CONCURRENCY/BATCH_SIZE/LEASE_SECONDS/MAX_RETRIES | 2 / 200 / 300 / 3; ajustar sólo con capacidad y prueba |
| COMPATIBILITY_V2_SAMPLE_LIMIT/BATCH_SIZE/LEASE_SECONDS | 20 / 5 / 120 |
| EVALUATION_MAX_UNIVERSE/MAX_SAMPLE/RETENTION_DAYS | 500 / 100 / 30; expiración lógica, plan de retención física separado |

El overlay fija fake/semántica off/cero llamadas como protección del RC inicial. Si el DEV existente contiene embeddings de otro proveedor/dimensión, **parar**: decidir explícitamente si usar otra base aislada o un plan de invalidación autorizado; no recalcular masivamente ni migrar vectores como efecto secundario. Configurar `RC_ENV_FILE` con ruta absoluta del archivo protegido también dentro del entorno de interpolación. El overlay usa `env_file: !override` para evitar heredar secretos del `.env` base. No exportar secretos a la consola para resolver interpolación.

Con entorno ya provisto, preflight offline desde backend:

```bash
.venv/bin/python scripts/release_preflight.py
```

No conecta a servicios. PASS_OFFLINE comprueba formato/coherencia; **no** verifica propiedad del host, backup, revisión real, marcador ni entropía. Los defaults locales dan BLOCKED y no deben habilitarse por conveniencia. Revisar también `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`: el código utiliza **REDIS_URL** para ambos, por lo que variables Celery distintas no deben crear una falsa expectativa.

## 4. Identificación, respaldo y estado anterior — sólo tras autorización

Registrar ticket/orden, operador, fecha, nombres no sensibles de servicios, commit/image digest anterior, revisiones Alembic, hash/schema y conteos de tablas clave. Consultas de lectura a DEV sólo tras confirmar destino y autorización. No imprimir cadena de conexión. Comparar company/users, UserOpportunity, historial, jobs/cursors, evidence/shadow/evaluation y auditoría. Si hay objetos creados por create_all sin historial Alembic o deriva de tipo/nulabilidad/FK/unique, detenerse y preparar reparación específica; **no usar stamp**.

Poner API en mantenimiento para impedir escrituras y detener schedulers/workers de **este** proyecto. Esperar tareas activas con límite controlado, registrar jobs RUNNING y checkpoints. Detener API antes de migración para evitar DDL del startup. No usar kill global, docker prune, down -v ni remove-orphans.

Plantilla Compose, en el nuevo directorio de release y con estas variables **no secretas** ya verificadas:

```bash
RC_COMPOSE=(docker compose --project-name "$RC_PROJECT" --env-file "$RC_ENV_FILE" -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.dev-rc.yml)
"${RC_COMPOSE[@]}" --profile scheduler --profile experiments config --quiet
"${RC_COMPOSE[@]}" --profile scheduler --profile experiments stop beat worker worker-matches worker-shadow worker-evaluation api
```

En una instalación anterior, detener también los nombres reales de workers previamente registrados; no asumir que son exactamente los de la nueva plantilla. No ejecutar stop sobre otro project_name. No arrancar servicios db/redis nuevos sobre volúmenes ajenos.

Backup PostgreSQL consistente con herramientas del operador. Ejemplo con servicio libpq preconfigurado en archivo protegido, no URL/password en argumentos:

```bash
umask 077
pg_dump --dbname="service=${RC_PG_SERVICE}" --format=custom --file="$RC_BACKUP_DB"
pg_restore --list "$RC_BACKUP_DB" > "$RC_BACKUP_INDEX"
```

El nombre RC_PG_SERVICE debe resolver **al DEV confirmado**, no una variable heredada. Respaldar también almacenamiento privado y config fuera del repositorio; cifrar, limitar permisos y registrar checksum, ubicación y política. `pg_restore --list` sólo valida catálogo: comprobar restauración real en una base aparte aislada antes de proceder. Preservar Redis si es necesario para recuperación; la cola no reemplaza DB/historial persistente. Nunca almacenar backups o dump de datos empresariales en Git o dentro del paquete RC.

## 5. Instalación y migraciones — sólo tras autorización

Construir imágenes del **nuevo** código antes de usar migrate y registrar sus IDs/digests. Evita el problema del deploy heredado, que intenta migrar antes de construir. No usar `scripts/deploy.sh` ni los workflows existentes para este procedimiento sin revisión: también arrancan beat y carecen del overlay RC.

```bash
"${RC_COMPOSE[@]}" --profile experiments build api migrate worker worker-matches worker-shadow worker-evaluation frontend
"${RC_COMPOSE[@]}" run --rm --no-deps api python scripts/release_preflight.py
"${RC_COMPOSE[@]}" run --rm --no-deps migrate alembic current
"${RC_COMPOSE[@]}" run --rm --no-deps migrate alembic heads
```

`heads` debe devolver un único 0014. `current` **sí conecta** a la base y sólo procede aquí con autorización. Registrar revisiones pendientes, revisar 0003–0008 si las hubiera y comparar schema con modelos en una copia del backup. No avanzar si el estado existente es desconocido. Upgrade aprobado:

```bash
"${RC_COMPOSE[@]}" run --rm --no-deps migrate alembic upgrade head
"${RC_COMPOSE[@]}" run --rm --no-deps migrate alembic current
```

Verificar que el esquema resultante corresponde a 0014: tablas, columnas, tipos, nullable, índices/unique/FK, y conservación de conteos/relaciones/historial. La prueba local no sustituye esta comprobación. No ejecutar downgrades ni stamp para corregir un fallo. PostgreSQL permite rollback DDL transaccional habitual, pero si el resultado es incierto inspeccionar primero y conservar logs sin secretos; no repetir escrituras a ciegas.

## 6. Inicio controlado y healthchecks

Usar el Redis/PostgreSQL DEV confirmado ya existente. No recrear infraestructura ni volúmenes. Primera puesta en marcha con flags off y sin scheduler:

```bash
"${RC_COMPOSE[@]}" up -d --no-deps api frontend worker worker-matches
"${RC_COMPOSE[@]}" ps
curl --fail --silent --show-error "$RC_API_ORIGIN/health"
```

Verificar `inspect active_queues`/ready de los workers y registrar sólo nombres: worker → celery; worker-matches → matches. Broker/result backend deben ser el mismo Redis DEV. Revisar logs con acceso restringido, sin volcados de perfiles, vectores, auth ni raw_json; no copiar logs operativos completos al repositorio. La API tiene pool 10+5 por proceso: considerar API+todos workers al calcular conexiones. Concurrency de Celery no sustituye MatchSlot global.

Confirmar proxy Host y scheme correctos para request.base_url y origen experimental exacto; confiar X-Forwarded sólo de proxies autorizados. No relajar la allowlist para eludir un rechazo de origen. Revisar CORS y bundle NEXT_PUBLIC_API_URL. El health HTTP por sí solo no prueba DB/broker, migraciones ni autorización.

No iniciar beat durante el smoke inicial: publica sincronización SECOP periódica y recuperación matching/recordatorios. Su habilitación futura requiere confirmar que las tareas programadas y volúmenes de datos están autorizados. La recuperación matching también puede solicitarse por las rutas de resume existentes; no llamar sync ni rescore_all masivamente como healthcheck.

## 7. Smoke comercial y privacidad

Usar sólo cuentas/empresa y oportunidades/documentos **sintéticos** separados y autorizados. No alterar perfiles, puntuaciones ni proyectos empresariales de terceros para probar. No poblar automáticamente todo DEV con demo seed.

1. Login, expiración/token inválido y cuenta sin Premium; validar límites Pro sin tocar licencias reales.
2. Dashboard y perfil, búsqueda por texto/filtros y paginación, oportunidad guardada/descartada y proyecto/análisis con documento ficticio; desktop/móvil.
3. Un recálculo acotado al universo sintético controlado: registrar candidatos, CURRENT/PENDING/STALE/FAILED, cursor y lotes; comprobar versiones, finalización/cancelación/resume y conservación de score/triage/historial. La ruta comercial recorre su universo, por lo que si DEV contiene datos reales extensos no usarla como prueba pequeña: ejecutar el arnés en otra base aislada.
4. Dos empresas: análisis/documentos/proyectos/jobs privados inaccesibles a la otra; comprobar corrección de Analysis con y sin análisis propio. Una fila histórica sin user_id no se comparte automáticamente.
5. Con flags false, rutas internas devuelven denegación; sin links internos en navegación comercial. Producción sigue rechazada por guardia aunque se cambien flags experimentales (probar en fixtures, no cambiando producción).
6. Alertas in-app con fixtures, sin enviar correo o cobrar. Revisar métricas propias `/api/matches/metrics`, lease expirado, retries y errores; ninguna métrica global revela scores/perfiles de otro usuario.

Registrar evidencia y diferencias comerciales esperadas: score pendiente ya no aparece como cero/calculado y análisis privado ajeno deja de mostrarse. No confundir integridad del matcher con ausencia total de cambios funcionales de fases 1–1.3.

## 8. Piloto experimental opcional posterior

**No está autorizado automáticamente por desplegar el código.** Requiere objetivo y actores DEV definidos y exclusivamente fixtures, salvo autorización separada de datos reales.

Después de 0014, fijar tupla exacta DB/broker/API en EVALUATION_DEV_TARGETS con UUID propio. Con workers experimentales detenidos y flags habilitados sólo para la configuración del piloto autorizada, registrar identidad persistida:

```bash
"${RC_COMPOSE[@]}" run --rm --no-deps api python scripts/evaluation_target.py --register-identity "$RC_EVALUATION_UUID" --acknowledge-isolated-dev
"${RC_COMPOSE[@]}" run --rm --no-deps api python scripts/evaluation_target.py --verify-database
```

Ese comando **escribe** marcador/auditoría y requiere aprobación de piloto. El script exige evaluation_enabled para provisionar: no se debe activar ese flag ni provisionar identidad sin la orden correspondiente. No sobreescribe identidad incompatible. Para shadow-only, preparar la identidad en esa ventana autorizada y después apagar evaluación si no se usará. Reiniciar servicios únicamente con configuración aprobada consistente.

Arrancar explícitamente worker-shadow y worker-evaluation con perfil experiments y verificar sus colas. Mantener semántica false/llamadas0/sin key externa. Crear snapshot shadow pequeño con admin y perfil propio ficticio; comprobar invariancia de UserOpportunity y pesos. Campaña sintética: import de pilot-synthetic-100.json sujeto a límites, dos revisores independientes role evaluation_reviewer y tercer adjudicador; admin no puede juzgar sus pares. Validar ausencia de scores antes del sellado, cierre y export sin documentos ni identidades privadas. No etiquetar fixtures como humanos reales ni afirmar superioridad A/B/C. Deshabilitar flags y detener workers experimentales al finalizar; conservar historial y auditoría.

El SDK `openai` opcional no forma parte de las dependencias instaladas/declaradas de este RC; el import diferido sólo se alcanzaría con proveedor externo. No intentar habilitarlo en este piloto. Una futura fase externa requiere dependencia fijada y validación separada, además de autorización de gasto y de textos.

## 9. Rollback conservador

Ante fallo crítico, parar nuevas solicitudes y publicaciones de este proyecto, detener beat/workers y documentar trabajos en vuelo. Deshabilitar shadow/evaluation/semántica y dejar llamadas0. Una llamada externa ya en vuelo podría consumir coste; este RC no las permite. No vaciar Redis ni purgar colas compartidas: los mensajes pueden recuperarse con código/contratos compatibles.

Reapuntar API/frontend/workers a imágenes anteriores **conocidas por digest** y configuración DEV protegida anterior. Antes de arrancar comprobar que el código anterior tolera las columnas aditivas y que no reabre consumo experimental. Mantener la base en 0014, conservando datos empresariales, scores históricos, MatchScoreHistory, checkpoints, campañas, juicios y auditoría. Comprobar login, permisos, listado, guardadas/proyectos y latencia; documentar cachés/contratos frontend y versión revertida. No usar `up --remove-orphans`, down -v, drop tables ni downgrades forzados.

Cambios que **no revierte el código**: datos SECOP insertados/normalizados, versiones y estados de score, historial, triage/proyectos/documentos creados, autorizaciones/revocaciones, campaña/juicios/adjudicaciones/informes/marcador, auditoría, y cualquier consumo externo ya producido. Un rollback de código no los borra ni reconstruye valores previos. Si una recuperación requiere restaurar DB/storage, autorizarla explícitamente, restaurar primero a un destino aislado y planificar escrituras posteriores al backup; no sobrescribir DEV ni perder datos nuevos como parte implícita del rollback.

0011–0014 tienen guardias de información; 0010 elimina cursores y 0001 usa modelos actuales. **No ejecutar downgrade en un ambiente con datos para facilitar rollback**. Si la imagen anterior no es compatible, mantener mantenimiento y resolver sobre copia, sin inventar éxito ni usar stamp.

## 10. Cierre de operación futura

Registrar autorización, destino, identidad, payload/Git SHA, digests, backup comprobado, revision/schema antes/después, flags, colas, smoke, incidencias, advertencias y decisión de continuar/revertir. La puesta en DEV no demuestra calidad estadística ni autoriza producción. La preparación actual termina antes de ese punto; el estado operativo sigue **no verificado/no desplegado**.
