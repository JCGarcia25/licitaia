# MySECOP Compatibility V2 — Release Candidate

Fecha: 16 de noviembre de 2026, America/Bogota. Nombre propuesto: `mysecop-compatibility-v2-rc1`.

## Resumen ejecutivo y dictamen

**Preparación local aprobada con restricciones. Publicación Git y despliegue operativo bloqueados hasta su autorización y verificación de destino.** No se ejecutó despliegue, migración DEV, conexión empresarial, sincronización, commit, push, merge ni tag. Los sistemas experimentales permanecen apagados por defecto; no se activa V2 comercial ni proveedor externo.

Existe un paquete local completo identificado por hashes, que captura explícitamente los archivos nuevos y las modificaciones acumuladas. **No existe todavía un release Git**: un checkout de HEAD no reproduce el código validado. La identidad exacta, archivos y hash del archivo se encuentran en `MYSECOP_COMPATIBILITY_V2_RELEASE_MANIFEST.md`. El paquete no equivale a una imagen Linux reproducible por digest.

La evidencia repetida sobre el código actual comprende 151 pruebas backend, 14 PostgreSQL, 8 Redis/Celery, build Next y E2E con servicios reales temporales. No hay etiquetas humanas reales ni llamadas a embeddings externos: la calidad estadística comercial de V2 sigue inconclusa.

## Estado Git y protección previa

Rama inspeccionada: `develop`. HEAD: `cac56d02c9f07690bc0ed04a96350cb5e8fa3377`. Índice sin conflictos; no archivos eliminados al inicio. Se conservaron los 32 archivos tracked modificados y los archivos nuevos de las fases anteriores. No se creó una rama: no aporta aislamiento al árbol sucio y no se debe simular un punto de release sin commit.

Antes de modificar se guardaron inventario por archivo, estado Git, hashes y un respaldo de código en `/private/tmp/mysecop-rc-preparation-20261116/`. `source-backup.tar.gz` SHA-256: `4d852d8fe5c4935c3514bd0038f4f80ed193928fa5735526f704c005c832292e`. Se verificó cada miembro contra el inventario. Se excluyeron secretos por nombre, persistencia, logs, benchmarks y PNG; ningún archivo original fue eliminado. Los assets públicos tracked sí se incluyen en el paquete final. Inventario inicial: `initial-inventory.json` en ese directorio.

El diff no es íntegramente V2: incluye normalización y UX de fase 1, sincronización 1.1, integración comercial del recálculo 1.2/1.3 y seguridad RC. La base comercial sin cambios forma parte del paquete y se identifica como tal. La clasificación describe contenido, no prueba de autoría o cronología; el manifiesto distingue HEAD, modified y untracked. No se encontró un cambio modificado sin explicación funcional dentro del payload.

## Inventario por fase y alcance

| Grupo | Archivos y función |
|---|---|
| Fase 1 | opportunity_filters/status, filtros/listado/dashboard/alertas, pruebas de ranking/búsqueda y textos de compatibilidad en frontend |
| Fase 1.1 | secop_client, ingest, SyncCursor, 0010, tests incrementales/PG; compatibilidad de upgrades 0003–0008 |
| Fase 1.2 | match_jobs, match_versions, router matches, perfil/recalculo, schemas, progreso frontend, 0011 y pruebas |
| Fase 1.3 | match_execution, match_metrics, metadata de fallos 0012, workers, arneses PG/Redis/E2E y benchmarks separados |
| Fase 2 | compatibility_v2, UNSPSC/catalog53.316, documents/shadow/evaluation, router privado, UI diagnóstico y 0013 |
| Fase 2.1 | evaluation_guard/platform/sampling/semantic/reporting, schemas/router, UI interna, 0014 y pruebas |
| Compartidos | config, modelos, startup, main, tasks, celery_app, fixtures, .env.example; cambios acumulados identificados |
| Comercial preexistente | matcher, embeddings, autenticación, cuotas, licencias, pagos, agentes y páginas restantes de HEAD. Se conserva esta base, sin atribuirla a V2 |
| Correcciones RC | seis consultas de Analysis por propietario; regresiones multiempresa; Next/PostCSS/lockfile; constraints; Dockerignore/Dockerfiles; Gitignore; overlay y preflight offline; generador de paquete/documentos |
| No identificados | Ninguno dentro del payload final; la ausencia de commits históricos por fase impide atribuir autores/hunks con certeza |

El manifiesto lista **todos** los archivos incluidos/excluidos con hash y fase. Los logs, capturas y bases temporales no son código de aplicación ni entran en las imágenes. No se descartaron avances comerciales por considerar que eran ajenos a V2.

## Arquitectura consolidada

SECOP normaliza procesos/contratos con identidad y cursor independientes por fuente, reconcilia por claves y conserva relaciones. OpportunityStatus y filtros compartidos gobiernan vigencia/candidatas. El matching comercial sigue usando el matcher heredado; MatchJob/Slot y versiones rodean ese cálculo con snapshots, lotes, arrendamiento y fencing, manteniendo historial y triage. La cobertura distingue actual, pendiente, obsoleto y fallido.

El diagnóstico V2 y las campañas escriben tablas independientes. Los endpoints internos exigen rol y destino DB/broker/API autorizado, secreto de instalación suficiente e identidad persistida; `production` no está en la allowlist de entornos aunque se activen flags. Las campañas conservan consentimiento, snapshots, revisiones separadas, adjudicación e informe sellado. Las llamadas semánticas están acotadas, presupuestadas y apagadas; sus pruebas de red usan simulaciones.

Colas: `celery` para tareas existentes; `matches` para recálculo y recuperación; `compatibility-shadow` para diagnóstico; `evaluation` para campañas. Broker y result backend se derivan ambos de **REDIS_URL**; definir sólo CELERY_BROKER_URL/CELERY_RESULT_BACKEND no modifica el código actual. No se añade beat para experimentos. El beat existente también programa sincronización/recordatorios: el runbook no lo arranca en el smoke inicial.

Frontend consume los contratos existentes de cobertura/jobs; las dos páginas internas son rutas privadas directas y no aparecen en NAV comercial. Sus componentes se compilan en el frontend, pero la autorización efectiva reside en el backend. Autenticación y suscripciones se mantienen; permisos Pro se verifican en los flujos y tests existentes.

No se detectó un import circular que impidiera importar/iniciar aplicación, workers o migraciones. Se reutilizan los evaluadores y filtros existentes. No se eliminaron módulos por parecer duplicados ni se afirmó una prueba formal de ausencia de código muerto. Persisten adaptadores de rescore heredado para callers existentes; no son razón suficiente para reescribirlos. La prueba y revisión se limitan a este árbol y los escenarios cubiertos.

## Problemas demostrados y correcciones de esta consolidación

1. **Análisis privados sin propietario.** Seis consultas buscaban el último Analysis por oportunidad en detalle, viabilidad, elegibilidad, creación de proyecto, matriz y recordatorios. Ahora también filtran `Analysis.user_id` por actor/destinatario. No se introduce nueva compartición por company_id ni se toca el matcher. Dos casos con empresas distintas, con y sin análisis propio, prueban ausencia de contenido ajeno, entradas del evaluador, checklist/matriz y recordatorios. Es una corrección deliberada de acceso: un usuario deja de ver análisis de terceros que antes podían aparecer. Un análisis histórico sin user_id no se reasigna automáticamente y queda fuera de estas consultas.
2. **Dependencias frontend vulnerables.** npm audit inicial: 1 crítico y 2 altos. Next 15.1.6 → **15.5.29**; PostCSS **8.5.33**, con override de la copia transitiva de Next. El aviso oficial confirma el impacto RSC/App Router: [CVE-2025-66478](https://nextjs.org/blog/CVE-2025-66478); actualización adicional oficial [14 octubre 2026](https://nextjs.org/blog/nextjs-security-update-october-14-2026). El lockfile final deja npm audit en **cero** hallazgos a fecha de consulta. No se migró a Next 16. La resolución transitiva inicial seguía fijada al paquete viejo; se regeneró y se comprobó el árbol, build, instalación npm ci y E2E. No se ejecutaron exploits.
3. **Contextos Docker y dependencias variables.** Backend carecía de Dockerignore, con riesgo de copiar entornos/DB/uploads al hacer COPY. Se excluyeron esos archivos en backend/frontend y persistencia en Gitignore. Frontend usa npm ci y lockfile; backend usa constraints del entorno validado, sin ampliar requirements funcionales. CI queda alineado con constraints/npm ci y TypeScript explícito; no se ejecutó GitHub Actions ni se modificaron workflows de despliegue. No se modificó ningún archivo de secretos. Las constraints no proporcionan hashes de wheels ni resuelven por sí solas todos los paquetes de plataforma.
4. **Consumo de colas.** El compose existente sólo inicia un worker sin -Q; no consume explícitamente las colas nuevas. Se añadió overlay **opt-in** `docker-compose.dev-rc.yml` con cuatro workers y perfiles separados; no se cambió el workflow operativo. Se verificaron estructura YAML, igualdad de entorno y rutas de colas; falta validación con Docker Compose real, ausente en este host.
5. **Preflight y snapshot.** `release_preflight.py` valida configuración sin abrir conexiones ni imprimir valores. Los defaults actuales quedan BLOCKED por SQLite/secreto corto/demo/CORS. `prepare_release_candidate.py` captura el payload con hashes, excluye sensibles/evidencia, aborta ante cambios sin clasificar/conflictos y verifica el archivo creado. No sustituye autorización ni comprobación de propiedad de destinos.

## Migraciones e integridad

Un único head inspeccionado: **0014_evaluation_platform**. Dependencias lineales 0001 → 0002 → … → 0009 → 0010 → 0011 → 0012 → 0013 → 0014. No stamp ni nueva reescritura histórica en esta consolidación.

0001 importa los modelos actuales mediante create_all: por ello una instalación vacía puede contener tablas de fases posteriores antes de llegar a su número de revisión. Las guardias 0003–0008 y las revisiones aditivas posteriores ya existentes evitan duplicaciones. Se conserva esa estrategia compatible y su limitación; una futura migración inicial congelada requeriría proyecto aparte y equivalencia demostrada. Las revisiones aplicadas no se vuelven a ejecutar en una base ya versionada.

Pruebas PostgreSQL actuales: upgrade base vacía hasta 0002 y head; downgrade sólo en base descartable para reproducir columnas ausentes; upgrade de revisión anterior con fila histórica conservada; comparación exacta de columnas, tipos, nulabilidad, PK y presencia de índices/unique/FK de SQLAlchemy; transiciones 0010–0014 y guardias de datos. Se probaron concurrencia, tokens, rollback/pérdida de conexión y relaciones. El resultado describe esos esquemas, no una inspección del DEV real.

Startup continúa teniendo create_all/ALTER históricos para tablas comerciales y shadow; **no** crea automáticamente evaluation_*. Por eso es obligatorio parar procesos antiguos y migrar antes de arrancar aplicaciones, evitando DDL concurrente del startup. No se pretende reemplazar Alembic por startup.

Rollback operativo: conservar tablas/columnas y revertir código/flags. 0011 protege historial/activos; 0012 metadata fallida; 0013 resultados; 0014 cualquier fila, incluida identidad. 0010 por sí sola retira cursores: **no usar downgrade operativo**, ya que pierde checkpoints. No se promete downgrade no destructivo de la cadena completa sobre datos existentes. Tampoco se ejecuta 0001 downgrade sobre datos: usa los modelos actuales. Restauraciones requieren respaldo y autorización propia.

## Validaciones repetidas y evidencia

| Validación | Resultado sobre candidato actual |
|---|---|
| Backend completo, Python 3.12 | **151 passed, 23 skipped, 1.539 warnings** |
| PostgreSQL temporal 16.2 | **14 passed**: 4 sync + 6 matching + 2 shadow + 2 evaluación; 5/364/12/6 warnings |
| Redis/Celery + PG temporales | **8 passed**: 6 operaciones + 1 shadow + 1 evaluación; 32/8/6 warnings |
| Frontend | Build Next 15.5.29 aprobado, 24 páginas; TypeScript tsc --noEmit aprobado |
| E2E combinado | Aprobado: Next/FastAPI/PG/Redis/Celery reales; cuentas/documentos/opiniones sintéticos |
| Dependencias npm | audit inicial 3 → final **0**; npm ci desde lockfile y árbol de paquetes revisado |
| Overlay | YAML y colas/entorno/perfiles comprobados; Docker/Compose no instalado: imagen y config resuelta no verificados |
| Preflight local | **BLOCKED**, esperado; cero conexiones. No es destino operativo autorizado |
| Git / fuentes críticas | diff --check aprobado; matcher/embeddings idénticos a HEAD; core V2 idéntico por SHA-256 a fase 2 |
| Reconstrucción de fuentes | Tar extraído en otro directorio temporal, hashes verificados y backend repetido: **151 passed, 23 skipped, 1.539 warnings**; no depende del código sin seguimiento que quede fuera del paquete |

Las 23 omisiones backend corresponden a 14 PG y 8 Redis ejecutadas con sus runners, más una prueba histórica opt-in Redis/SQLite no ejecutada. Los tests de fallo sólo actúan sobre procesos propios y bases mysecop_test_* del arnés. En un escenario se adelanta el lease descartable para evitar esperar 120s; no se confunde con vencimiento real de reloj operativo. Otros escenarios sí esperan leases reales cortos. Los adaptadores semánticos mockeados no cuentan como proveedor verificado.

E2E: dashboard, perfil, recálculo/cancelación/cobertura, búsqueda/paginación, guardar/descartar sin alterar score, detalle, documento sintético/análisis, proyecto y alertas, diagnóstico V2 y campaña con dos revisores y tercero, sellado/exportación. Incluye escritorio/móvil y ausencia de errores JS; no prueba todas las combinaciones visuales ni servicios de pagos/correo. Premium y flujo integral se ejercitan además en backend. El build respeta la configuración histórica que **omite ESLint**: no se afirma lint aprobado.

Evidencia íntegra: `MYSECOP_COMPATIBILITY_V2_RELEASE_VALIDATION.json` contiene comandos/resultados, hashes de fuentes y logs. Logs/capturas JSON sintético en `/private/tmp/mysecop-rc-preparation-20261116/evidence/`, separados del payload. Las fuentes de backend y QA se alinearon con las mismas constraints antes de repetir integraciones; no se reutilizan como aprobación los resultados históricos de otra dependencia. La reconstrucción reutilizó el venv local validado, no una instalación limpia Python/Linux; npm ci y build limpio también se verificaron, sin ampliar ese resultado a imágenes Docker.

## Advertencias por gravedad

| Nivel | Hallazgo y consecuencia |
|---|---|
| Crítico corregido | Vulnerabilidad Next y lecturas Analysis entre propietarios; parches y regresiones descritos arriba |
| Alto operativo pendiente | Destino, backup, esquema DEV, aislamiento real, secretos y configuración resuelta de contenedores no verificados. Impiden despliegue/aprobación operativa |
| Medio | SAWarning por ciclo FK companies/users; deprecaciones UTC naive, FastAPI on_event, Starlette/httpx y crypt/passlib. Riesgo de futura actualización; no silenciamiento ni refactor comercial en este release |
| Informativo/esperado | Desconexiones/reintentos Redis al provocar fallos, restricción RVM/ps del sandbox y avisos de cache pip. npm ci advierte que Recharts 2.x dejó de recibir mantenimiento; se conserva esa advertencia y no se migra una librería de gráficos sin validación propia. Logs conservados |

No se ejecutó auditoría SCA completa de paquetes Python, imágenes o historial Git. Se identificaron dependencias y se fijaron versiones observadas, pero **no** se declara seguridad universal por npm audit cero. El escaneo local por patrones de credenciales tuvo cero coincidencias de alta confianza; defaults/credenciales ficticias y emails públicos del producto no son secretos operativos nuevos. No se imprimieron archivos de secretos ni URLs empresariales. Si el frontend antiguo estuvo expuesto, la evaluación de exposición y rotación de secretos debe realizarla el operador con autorización; no se investigó producción.

Dependencia opcional detectada: `openai` se importa de forma diferida y no está instalada ni declarada en requirements del RC. No afecta fake/heuristic ni el piloto sin llamadas, pero **el proveedor externo no queda preparado**: antes de una autorización futura necesita dependencia fijada, pruebas reales acotadas y revisión de coste/consentimiento. No se instaló el SDK ni se habilitó como efecto de la consolidación.

## Matriz DEV y seguridad

| Configuración | Requisito para el despliegue futuro |
|---|---|
| ENVIRONMENT | development exacto; nunca reutilizar identidad/volúmenes/credenciales prod |
| DATABASE_URL | PostgreSQL explícito, usuario/base/host revisados; secreto inyectado fuera del código; respaldo previo |
| REDIS_URL | Redis DEV aislado con DB explícita; broker y result backend usan este mismo valor |
| SECRET_KEY | Instalación DEV aleatoria, al menos 32 caracteres, del gestor de secretos; no usar defaults/test fixtures |
| API / frontend | EVALUATION_API_ORIGIN exacto, FRONTEND_URL/CORS_ORIGINS coherentes y NEXT_PUBLIC_API_URL fijado al construir la imagen |
| Workers | celery(1), matches(2), shadow(1), evaluation(1); sólo últimos dos con perfil experiments explícito; límite matching global 2 independiente del número de procesos |
| Matching | MATCH_BATCH_SIZE=200, MATCH_LEASE_SECONDS=300, MATCH_MAX_RETRIES=3; revisar pool SQLAlchemy 10+5 por proceso y conexiones totales |
| Shadow | flag false; muestra máx20, lote5, lease120; no nuevas tareas programadas |
| Evaluación | flag false; universo500, muestra100, retención30 días, lote base5 y semántica1, lease120; expiración lógica, sin borrado físico automático |
| Identidad experimental | EVALUATION_DEV_TARGETS=[] inicialmente; tupla DB/broker/API y UUID persistido sólo tras aprobación y 0014 |
| Consumo externo | EVALUATION_SEMANTIC_ENABLED=false; EVALUATION_EXTERNAL_MAX_CALLS=0; tarifa no definida y maxcost .25 sin llamadas; API key ausente en QA |
| Embeddings/LLM | fake/heuristic para este RC de DEV; no cambiar proveedor/dimensión de datos reales sin plan de invalidación aparte |
| Comercial/comunicaciones | billing manual para DEV, SMTP no habilitado en QA; licenciamiento/pagos de aplicación sin cambios; demo/debug false |

Una allowlist textual no acredita por sí sola que una base es DEV: se necesita verificación operacional de propiedad, destino y marcador. El preflight offline lista lo que no verifica. Los permisos internos se prueban por rol/propietario y flag, con producción rechazada incluso si se habilitan experimental flags. Los vectores se cachean por administrador y propietario original, nunca se retornan al revisor; los consentimientos pueden revocarse. No se usaron documentos reales ni cuentas empresariales. Persisten las limitaciones de pseudonimización, permisos de DBA y retención lógica documentadas en 2.1.

## Criterios de aceptación

| Criterio | Dictamen |
|---|---|
| Código inventariado/sin cambios desconocidos dentro del payload | Aprobado; clasificación funcional y hashes completos |
| Versionado Git RC | **Bloqueado**: requiere autorización de commit/referencia; HEAD es sólo base |
| Migraciones | Aprobado sobre PG aislado; DEV real no verificado |
| Backend / PG / Redis-Celery | Aprobado con omisión histórica y advertencias documentadas |
| Frontend build / TS / E2E | Aprobado local; Node22/Linux/imagen OCI no verificados |
| Endpoints privados y separación experimental | Aprobado en escenarios automatizados; propiedad real del entorno pendiente |
| Configuración y secretos DEV | Documentado; **no verificado** en destino; defaults locales rechazados |
| Ausencia de secretos incluidos | Aprobado con alcance de escaneo declarado; configuraciones excluidas |
| Comportamiento comercial | Regresiones aprobadas, matcher/pesos intactos; acceso a análisis ajenos corregido deliberadamente |
| Runbook y rollback | Preparados; ejecución operativa pendiente |
| Identidad reproducible | Código en tar verificable; Git release e imagen por digest pendientes |
| Preparación global | **Aprobada con restricciones para revisión local; NO aprobado para desplegar todavía** |

## Recomendación final

Revisar el manifiesto y runbook concretos. Una orden posterior deberá autorizar explícitamente el destino DEV y alcance operativo; antes de ejecutar se comprobarán identidad, imagen/Compose en el host, backup restaurable, revisión/schema real y versiones previas. La publicación Git necesita autorización propia y atención al auto-deploy en develop: **no hacer push a develop como simple paso administrativo**. El workflow heredado ejecuta migración con imagen previa al build y arranca beat/worker genérico; no es el procedimiento aprobado para este candidato. No se modificó ni ejecutó ese workflow.

Mantener semántica, shadow y evaluación apagados en la primera puesta en marcha; autorizar después un smoke sintético acotado con identidades internas, sin sincronización masiva. No promover V2 comercial ni afirmar no inferioridad/beneficio estadístico con esta evidencia sintética.
