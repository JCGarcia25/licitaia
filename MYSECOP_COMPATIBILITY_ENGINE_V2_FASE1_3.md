# MySECOP Compatibility Engine V2 — Fase 1.3

Fecha: **15 de noviembre de 2026**, America/Bogota. Alcance: implementación local, datos sintéticos y servicios descartables. Sin despliegues, commits ni operaciones productivas.

## 1. Resumen ejecutivo

Se estabilizó el motor con preparación de snapshot, cálculo sin conexión/transacción de escritura y confirmación breve con versiones y fencing. Se agregaron renovación de leases, persistencia agrupada, cobertura mediante joins, métricas privadas, separación de intentos fallidos, QA funcional y evaluación reproducible de ranking. **No se modificó la fórmula ni los pesos del matcher.**

Resultado: **implementado y validado técnicamente en el alcance local descrito; apto para validación controlada en DEV**. La validación no certifica producción, OpenAI, calidad de recomendación ni resultados sobre datos empresariales reales.

Evidencia: 105 pruebas backend aprobadas; diez PostgreSQL por separado; seis Redis/Celery con servicios reales aislados; E2E Chromium sobre Next/FastAPI/PostgreSQL/Redis, escritorio y móvil; TypeScript aprobado. Los seis benchmarks sintéticos cumplieron presupuestos fijados antes de medir. La calidad estadística real queda **pendiente de etiquetas humanas**, con plantillas, protocolo, CLI y pruebas matemáticas preparados.

## 2. Estado inicial

Auditoría escrita antes de modificar: rama `develop`, HEAD `cac56d0`, head Alembic `0011_match_jobs`. Había cambios locales de fases 1–1.2 en modelos, ingesta, routers, frontend, migraciones históricas y pruebas, además de archivos sin seguimiento. Se conservaron. El diff contra HEAD incluye esas fases y no debe atribuirse íntegramente a Fase 1.3.

MatchJob, MatchSlot, MatchScoreHistory, versiones y endpoints privados ya existían. El ejecutor mantenía FOR UPDATE sobre trabajo, slot, perfil, oportunidades y embeddings mientras calculaba y esperaba proveedores. Cobertura repetía subconsultas correlacionadas. El panel tenía polling básico. El feedback existente era binario y no constituía juicios de relevancia 0–3 independientes del algoritmo. No había Redis ni navegador en PATH; sí un venv temporal con PostgreSQL y dependencias backend.

Plan ejecutado: separar cálculo/confirmación → carreras e integridad → servicios Redis/Celery reales → consultas/benchmarks → métricas privadas → QA frontend → instrumentos estadísticos y regresiones. No se reimplementaron componentes que ya funcionaban.

## 3. Arquitectura final

`services/match_jobs.py::process_batch` delega en `services/match_execution.py`:

1. Adquirir slot y trabajo con token/vencimiento y confirmar esa reserva.
2. `prepare`: leer perfil, página estable, vectores y scores vigentes; copiar entradas y versiones; cerrar la transacción y devolver la conexión.
3. `calculate`: generar/reutilizar embeddings y ejecutar el matcher fuera de una transacción de escritura. Un heartbeat independiente renueva la reserva.
4. `_confirm`: bloquear brevemente slot, trabajo, perfil, oportunidades y vectores; validar titularidad, vencimiento, cursor, versiones y elegibilidad; escribir scores, historial y progreso atómicamente.

El snapshot es optimista: su coherencia se comprueba nuevamente al confirmar. No se afirma aislamiento REPEATABLE READ. Una edición de perfil/modelo deja SUPERSEDED el trabajo; una oportunidad modificada rechaza el lote sin avanzar y permite nueva lectura. Vectores generados concurrentemente se aceptan únicamente si su contenido/versiones coinciden exactamente con los usados; no se etiquetan resultados con entradas diferentes.

La ingesta incremental, el aislamiento por usuario y los estados comerciales se conservan. No se introdujeron nuevas bases de datos ni servicios productivos.

## 4. Validación Redis/Celery

Ejecutor: `backend/scripts/test_isolated_phase13.py`. Suite: `tests/test_redis_operations.py`. Worker de inyección de fallos exclusivo de pruebas: `tests/isolated_match_worker.py`; no se registra en la aplicación productiva.

Se utilizó Redis real incluido por redislite en el venv temporal, por socket Unix privado, con AOF, PostgreSQL descartable y Celery con `--pool=prefork --concurrency=2`. En macOS los hijos se muestran como SpawnPoolWorker; esto no equivale a validar el arranque fork de Linux.

**Seis pruebas aprobadas, 32 advertencias, 44,63 s**, cubriendo:

- Trabajo completo, dos usuarios simultáneos y dos solicitudes concurrentes del mismo usuario.
- Entregas duplicadas: sin duplicar scores ni historial confirmado.
- Cancelación durante espera de proveedor y reinicio warm del worker.
- SIGKILL del grupo de procesos propio, reinicio y vencimiento real del lease de diez segundos, seguido de recuperación desde DB.
- Redis detenido, publicación fallida, reinicio del broker, reconexión y recuperación de PENDING por coordinador.
- Tres fallos de confirmación, FAILED, reanudación y fallo individual de proveedor.

Redis y workers fueron reales. Los fallos del proveedor y de persistencia fueron inyectados mediante archivos locales de control en el worker de pruebas. No se llamó a una API externa. Solo se detuvieron procesos creados por el arnés. Los directorios de evidencia permanecen disponibles; no se limpiaron bases empresariales.

El transporte memory sigue teniendo su regresión propia, pero **no se usa como sustituto de esta evidencia Redis**.

## 5. Optimización transaccional

Las llamadas costosas no conservan locks de perfiles u oportunidades ni una conexión del cálculo. La reserva no es un lock prolongado: es una fila con token/vencimiento renovada por otra sesión con transacciones cortas.

Pruebas PostgreSQL exigieron que un escritor terminara antes de liberar el cálculo bloqueado; los resultados de ese snapshot no se confirmaron. También se probaron pérdida de token, cambio de revisión del algoritmo durante cálculo, renovación solo del propietario, fallo al persistir, interrupción y pérdida de conexión. Una confirmación cuyo acuse falla se reconcilia con el estado durable; redelivery no vuelve a insertar historial ya confirmado.

La cancelación puede confirmarse durante el cálculo. El ejecutor libera solamente su propio slot mediante comparación de token, sin liberar una reserva de otro worker. Las actualizaciones breves de confirmación pueden esperar otros escritores; no se garantiza ausencia total de contención. La generación de embeddings durante ingesta SECOP conserva su comportamiento previo y no fue rediseñada en esta fase.

## 6. Optimización PostgreSQL

Scores nuevos, actualizaciones e historial usan operaciones agrupadas SQLAlchemy, preservando triage, feedback, IDs y relaciones. Los embeddings se cargan por página, evitando lazy SELECT por oportunidad. La cobertura reemplaza EXISTS repetidos por joins y un agregado consistente con categorías excluyentes. Sigue sin existir un límite total de oportunidades ni OFFSET en el recorrido del motor.

Se ejecutaron EXPLAIN y EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) sobre bases descartables. Planes completos: `backend/benchmarks/phase13/plans-*.json`. En 50.000 registros/10 usuarios se observó:

- Candidatos: Index Scan por PK y Limit.
- Ranking: joins y Sort de resultados del usuario; se mantienen los índices existentes.
- Cobertura: agregado con joins y recorrido de oportunidades; no se promete coste constante con el universo.
- Scores vigentes y filtros: uso de índices existentes.
- Trabajos, slots e historial: Seq Scan en tablas pequeñas o vacías. Esa evidencia no justifica índices adicionales ni demuestra rendimiento de un historial grande.

No se añadieron índices especulativos. Se conservan PK, unique(user_id, opportunity_id), unique(active_key) e índice de usuario del trabajo. El benchmark fija pool 4, sin overflow, y dos ejecutores; el máximo observado fue dos conexiones y no hubo timeouts de pool. Los defaults de conexión de la aplicación permanecen como en Fase 1.2 y deben dimensionarse por proceso en DEV.

## 7. Métricas operativas

Nuevo `GET /api/matches/metrics`, autenticado y limitado al usuario, en `routers/matches.py` y `services/match_metrics.py`:

- PENDING/RETRY, RUNNING, FAILED y RUNNING con reserva vencida.
- Antigüedad del pendiente más antiguo, segundos registrados, lotes confirmados y relación de tiempo registrado por lote.
- Reintentos y errores de matching por clase, errores de sincronización del propio usuario.
- Cobertura vigente, pendientes, desactualizados y fallidos.
- Antigüedad de sincronizaciones propias y último éxito/edad por fuente pública de SyncCursor, sin tokens ni auditorías de otros usuarios.

Logs JSON incluyen job_id, duración de preparación/cálculo/confirmación, lecturas, sentencias y filas del lote. Los errores nuevos registran clase y componente, sin mensajes externos, perfiles, tokens ni vectores privados. Las duraciones persistidas alcanzan la preparación del commit; los logs incluyen el acuse del commit. El promedio basado en contadores confirmados es una medida operativa, no latencia de cola ni una distribución de todos los intentos abortados.

La cobertura no redondea a 100% si resta alguna candidata: el caso 49.999/50.000 devuelve 99,99 a dos decimales. Con cero candidatas sigue devolviendo null, sin inventar 100%.

## 8. QA frontend

Se ejecutó `backend/scripts/e2e_phase13.py` con Chromium temporal y aplicación local real: Next.js en desarrollo, FastAPI, PostgreSQL, Redis y worker Celery, usando usuario Pro, documentos y oportunidades sintéticos.

Comprobado en E2E:

- Login, dashboard, perfil y aviso de recomendaciones pendientes.
- Inicio, progreso real, cancelación y nuevo recorrido autorizado.
- Cambio de perfil con cálculo detenido; score anterior oculto como STALE.
- Cero pendientes antes de mostrar cobertura completa.
- Filtro sin resultados mantiene lo escrito; paginación posterior conserva contexto.
- Guardar y descartar desde la segunda página sin cambiar scores.
- Listado y detalle; creación de propuesta y relación conservada.
- Subida explícita del DOCX, análisis real con parser heurístico y navegación a Ofertas/Alertas.
- Sin excepciones de página registradas; viewport de 390 px sin overflow horizontal.

Se corrigió el polling inicial bajo React StrictMode y se evitan respuestas antiguas que sobrescriban una acción nueva. Se restauró el control de guardar en la lista; el botón de análisis se deshabilita cuando faltan documentos, hay archivos aún sin subir o existe una operación en curso. Los textos llaman compatibilidad al score, no probabilidad.

TypeScript aprobado. Se revisaron visualmente las capturas de escritorio y móvil. No se hizo un rediseño ni se validaron todos los navegadores, accesibilidad completa, dispositivos físicos o build productivo.

Evidencia: `backend/benchmarks/phase13/e2e-result.json`, `e2e-dashboard.png`, `e2e-oportunidades.png`, `e2e-mobile.png`. El usuario y la suscripción mostrados son fixtures, no cuentas reales.

## 9. Seguridad y aislamiento

Se conservan perfiles por usuario y scores privados incluso dentro de la misma empresa. Las rutas de inicio, progreso, cancelación, reanudación, cobertura y métricas requieren autenticación. Trabajos ajenos responden 404; no se acepta un user_id del cuerpo para cambiar de propietario. Los tests incluyen dos usuarios de una empresa y otra empresa, manipulación de identificadores y todas las rutas nuevas sin autorización.

No se exponen profile_vector ni perfiles empresariales en el contrato de trabajos. Las métricas de otro usuario no aparecen en los agregados propios. Los vectores de oportunidades públicas pueden reutilizarse; eso no comparte scores, triage ni el vector empresarial. No se cambió autenticación, pagos, licenciamiento ni el modelo organizacional.

## 10. Línea base estadística

Implementado `services/ranking_evaluation.py::evaluate` y CLI `scripts/evaluate_ranking.py`, con protocolo y plantillas en `backend/evaluation/`.

Las anotaciones se entregan a ciegas, sin el score: perfil anonimizado, referencia pública/texto anonimizado, estado/vigencia, relevancia 0–3, motivo, evaluador pseudónimo, fecha y versiones de las entradas. Predicciones y orden servido se registran por separado. No se exportaron datos empresariales ni se inventaron etiquetas humanas.

Definiciones:

- Relevante = etiquetas 2 o 3.
- Precision@5/@10 usa denominador k; plazas no devueltas no reciben crédito. Si un resultado devuelto no fue juzgado, la precisión correspondiente es null.
- Recall@20 y NDCG@10 requieren universo de referencia completamente etiquetado y ranking completo declarado. Recall sin relevantes e IDCG cero producen null.
- NDCG utiliza ganancia 2^relevancia−1 y descuento log2(posición+1).
- FPR = FP/(FP+TN), positivo = score >= umbral predefinido. Exige scores de todo el universo y negativos etiquetados.
- Cobertura de evaluación = fracción etiquetada del universo declarado. Se entregan macro promedios por consulta/sector y cantidad de consultas que contribuyen a cada métrica.
- Se valida ausencia de duplicados, scores finitos 0–100, escala de etiquetas y versiones compatibles. El rank explícito preserva el orden servido; sin él se usa score descendente e ID descendente, numérico cuando corresponde.

Las etiquetas sintéticas existen únicamente en pruebas matemáticas; el CLI no las acepta como humanas. `evaluation/baseline-status.json` declara **PENDING_HUMAN_LABELS**, cero juicios humanos y métricas de calidad null. La cobertura cero de la plantilla no es una medición de una población real. Feedback binario, guardadas y descartadas no se convierten automáticamente en etiquetas.

El universo de referencia debe justificarse; declarar un pool sesgado como completo no produce Recall válido sobre todo SECOP. El score heurístico no es una probabilidad de adjudicación. No se entrenó ningún modelo.

## 11. Archivos modificados

Cambios de esta fase, adicionales a los locales anteriores:

- `backend/app/services/match_execution.py`: snapshot/cálculo/confirmación, heartbeat y fencing.
- `backend/app/services/match_jobs.py`: delegación, cobertura y protección del porcentaje.
- `backend/app/services/match_versions.py`, `backend/app/db/models.py`: procedencia separada de fallos.
- `backend/app/services/match_metrics.py`, `backend/app/routers/matches.py`: observabilidad privada.
- `backend/app/routers/opportunities.py`: serialización coherente de fallos.
- `backend/alembic/versions/0012_failed_match_inputs.py`.
- `frontend/components/match-progress.tsx`, páginas Oportunidades/lista/detalle, Perfil y una corrección terminológica del manual.
- `backend/app/services/ranking_evaluation.py`, `backend/evaluation/*`, `backend/scripts/evaluate_ranking.py`.
- `backend/scripts/test_isolated_phase13.py`, `benchmark_phase13.py`, `e2e_phase13.py` y `requirements-isolated-tests.txt`.
- Pruebas nuevas de estabilización, estadísticas, métricas/autorización y Redis; ajustes de las pruebas existentes para inyectar fallos en escrituras agrupadas y exigir que los escritores terminen durante cálculo.
- `backend/benchmarks/phase13/`: resultados y planes sintéticos/capturas, sin datos empresariales.

No se eliminaron pruebas para lograr aprobación. No se reescribieron matcher, migraciones históricas, licencias ni pagos.

## 12. Migraciones

Nueva migración aditiva `0012_failed_match_inputs`, dependiente de 0011, agrega `UserOpportunity.failed_input_versions` JSON nullable. Separa versiones del intento fallido de las del último score conservado.

Antes, un fallo podía conservar la cifra pero reemplazar sus versiones; un historial posterior quedaría mal atribuido. Ahora la cifra y sus versiones buenas permanecen juntas; el intento fallido tiene su propia metadata. Un recálculo exitoso conserva historial correcto y limpia la metadata del fallo. Fallos heredados sin procedencia verificable no se presentan como historial verificado.

El upgrade es compatible con create_all histórico y no duplica columnas. El downgrade rechaza retirar 0012 si existe metadata que perdería. Se probó la guarda con PostgreSQL real y se conservaron las protecciones de historial/trabajos de 0011. Sin stamp ni migraciones sobre bases reales. Un esquema preexistente incompatible requiere inspección; una guarda de existencia no lo repara.

## 13. Pruebas ejecutadas

| Conjunto | Resultado |
|---|---|
| Backend general | 105 aprobadas, 17 omitidas; log completo con advertencias |
| PostgreSQL ingesta/Fase 1.1 | 4 aprobadas, 5 advertencias |
| PostgreSQL matching/migración | 6 aprobadas, 364 advertencias |
| Redis + Celery prefork + PostgreSQL | 6 aprobadas, 32 advertencias |
| Ranking offline focal | 4 aprobadas; etiquetas sintéticas de test, no evaluación humana |
| TypeScript | tsc --noEmit aprobado |
| E2E escritorio/móvil | aprobado con aplicación/servicios locales reales y datos sintéticos |
| Fórmula y pesos | git diff vacío para matcher.py |

Las 17 omisiones del comando general corresponden a diez tests PostgreSQL y seis Redis operativos, ejecutados aparte, más una regresión anterior Redis/SQLite opt-in que no se repitió sobre Redis en esta fase. Su variante memory pasó; no se equipara con Redis ni se oculta esa omisión.

Se conservaron deprecaciones de fechas/FastAPI/httpx/crypt, clave corta JWT de fixtures y ciclo FK companies/users. La cantidad exacta de advertencias del comando final figura en `/tmp/mysecop-phase13-backend-final.log`. No se silenciaron. Las primeras ejecuciones detectaron un import opcional recolectado por pytest y supuestos incorrectos del arnés (configuración entre procesos, nuevos candidatos después del snapshot y controles no importados por hijos spawn); se corrigieron y se repitieron las pruebas.

Otros logs: `/tmp/mysecop-phase13-postgres-final.log`, `/tmp/mysecop-phase13-redis-final.log`, `/tmp/mysecop-phase13-e2e-final.log`, `/tmp/mysecop-phase13-benchmark-final.log`, `/tmp/mysecop-phase13-ranking-final.log`. Los tests generales incluyen autenticación, perfiles, Premium, suscripciones, análisis, guardar/descartar, ofertas, búsqueda, dashboard y alertas.

Se instalaron herramientas únicamente en el venv temporal de QA, sin servicios globales. Dependencias opcionales probadas en `requirements-isolated-tests.txt`: pgserver 0.1.4, redislite 6.2.912183, psycopg2-binary 2.9.13, Playwright 1.65.2, psutil 7.2.2. Chromium se descargó bajo /tmp. El navegador integrado no exponía node_repl/js y se usó el fallback Playwright local.

## 14. Métricas y benchmarks

Presupuesto escrito **antes de medir**: batch 200, fake embeddings 64 dimensiones, dos ejecutores, pool PostgreSQL cuatro conexiones sin overflow; p95 candidatos <=250 ms, ranking SQL <=500 ms, cobertura <=2.000 ms, confirmación <=1.000 ms; RSS del proceso <=512 MiB; throughput >=500 scores/s; máximo 120 s/escenario y 600 s total. Son metas locales de smoke, no SLO de producción.

Scoring controlado constante para aislar infraestructura; no son mediciones del matcher completo ni de OpenAI. 20% de registros sintéticos se excluyen por fuente/estado: 50.000 registros contienen 40.000 candidatas. PostgreSQL 16.2 real, socket privado, sin Redis en el benchmark directo del motor.

| Registros | Usuarios | Scores confirmados | Segundos | Scores/s | Cobertura p95 ms | Confirmación p95 ms |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 1 | 800 | 0.189 | 4236 | 2.99 | 34.06 |
| 1,000 | 10 | 8,000 | 1.234 | 6482 | 2.58 | 49.47 |
| 10,000 | 1 | 8,000 | 1.775 | 4508 | 16.47 | 43.57 |
| 10,000 | 10 | 80,000 | 11.232 | 7122 | 17.10 | 51.22 |
| 50,000 | 1 | 40,000 | 11.049 | 3620 | 102.71 | 48.01 |
| 50,000 | 10 | 400,000 | 61.036 | 6554 | 100.00 | 49.76 |

**Los seis escenarios cumplieron el presupuesto.** Resultados completos: `backend/benchmarks/phase13/results.json`, con hash del motor y fecha de medición. El hash se contrastó con el archivo final. Máximo RSS observado del proceso: aproximadamente 102,6 MB; no incluye memoria del servidor PostgreSQL ni permite inferir memoria productiva. Pico de conexiones: dos, sin timeouts. Por lote: hasta 17 sentencias y 11 SELECT en PostgreSQL, sin N+1.

Se registran p50/p95 de candidatos/ranking/cobertura y confirmación, escrituras, lecturas, throughput y memoria. El estimador p95 del script es el estadístico de orden floor((n−1)×0,95); las muestras de consultas son pequeñas (diez de candidatos/ranking y tres de cobertura por usuario), por lo que no constituyen estimaciones precisas de cola ni garantías de SLO. El p50 de consultas usa mediana; los cuantiles de confirmación usan el estadístico de orden. No se cambiaron los límites después de observar resultados.

Los planes adicionales de trabajos, slots e historial tienen volumen pequeño/vacío. No se certifica comportamiento de un historial grande, cold cache, datasets con textos extensos, 768/1.536 dimensiones, alta cardinalidad empresarial o muchos procesos distribuidos. Esas mediciones corresponden a DEV. No se extrapolan los resultados a millones de oportunidades.

## 15. Problemas encontrados

- Locks y conexiones retenidos durante proveedor: reemplazados por cálculo fuera de transacción y validación optimista.
- Procedencia del score anterior corrompida por un intento fallido: corregida con 0012 y pruebas de historial.
- Respuestas de polling antiguas y primer render StrictMode: corregidos con control de generación/ciclo de vida.
- Redondeo 100% con pendientes: corregido y probado con 49.999/50.000.
- Acción guardar ausente en la lista: restaurada sin afectar score.
- Análisis antes de completar selección/subida: se evita habilitarlo en estados incompatibles.
- Terminología de probabilidad en filtros/manual: sustituida por compatibilidad, sin cambiar fórmula.
- Herramientas Redis/navegador ausentes y límites sandbox: resueltos con herramientas temporales y ejecución autorizada; no se conectaron servicios empresariales.

## 16. Riesgos pendientes

1. Falta validar en DEV sobre copia autorizada del esquema y datos representativos, con réplicas/latencias/proveedores reales.
2. No se validó Linux prefork, caída completa del servidor PostgreSQL, reinicio de host, particiones prolongadas ni supervivencia a pérdida de disco/AOF. Se inyectó pérdida de conexión PG y reinicio de Redis local.
3. Los leases dependen de relojes sincronizados. Un proveedor puede exceder el timeout; los fallos individuales requieren reintento controlado y no se convierten en scores verificados.
4. La confirmación todavía bloquea brevemente filas y puede esperar a ingesta/escritores. La ingesta no recibió esta refactorización transaccional.
5. Cobertura continúa recorriendo el universo; historia y coordinación por muchas empresas necesitan benchmarks propios y eventual retención/índices justificados.
6. Las escrituras fuera del contrato ORM/versionado siguen requiriendo invalidación explícita. No hay triggers universales.
7. El QA fue de Next en desarrollo y Chromium; faltan otros navegadores, accesibilidad completa, dispositivos físicos y build/despliegue productivo.
8. No existen etiquetas humanas: precisión, recall, NDCG y FPR reales permanecen pendientes. El pool de evaluación no debe sesgarse por seleccionar solamente scores altos.
9. Las limitaciones de cobertura Socrata y advertencias históricas de fases anteriores siguen vigentes.

## 17. Validación recomendada en DEV

Revisar el diff preservando fases anteriores, verificar backup/host/base y ejecutar 0012 en una copia autorizada. Comprobar scores antiguos, intentos fallidos, historial y aislamiento. Mantener API, beat y workers con mismo código/configuración de algoritmo/embeddings para evitar SUPERSEDED por revisiones incompatibles.

Reproducir servicios aislados con un venv dedicado:

```bash
cd backend
python3 -m venv /tmp/mysecop-qa
/tmp/mysecop-qa/bin/python -m pip install -r requirements-isolated-tests.txt
/tmp/mysecop-qa/bin/python scripts/test_isolated_postgresql.py
/tmp/mysecop-qa/bin/python scripts/test_isolated_phase13.py
/tmp/mysecop-qa/bin/python scripts/benchmark_phase13.py
PLAYWRIGHT_BROWSERS_PATH=/tmp/mysecop-playwright-browsers /tmp/mysecop-qa/bin/python -m playwright install chromium
PLAYWRIGHT_BROWSERS_PATH=/tmp/mysecop-playwright-browsers /tmp/mysecop-qa/bin/python scripts/e2e_phase13.py
```

Los ejecutores crean bases mysecop_test_* vacías y Redis por socket privado; no aceptar URLs empresariales ni reutilizar bases existentes. No instalan servicios globales ni limpian producción. Las pruebas de fallo terminan procesos propios deliberadamente. Después, probar workers/beat controlados en DEV, medir pools por proceso, proveedor real, tiempos de ingesta y una muestra acotada; no iniciar sincronizaciones masivas.

Completar juicios humanos ciegos y el protocolo de evaluación antes de comparar un modelo nuevo. La plantilla y el CLI funcionan sin cargar datos reales ni entrenar modelos.

## 18. Procedimiento de rollback

Detener beat/cola matches y permitir finalizar o cancelar trabajos en un límite transaccional. Respaldar base, historial y metadata. Revertir backend/frontend conjuntamente a una revisión conocida, conservando por defecto el esquema aditivo, los valores y la procedencia de intentos.

No forzar downgrades: 0012 bloquea pérdida de metadata de fallos y 0011 bloquea pérdida de historial/trabajos activos. No borrar esas filas ni usar stamp para sortear guardas. Diseñar primero un archivo/restauración verificados si se exige retirar físicamente columnas/tablas con datos. El rollback de código no restaura automáticamente valores anteriores de score; usar historial/respaldo. No se ejecutó rollback en producción ni sobre bases empresariales.

## 19. Matriz de criterios de aceptación

| Criterio | Estado | Evidencia y alcance |
|---|---|---|
| Redis/Celery reales aislados | Probado con servicios reales | seis casos operativos; prefork/spawn macOS |
| Recuperación tras fallo de worker | Probado con servicios reales | warm/SIGKILL, leases reales vencidos y coordinador |
| Sin duplicaciones indebidas | Probado local/servicios | entregas repetidas; scores/historial únicos |
| Sin esperas externas bajo locks críticos de matching | Probado PostgreSQL | escritores terminan durante cálculo; confirmación corta |
| No confirmar entradas obsoletas | Probado local/PostgreSQL | perfil, oportunidad, revisión, token y versiones fallidas |
| Cobertura consistente | Probado local/E2E | agregado, categorías, cero y protección de redondeo |
| Consultas dentro de presupuesto | Probado en benchmark sintético | seis escenarios; límites previos, planes y métricas; producción pendiente |
| Autorización y aislamiento | Probado API | todas las rutas, misma/distinta empresa y metadata privada |
| Regresiones comerciales | Probado backend/E2E | Premium/auth/perfil/ofertas/análisis/guardar/descartar; sin cambios de licencias |
| Evaluación reproducible del matcher | Implementado y probado con fixtures | CLI, protocolo y métricas; calidad humana pendiente |
| Resultados/riesgos documentados | Completo | informe, logs y artefactos sintéticos |
| Sin operaciones productivas/destructivas sobre datos reales | Respetado | solo entornos propios descartables; sin despliegues ni commits |

Dictamen: **estabilización técnica local completada en este alcance, preparación para DEV controlado; producción pendiente**. No confundirlo con certificación de disponibilidad distribuida ni de calidad estadística.

## 20. Preparación para la Fase 2

Existe infraestructura verificable para conservar versiones, recuperar trabajo, medir cobertura y evaluar ranking. La condición para sustituir el matcher no es aumentar porcentajes: es contar con un conjunto humano independiente, referencia no sesgada, métricas reproducibles por sector y validación operativa de DEV.

No se implementaron LambdaMART, entrenamiento predictivo ni nuevos pesos. Tampoco se migró a perfiles compartidos por empresa. Antes de Fase 2: completar anotaciones, resolver desacuerdos sin mostrar scores, medir comparativas con el ranking servido, fijar criterios de calidad previamente y mantener la procedencia de datos/algoritmo. El nuevo modelo deberá superar esa línea base y conservar estas garantías operativas.
