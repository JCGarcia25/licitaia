# MySECOP Compatibility Engine V2 — Fase 1.2

Fecha: 15 de noviembre de 2026, America/Bogota. Implementación local; sin despliegues, commits ni operaciones productivas.

## 1. Resumen ejecutivo

Se sustituyó el recálculo limitado a 1.500 oportunidades por trabajos persistentes por usuario, paginados por ID, con versiones de entradas, caché verificable de embeddings, cobertura real y recuperación por lote. La fórmula y los pesos de `services/matcher.py` permanecen intactos. No se comparten perfiles ni scores entre usuarios, incluso si pertenecen a la misma empresa.

Resultado: **implementado y probado localmente, pendiente de validación operativa en DEV**. Pasaron 92 pruebas backend y nueve pruebas PostgreSQL por separado. Un worker Celery real procesó mensajes con transporte de memoria. La prueba Redis está preparada pero no se ejecutó porque no hay servidor local disponible. No se certifica capacidad productiva ni rendimiento de millones de oportunidades.

## 2. Estado inicial del repositorio

Inspección documentada antes de modificar código: rama `develop`, HEAD `cac56d0`, head Alembic `0010_sync_cursor`. No se encontró AGENTS.md en el árbol. Había cambios locales de Fase 1/1.1 en migraciones 0003–0008, modelos, ingesta, SECOP, routers, alertas, frontend y pruebas, además de informes y archivos nuevos. Se conservaron; el diff contra HEAD incluye esos avances anteriores.

Hallazgos iniciales:

- `services/matcher.py::score_opportunity` combina semántica, keywords/UNSPSC, departamento, cuantía, modalidad, estado y learning_weights. El flujo `alerts.py::rescore_user` construía el vector del perfil con sector, actividades, productos y keywords, seleccionaba solo 1.500 oportunidades y cargaba todas las asociaciones del usuario. Guardaba score/reasons sin versiones.
- `CompanyProfile` pertenece al usuario; `company_id` no autoriza compartir scores. `UserOpportunity` tiene unique(user_id, opportunity_id) y mezcla score con estados comerciales en una misma fila, sin estado independiente de cálculo.
- PUT profile, POST rescore y preferencias de alertas podían ejecutar scoring síncrono. Dashboard y frontend suponían que POST rescore terminaba el trabajo. Los consumidores no verificaban versiones.
- La búsqueda ya filtraba antes de paginar, con afinidad léxica adicional por lotes para perfil. La ingesta conservaba asociaciones y confirmaba página/cursor juntos, con arrendamiento y renovación. Los embeddings JSON tenían etiqueta de modelo, sin procedencia verificable del texto.
- Celery tenía ingesta, pagos, recordatorios y digest; faltaba un coordinador de matching. `init_db` aún crea tablas y añade columnas al arrancar: esto no sustituye aplicar y verificar Alembic en DEV.

Plan seguido: versiones e historial → trabajos/slots y migración → scoring paginado → consumo común de scores → Celery/API/frontend → pruebas y revisión de rendimiento. Los riesgos identificados fueron carreras, mensajes perdidos, duración de transacciones con proveedores externos, compatibilidad de esquemas y disponibilidad de Redis.

## 3. Arquitectura implementada

Rutas principales:

- `backend/app/services/match_versions.py`: hashes, procedencia de vectores, eventos ORM y condición SQL común `current_score_condition`.
- `backend/app/services/match_jobs.py`: `request_job`, `process_batch`, `coverage`, `cancel_job`, `resume_job`, `job_progress` y publicación `enqueue`.
- `backend/app/db/models.py`: metadatos adicionales de score y modelos `MatchJob`, `MatchSlot`, `MatchScoreHistory`.
- `backend/app/services/opportunity_filters.py`: filtros explícitos reutilizados por búsqueda de perfil, dashboard y alertas.
- `backend/app/workers/tasks.py`: coordinador `rescore_all` y ejecutor `process_match_batch`.

El coordinador detecta trabajo, el ejecutor procesa una página y la transacción del lote confirma scores, historial y progreso juntos. La base conserva el trabajo aunque se pierda un mensaje del broker. El adaptador síncrono `alerts.rescore_user` queda para semillas/CLI y pruebas; las rutas HTTP de matching utilizan trabajos asíncronos.

## 4. Esquema de procesamiento por lotes

`request_job` registra el máximo ID y el universo inicial. Cada lote utiliza `id > cursor_id AND id <= max_id`, elegibilidad centralizada, orden ID ascendente y LIMIT configurable. No hay OFFSET ni un máximo de oportunidades por ejecución. Solo se cargan oportunidades, embeddings y asociaciones del lote; el vector del perfil se conserva dentro del trabajo privado.

Los scores ya vigentes se omiten. Los errores individuales se registran como FAILED sin detener otras filas; un fallo de persistencia revierte todo el lote y su cursor. Una página vacía finaliza recorridos cuyo tamaño es múltiplo del lote. Si hubo cambios por debajo del cursor o nuevas filas por encima de max_id, la cobertura detecta trabajo pendiente y el siguiente recorrido lo procesa.

`candidate_total` y `excluded_total` del trabajo describen el universo inicial. `examined`, `scored`, `skipped`, `failed`, `batches` y cursor son contadores confirmados. La cobertura adjunta describe el universo vivo, que puede variar durante el recorrido; no debe interpretarse el cociente examined/candidate_total como cobertura vigente.

Configuración en `core/config.py` y `.env.example`:

| Variable | Inicial | Control |
|---|---:|---|
| MATCH_BATCH_SIZE | 200 | 1–1.000 filas por lote; nunca limita el universo |
| MATCH_GLOBAL_CONCURRENCY | 2 | 1–16 slots globales en DB |
| MATCH_LEASE_SECONDS | 300 | 10–3.600 segundos; límite temporal por lote |
| MATCH_MAX_RETRIES | 3 | 1–10 fallos de lote antes de intervención |
| MATCH_ALGORITHM_VERSION | heuristic-v1-phase12 | revisión explícita, combinada con hash de código |

## 5. Modelo de versionado

SHA-256 de JSON determinista permite comparar entradas sin copiar perfiles completos en cada score. Se guardan profile_version, opportunity_version, algorithm_version, embedding_version, scored_at y match_error, además de match_state. Las versiones nulas de scores preexistentes no se consideran verificadas.

- Perfil: campos consumidos por el matcher o por el texto semántico heredado, incluido learning_weights. Nombres comerciales, NIT, certificaciones y otros campos ajenos al cálculo no invalidan el score. Municipios afectan filtros de presentación, no la fórmula.
- Oportunidad: campos del matcher y campos que afectan vigencia/procedencia. Entidad, enlaces y raw_json sin cambio relevante no invalidan. Cambios de vector/modelo/procedencia sí invalidan.
- Algoritmo: hash del archivo del matcher y revisión configurable. Es conservador: un cambio de código, incluso sin efecto matemático, puede invalidar resultados.
- Embeddings: proveedor efectivo, modelo, dimensión y hash de implementación. Se distingue el fallback fake del proveedor OpenAI efectivo. La configuración actual OpenAI utiliza text-embedding-3-small con dimensión 1.536; fake utiliza EMBEDDING_DIM.
- `OpportunityEmbedding.content_version` identifica el texto contractual. Una etiqueta de modelo y dimensión correctas no bastan si cambió ese texto. Vectores antiguos sin procedencia se regeneran; la caché pública se reutiliza posteriormente entre usuarios, mientras sus scores y el vector del perfil permanecen privados.

Estados efectivos: PENDING, CURRENT, STALE, FAILED. CALCULATING se usa dentro de la transacción de cálculo; el trabajo RUNNING es la evidencia visible de actividad, sin publicar un score no confirmado. STALE se deriva al leer comparando versiones, sin una actualización masiva de todas las asociaciones. Antes de sobrescribir un score existente se conserva valor, razones y versiones en MatchScoreHistory. Un fallo de recálculo no elimina el último valor.

## 6. Reglas de invalidación

Un evento SQLAlchemy before_flush, registrado desde modelos, actualiza versiones dentro de la misma transacción del perfil, oportunidad o embedding. Cubre PUT profile, feedback que cambia learning_weights, ingesta y otras modificaciones ORM. Una transacción revertida no invalida datos confirmados.

Las comparaciones SQL hacen inmediatamente invisible una cifra obsoleta después del commit. PUT profile crea/publica un trabajo después de confirmar los datos. Para cambios de oportunidades o mensajes perdidos, el coordinador periódico consulta versiones y cobertura de datos confirmados: no depende de una notificación efímera de ingesta ni hace fanout dentro de su transacción.

El ejecutor bloquea perfil, oportunidades y embeddings del lote. Una edición concurrente espera o provoca recuperación de la transacción; después de confirmarse, las versiones impiden publicar scores viejos. Un cambio de perfil entre lotes termina el trabajo como SUPERSEDED; el coordinador prepara el siguiente. Cambios de oportunidad detrás del cursor se recuperan en un recorrido posterior.

Limitación: SQL directo, query.update o mutaciones JSON en sitio que no notifique SQLAlchemy deben actualizar versiones explícitamente. No se instalaron triggers universales; las rutas de escritura existentes revisadas usan asignaciones ORM.

## 7. Cálculo de cobertura

`coverage` ejecuta un agregado SQL único para obtener categorías coherentes sobre una misma lectura: universo total, candidatas, CURRENT, FAILED con entradas aún coincidentes y STALE. PENDING se obtiene por diferencia. Las categorías son excluyentes.

Cobertura = 100 × current_scores / candidate_total. Sin candidatas devuelve null y NO_CANDIDATES. Incluye measured_at y criterion. No inventa 100%, scores ni compatibilidades.

El universo candidato usa `potentially_current_condition`: excluye contratos SECOP II, registros SECOP I, cancelados, terminales conocidos, publicaciones futuras y cierres pasados. UNKNOWN no demuestra apertura; conserva la política conservadora existente. La cobertura mide todas las candidatas públicas por perfil, incluidas las que el usuario haya descartado; los consumidores respetan el triage y no las recomiendan. Los filtros geográficos, de modalidad, cuantía, relevancia y gestión de la pantalla pueden reducir el conjunto mostrado sin cambiar esta definición de cobertura.

## 8. Integración con Celery

Cola `matches`, tareas `app.workers.tasks.process_match_batch` y `rescore_all_task`. El ejecutor publica la siguiente página solo después de commit. Reintentos de fallo de lote tienen espera exponencial acotada y contador durable. acks_late, reject_on_worker_lost, prefetch 1 y límites soft/hard por lote ayudan a recuperar interrupciones. Las publicaciones de matching no tienen fallback síncrono.

Beat ejecuta recuperación cada 60 segundos. El coordinador recorre perfiles por claves en páginas de 200 y continúa mediante otra tarea. Recupera PENDING/RETRY/RUNNING vencidos y crea trabajo para cobertura pendiente/desactualizada. FAILED requiere reanudación explícita. La cancelación se respeta para las mismas versiones del perfil/algoritmo/embeddings hasta nueva solicitud o cambio de esas versiones.

`celery_app.py` declara ambas colas, de modo que el worker existente puede consumir matching. Para separar recursos en DEV se recomienda un worker de matching con `-Q matches --concurrency=2 --prefetch-multiplier=1` y el worker general con `-Q celery`. No se arrancaron servicios de la aplicación ni se modificó su despliegue.

Se corrigió la construcción existente de crontab: la zona horaria se define en la aplicación Celery, no como argumento del cron. Se verificó que Celery queda disponible. Un worker real con transporte memory completó múltiples lotes y una entrega duplicada. **Redis real sigue pendiente**, con prueba opt-in `tests/test_match_celery.py` que acepta únicamente un socket temporal identificado como mysecop-test-redis-*/redis.sock mediante MYSECOP_TEST_REDIS_URL.

## 9. Manejo de concurrencia

Un active_key único por usuario y el bloqueo de su perfil impiden dos trabajos activos para ese usuario. Los slots compartidos en DB imponen el límite global incluso con múltiples workers. La adquisición usa actualizaciones condicionales, token UUID y vencimiento. El lote bloquea slot y trabajo en orden fijo; una ejecución sin token no confirma progreso. El límite se renueva al adquirir cada lote, y el fencing comprueba vencimiento antes de commit.

No hay heartbeat independiente durante un lote de matching: el límite temporal de Celery y el tamaño del lote deben mantenerlo por debajo del arrendamiento. Si vence, se revierte y reintenta. Un worker muerto deja el último cursor confirmado; el coordinador puede retomarlo tras el vencimiento. Los relojes de hosts deben mantenerse sincronizados.

La cancelación ocurre en un límite de transacción: puede esperar a que termine el lote activo. No mata conexiones ni borra scores. Si ocurre entre adquisición y procesamiento, el slot puede quedar reservado hasta que el ejecutor lo libere o venza. Compartir empresa no comparte scores ni concede control de trabajos ajenos.

## 10. Cambios de API

| Ruta | Comportamiento |
|---|---|
| POST /api/rescore | HTTP 202, crea/deduplica trabajo del usuario; devuelve ID, progreso y cobertura |
| GET /api/match-jobs/current | último trabajo propio o null |
| GET /api/match-jobs/{id} | progreso propio; trabajo ajeno responde 404 |
| POST /api/match-jobs/{id}/cancel | cancelación propia en límite de lote |
| POST /api/match-jobs/{id}/resume | HTTP 202; reanuda fallos o inicia nuevo recorrido si el anterior terminó/canceló |
| GET /api/matches/coverage | cobertura privada del usuario autenticado |

Contratos Pydantic en `schemas.py`: MatchCoverageOut y MatchJobOut. Router nuevo `routers/matches.py`, registrado en main.py. No se acepta identidad empresarial/usuario del cliente para seleccionar los scores. El vector privado del trabajo no se expone.

Búsqueda general, búsqueda por perfil, dashboard, alertas y ambos digests usan la condición de score vigente. Si no está vigente, la API devuelve score null y reasons vacías, manteniendo los valores históricos en DB. Incluye score_state para distinguir el motivo. Los filtros de score se aplican en SQL antes de contar/paginar. Perfil conserva orden por score e ID, y afinidad léxica antes de paginar. Guardadas/proyectos no omiten filtros explícitos; descartadas solo aparecen cuando se solicitan y no generan recomendaciones de alta compatibilidad.

POST /api/rescore cambia el contrato síncrono anterior: los clientes externos que esperaban puntuadas/alertas_creadas deben migrar a consultar progreso. El frontend del repositorio y las pruebas se adaptaron. PUT profile conserva su respuesta de perfil, con scoring programado.

## 11. Cambios de frontend

`frontend/components/match-progress.tsx` muestra cobertura y sus categorías, inicia, cancela y reintenta trabajos; consulta progreso cada cinco segundos y actualiza resultados cuando cambia. Se integra en dashboard y Oportunidades. El dashboard deja de asumir un recálculo inmediato cuando no hay resultados. Lista y detalle distinguen scores desactualizados/fallidos/pendientes sin publicar cifras viejas.

TypeScript `tsc --noEmit` aprobado. No se ejecutó una sesión visual de navegador ni una prueba E2E completa de frontend; esa validación permanece pendiente en DEV. No se cambiaron páginas comerciales ni licencias.

## 12. Migraciones

Nueva `backend/alembic/versions/0011_match_jobs.py`, dependiente de 0010. Agrega versiones nullable a perfiles, oportunidades, embeddings y asociaciones, más tablas de trabajos, slots e historial. No borra oportunidades, asociaciones ni valores anteriores de score. Las versiones desconocidas quedan pendientes/desactualizadas hasta un cálculo verificable.

Se conserva compatibilidad con el create_all histórico: no duplica columnas/tablas ya presentes. No se reescribieron nuevamente 0003–0008. Se verificó correspondencia del esquema con modelos en PostgreSQL y un solo head: 0011_match_jobs. Se probó instalación vacía, downgrade a 0010 y upgrade desde ese esquema con usuario, perfil, oportunidad y score/triage previos conservados, sin stamp.

El downgrade de 0011 funciona sobre esquema sin trabajos activos ni historial. Rechaza la operación si encuentra historial o trabajos activos para evitar pérdidas. No convierte una tabla preexistente incompatible en un esquema correcto; inspeccionar copias reales antes de promoción.

Índices: PK de oportunidad para keyset, unique(user_id, opportunity_id) existente para scores, PK para slots y unique(active_key) para exclusión. Se agregó ix_match_jobs_user_id para consultas privadas de progreso. No se agregaron índices especulativos en scores/historial. La integración ejecuta EXPLAIN sobre la consulta keyset; el volumen pequeño de esa instancia no decide índices para producción.

## 13. Resultados de pruebas

| Validación | Resultado comprobado |
|---|---|
| Suite backend completa | 92 aprobadas, 10 omitidas, 1.389 advertencias; 21,08 s |
| PostgreSQL Fase 1.1 | 4 aprobadas, 5 advertencias |
| PostgreSQL Fase 1.2 | 5 aprobadas, 252 advertencias |
| Celery real, broker memory | aprobado dentro de la suite; entrega duplicada y múltiples lotes |
| Redis real | omitido: servidor ausente; prueba preparada |
| TypeScript | tsc --noEmit aprobado |
| SQLite Alembic | vacío → head → 0010 → head aprobado, sin stamp |
| Fórmula del matcher | git diff vacío para matcher.py |

Las diez omisiones son nueve pruebas PostgreSQL opt-in, ejecutadas por separado en bases vacías diferentes, y una Redis no ejecutada. PostgreSQL 16.2 provino del venv temporal existente `/tmp/mysecop-audit-venv`; no se instalaron servicios globales ni paquetes adicionales. El servidor se detuvo al finalizar; los directorios temporales se conservan. No se utilizaron bases empresariales.

Casos probados: 0, 17, 1.601 y 10.000 candidatas; cobertura parcial/completa; fallos individuales; idempotencia; reanudación; rollback antes de confirmar; interrupción de lote; dos ejecutores; slots globales entre usuarios; vencimiento; agotamiento de reintentos; perfil y oportunidad modificados durante un lote PostgreSQL; pg_terminate_backend y recuperación; cambio de modelo/dimensiones/texto de embeddings; historial y relaciones guardadas; seguridad entre usuarios de la misma y distintas empresas; scores obsoletos ocultos; descartadas coherentes; regresiones de análisis, ofertas, dashboard, alertas, búsqueda, perfiles y suscripciones Premium.

Las pruebas de concurrencia/transacciones usan PostgreSQL real, con matcher/vectores simulados. Las regresiones generales también ejercitan el matcher heurístico y embeddings fake reales. La ingesta de prueba usa fuentes simuladas. No se consultó ni sincronizó masivamente SECOP durante esta fase.

Logs completos, sin filtros de advertencias:

- `/tmp/mysecop-phase12-backend-final.log`
- `/tmp/mysecop-phase12-postgres-final.log`
- `/tmp/mysecop-phase12-benchmark.log`
- `/tmp/mysecop-phase12-celery.log` (ejecución focal previa, además del caso repetido en la suite final).

Persisten deprecaciones de fechas/FastAPI/httpx/crypt, clave JWT corta de fixtures y ciclo FK companies/users. No se ocultaron ni se presentan como advertencias resueltas. La cantidad mayor refleja, entre otros factores, más ejecuciones de la regla central de vigencia dentro de las pruebas nuevas.

Reproducción:

```bash
cd backend
.venv/bin/python -m pytest -q
/tmp/mysecop-audit-venv/bin/python scripts/test_isolated_postgresql.py
```

El segundo comando exige el venv temporal con pgserver/controlador y permisos locales para arrancarlo. Crea dos bases mysecop_test_* diferentes y ejecuta ambas suites. Alternativamente, proporcionar MYSECOP_TEST_POSTGRES_URL a cada módulo por separado, siempre en una base descartable vacía distinta. Los fixtures aplican migraciones y modifican esa base.

## 14. Métricas de rendimiento

Smoke test local con SQLite, lotes de 200, matcher de prueba y vectores de cuatro dimensiones:

| Candidatas | Tiempo de recorrido/validación | Lotes |
|---:|---:|---:|
| 0 | 0,022 s | 1 |
| 17 | 0,025 s | 1 |
| 1.601 | 0,288 s | 9 |
| 10.000 | 1,650 s | 51 |

No incluye la construcción inicial del fixture en el tiempo de recorrido. El pico RSS del proceso completo de prueba fue 148.652.032 bytes, incluyendo fixtures y pytest; no mide memoria exclusiva del motor. El lote tuvo entre 4 y 7 SELECT, sin crecimiento por oportunidad. En SQLite se observaron hasta 409 sentencias totales por lote de 200, incluyendo inserts con RETURNING y actualizaciones: la persistencia ORM todavía requiere optimización para volúmenes mayores. Hay una prueba que limita las lecturas de un lote de 200 a menos de 20 para detectar N+1.

Cada trabajo registra tiempo acumulado de procesamiento, tiempo del último lote, consultas del lote y pico RSS del proceso. Logs JSON incluyen job_id, contadores, segundos, lecturas, sentencias y throughput. El contador de consultas llega hasta flush de scores; excluye adquisición del lease y el último commit/registro de métricas. Los timestamps permiten medir espera/antigüedad, sin prometer un monitor de lag ya agregado. No se registran perfiles ni vectores en los logs nuevos.

No son benchmarks del matcher productivo, OpenAI, Redis ni de PostgreSQL con millones de filas. Falta medir anchura real de registros, coste de embeddings, contención de pools y planes de cobertura. El vector del perfil se genera una vez por trabajo; el contractual se almacena por modelo y texto para evitar repetir llamadas innecesarias entre usuarios.

## 15. Riesgos pendientes

1. Redis real, reinicio de worker prefork, caída completa del broker/servidor y recuperación distribuida requieren DEV. El transporte memory no valida Redis.
2. Los locks se mantienen durante el scoring del lote, incluidas llamadas al proveedor. Ajustar lote/timeout según latencias reales; no garantizar 200 filas por lote si el proveedor demora más que el arrendamiento.
3. Cobertura y ranking léxico pueden recorrer universos grandes en SQL/streaming; memoria acotada no significa coste constante de CPU/DB. El coordinador mide cobertura por perfil y aún no tiene un índice materializado de invalidaciones.
4. La marca temporal utiliza el reloj del host. Sincronizar hosts y revisar duraciones de leases en DEV.
5. Las escrituras fuera de eventos ORM o mutaciones JSON no detectadas requieren invalidación explícita. No hay garantía frente a cambios administrativos por SQL sin ese contrato.
6. El historial crece sin política de retención; no se elimina automáticamente. Una retención futura requiere requisitos y autorización.
7. El frontend está comprobado con TypeScript y contrato backend, sin QA visual/E2E. Los clientes externos deben adoptar el HTTP 202.
8. El matcher heredado conserva sus limitaciones matemáticas; esta fase no añade un modelo predictivo ni certifica probabilidades.
9. Continúan los límites conocidos de cobertura incremental SECOP de Fase 1.1 y la necesidad de verificar el esquema real de DEV. No se certifica producción.

## 16. Procedimiento de validación en DEV

1. Revisar el diff distinguiendo cambios previos y Fase 1.2; mantener respaldos y una copia PostgreSQL aislada. Verificar base/host antes de migrar.
2. Detener workers de esa copia, aplicar Alembic hasta 0011 y comparar tablas, columnas y restricciones. Verificar que scores anteriores permanezcan almacenados pero no aparezcan como CURRENT sin versiones.
3. Configurar límites homogéneos en API/beat/workers. Arrancar Redis descartable, beat y worker de cola matches; ejecutar la prueba Redis preparada por socket temporal. No utilizar el Redis compartido/productivo.
4. Crear dos usuarios/empresas de prueba y probar inicio, progreso, cancelación y reanudación, comprobando 404 en accesos ajenos y preservación de guardadas/descartadas/proyectos.
5. Probar cambio de perfil y de oportunidad durante trabajo; cortar un worker y reconectar DB/broker. Verificar cursor, reintentos, slots y consistencia de cobertura con consultas independientes.
6. Hacer QA visual de dashboard, lista, detalle y alertas: ningún score obsoleto visible como vigente, filtros conservados, panel de cobertura y actualización progresiva.
7. Medir lotes con datos representativos anonimizados y planes EXPLAIN ANALYZE de cobertura/ranking. Elegir lote/concurrencia según presupuesto de conexiones y latencia; no iniciar cargas masivas ni fuentes externas sin alcance definido.

Este procedimiento se documenta; no se ejecutó un despliegue DEV durante la tarea.

## 17. Procedimiento de rollback

Detener beat y workers de matching y terminar/cancelar trabajos en un límite de transacción. Respaldar base e historial. Revertir conjuntamente frontend/backend a una revisión conocida, conservando por defecto el esquema aditivo y el historial: esto permite mantener scores y relaciones sin borrar datos.

Solo en copia descartable sin historial/trabajos activos se verificó downgrade de 0011 a 0010 y nuevo upgrade. La migración rechaza retirar el esquema si perdería historial; no quitar la guarda ni borrar filas para forzarla. Si se requiere retirar físicamente el esquema con datos, diseñar y verificar primero una exportación/restauración que preserve también vectores privados y metadatos de trabajos. El rollback de código no restaura automáticamente scores anteriores: su recuperación requiere historial/respaldo.

No ejecutar downgrades históricos para instalar esta fase en una base empresarial. No usar stamp como sustituto de migraciones. No se ejecutó rollback sobre datos reales.

## 18. Matriz de criterios de aceptación

| Criterio | Estado | Evidencia/límite |
|---|---|---|
| 1. Sin límite arbitrario de 1.500 | Comprobado local | 1.601 y 10.000 simuladas; recorrido completo |
| 2. Lotes y reanudación | Comprobado local | cursor/commit por lote; interrupción y conexión PG |
| 3. Control de concurrencia | Comprobado local | unique activo, slots, dos workers PG; Redis distribuido pendiente |
| 4. Versiones verificables | Comprobado local | perfil, oportunidad, algoritmo, proveedor/modelo/dimensión/texto/vector |
| 5. Invalidación relevante | Comprobado local | ORM y comparación SQL; escrituras externas requieren contrato explícito |
| 6. Cobertura medible | Comprobado local | agregado único, categorías disjuntas, cero → null |
| 7. API/interfaz sin scores obsoletos actuales | Implementado; QA parcial | tests API, TypeScript; navegador E2E pendiente |
| 8. Dashboard/alertas coherentes | Comprobado en backend | condición/filtros comunes, descartadas y digests; visual pendiente |
| 9. Estados y asociaciones conservados | Comprobado local | triage, feedback, proyectos/regresiones e historial PG |
| 10. Regresiones aprobadas | Comprobado local | 92 backend y nueve PG separados; Redis omitido |
| 11. Recuperación documentada | Completo | leases, reintentos, cancelación, DEV y rollback |
| 12. Sin cambios destructivos | Comprobado en alcance local | esquema aditivo, downgrade con guarda; sin producción/despliegue/commit |

La implementación no equivale a validación productiva. Redis y QA visual/E2E impiden declarar terminada su validación operativa integral.

## 19. Recomendaciones para la Fase 1.3

Validar Redis/prefork y observabilidad de cola en DEV; medir proveedor de embeddings y pools; convertir persistencia por fila en escrituras agrupadas donde conserve historial y versiones; evaluar un registro durable de invalidaciones para reducir barridos de cobertura por perfil; diseñar retención/consulta de historial; completar pruebas visuales y de larga duración. Mantener el matcher matemático sin cambios hasta disponer de criterios verificables y datos etiquetados para la fase correspondiente.

No migrar a perfiles compartidos por empresa en esta fase. Un diseño futuro deberá especificar consentimiento, permisos de miembros, versión del perfil organizacional y separación entre score compartido y triage privado antes de reutilizar resultados entre usuarios.
