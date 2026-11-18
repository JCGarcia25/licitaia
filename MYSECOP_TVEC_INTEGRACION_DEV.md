# MySECOP — Integración TVEC preparada para DEV

Fecha: 16 de noviembre de 2026, America/Bogota. **Implementación y QA locales; no desplegada ni publicada.** TVEC y su ingesta permanecen deshabilitadas por defecto. No se accedió a bases operativas ni se ejecutaron pipelines, commits, pushes o acciones sobre STG/producción en esta tarea.

## 1. Resumen ejecutivo

Se incorpora el consolidado TVEC `rgxm-mmea` como historial de órdenes de compra, con almacenamiento, ingesta, cola e indicadores propios. No se crea ninguna Opportunity TVEC, puntuación de compatibilidad, alerta de convocatoria o proyecto de propuesta. El selector Todas/SECOP/Tienda Virtual presenta secciones diferentes; no crea un ranking combinado.

Las órdenes se identifican por el campo oficial, sin inventar líneas de producto a partir de texto. La API autenticada permite filtros, paginación, detalle y análisis de compradores, proveedores, agregaciones y periodos. No se publican solicitudes de cotización abiertas, vigencia de instrumentos, elegibilidad de proveedores ni totales monetarios agregados sin respaldo suficiente.

Dictamen: **preparada localmente para revisión y preflight DEV, con restricciones documentadas**. La validación operativa DEV sigue pendiente de destino PostgreSQL/Redis comprobado, respaldo restaurable, revisión de esquema y autorización posterior. La autorización previa de otros despliegues no se reutilizó para este trabajo.

## 2. Estado del repositorio, RC y ambientes

- Checkout original: develop, HEAD `cac56d02c9f07690bc0ed04a96350cb5e8fa3377`, con avances acumulados sin commit local. Se conservaron, incluidos Contacto/WhatsApp.
- Referencia remota DEV consultada sólo en lectura: `77fc86658540f6a0041a855f1be3120a938413c0`. Esta tarea no movió esa referencia.
- RC histórico: `mysecop-compatibility-v2-rc1`, payload `0475bffbe701d87abf352acacc1d7350671624b55c2578971568d2636ae9fce7`. Es antecedente; no identifica el nuevo código TVEC.
- Respaldo previo de código: `/tmp/mysecop-tvec-before/code.tar.gz`, inventario SHA-256 por archivo `/tmp/mysecop-tvec-before/inventory.json`; 232 archivos de código/documentación verificados dentro del tar. Se excluyeron secretos, persistencia, logs, benchmarks e imágenes. No se eliminaron los originales ni archivos sin seguimiento.
- Configuración local leída sin conexión: development, SQLite local, Redis localhost/0, flags TVEC false, allowlist TVEC vacía y origen localhost. **No acredita un DEV PostgreSQL autorizado.** El preflight TVEC devuelve DENIED antes de conectar.
- DEV real identificado por workflow existente: dev.mysecop.co, proyecto licitaia-dev; healthcheck GET público devuelve development. No se comprobaron sus credenciales, identidad DB/broker, respaldo ni revisión actual por SQL. La última entrega previa usaba 0014; ese antecedente no sustituye inspección actual.
- No hay conflictos en el índice; no se ejecutó reset, clean, merge, tag o publicación. Los workflows automáticos existentes no fueron modificados para esta integración.

## 3. Esquema real y disponibilidad oficial

Se consultaron los [metadatos oficiales](https://www.datos.gov.co/api/views/rgxm-mmea.json), cinco registros con `$limit=5` y un resumen agregado del [dataset](https://www.datos.gov.co/Gastos-Gubernamentales/Tienda-Virtual-del-Estado-Colombiano-Consolidado/rgxm-mmea). No fue una carga de datos en una base de MySECOP.

Al cierre se probó además el adaptador HTTP final con **una sola fila oficial**, normalizada en memoria, solicitando únicamente columnas permitidas y excluyendo solicitante desde el `$select`. Resultado válido, sin conexión ni escritura DB; `live-contract.json` conserva sólo el resultado técnico, sin valores personales. Esta prueba real acotada no es una sincronización operativa.

Resultado observado: **169.444 filas y 169.444 órdenes distintas**, por `identificador_de_la_orden`; fecha mínima 2013-10-17, máxima 2026-10-26. `rowsUpdatedAt=1793177887`, equivalente a 2026-10-28 08:58:07 UTC. El portal declara frecuencia **diaria**, pero esa actualización real tiene 19 días de antigüedad al corte; no se confunde frecuencia declarada con frescura efectiva.

El contrato observado tiene 28 columnas de negocio. Sus nombres, tipos y descripciones se conservan en `backend/app/data/tvec_schema_verified.json`, junto al resultado agregado y origen. No contiene muestras personales reales. La revisión automática de permisos falló técnicamente al solicitar varias consultas juntas; esa operación no se ejecutó. La consulta agregada individual posterior sí se autorizó y respondió correctamente.

La [FAQ oficial TVEC](https://operaciones.colombiacompra.gov.co/ciudadanos/preguntas-frecuentes/tienda-virtual-del-estado-Colombiano) distingue la selección/cotización y la solicitud de compra. La [guía general de acuerdos](https://www.colombiacompra.gov.co/archivos/manual/guia-general-de-los-acuerdos-marco-de-precio) remite al procedimiento específico de cada instrumento. Las compras registradas no acreditan una oportunidad abierta ni habilitación general para cotizar.

## 4. Inventario y mapeo de columnas

| Columna oficial | Tipo Socrata | Uso / significado |
|---|---|---|
| a_o | number | Año declarado; conservado en raw, no cursor |
| identificador_de_la_orden | text | official_id y número de orden; identidad única verificada en este corte |
| rama_de_la_entidad | text | Rama compradora, raw |
| orden_de_la_entidad | text | Nivel territorial, raw; no confundir con número de compra |
| sector_de_la_entidad | text | Sector estatal comprador, raw |
| entidad | text | buyer, nombre público comprador |
| solicitante | text | Persona solicitante; **excluida del almacenamiento raw/API/documentación** por minimización |
| fecha | calendar_date | issued_at, fecha de orden |
| fecha_vence | calendar_date | expires_at, vencimiento de orden; nunca fecha límite para ofertar |
| proveedor | text | supplier, proveedor registrado, no participante competitivo inferido |
| estado | text | status, estado de la orden, no estado de convocatoria |
| solicitud | number | ID de solicitud de compra, raw; no se trata como evento RFQ abierto |
| items | text | description íntegra; no contiene un contrato estructurado de cantidades/precios por línea |
| total | number | amount Decimal exacto, Numeric(30,6); no se sustituye por monto inicial ni por cero |
| agregacion | text | instrument, nombre de agregación/mecanismo; no catálogo de vigencia |
| ciudad | text | city, ubicación registrada, no lugar de ejecución inferido |
| entidad_obigada | text | Indicador fuente de entidad obligada, raw |
| espostconflicto | text | Indicador fuente, raw |
| nit_proveedor | text | supplier_nit, trazabilidad pública necesaria; no se expone en la API inicial |
| actividad_economica_proveedor | text | category: **actividad del proveedor**, no categoría de producto ni UNSPSC inventado |
| nit_entidad | text | buyer_nit, trazabilidad pública; no se expone en API inicial |
| id_entidad | text | ID comprador Coupa, raw |
| departamento | text | department, departamento comprador |
| items_solicitud_inicial | text | Descripción inicial, raw; no ítems estructurados |
| total_solicitud_inicial | number | Monto estimado inicial, raw; no se suma al total de la orden |
| fecha_creacion_solicitud_inicial | calendar_date | initial_request_at; fecha de compra inicial, no actualización de orden |
| destinacion_gasto | text | Origen/categorización del gasto según descripción oficial, raw |
| origen_recursos | text | Origen de recursos, raw |

Se consulta adicionalmente `:id AS source_row_id`, sólo como procedencia de la fila Socrata. **No es la identidad de orden ni el cursor de actualización.** Los IDs oficiales se preservan como texto, incluidos ceros o caracteres originales. La versión es hash del payload permitido, sin solicitante ni metadatos volátiles de captura.

Ausentes: moneda, timestamp de modificación de cada orden, URL individual, UNSPSC de producto, precios/cantidades normalizados de líneas, vigencia de instrumentos y disponibilidad de cotizaciones. No se inventan. El enlace de la UI se denomina «Ver dataset oficial TVEC», no enlace individual a la orden.

## 5. Modelo de datos

Cinco tablas independientes:

1. `tvec_purchase_orders`: official_id único, source_row_id, comprador/proveedor, NIT públicos internos, descripción textual, agregación, actividad del proveedor, ubicación, valor exacto/moneda nullable, fechas, estado, URL nullable, raw permitido, hash, ciclo visto y synced_at.
2. `tvec_order_revisions`: FK a orden, versión/payload anterior, source_row_id anterior y fecha de registro. Una actualización conserva la revisión previa; no sobreescribe historia.
3. `tvec_source_metadata`: dataset, contrato de columnas/hash, actualización global, comprobación local, frecuencia declarada y conteo remoto comprobado.
4. `tvec_sync_states`: cursor por ID oficial, generación de fuente, ciclo, filas del ciclo, ciclos completos, lease/token, estado y errores.
5. `tvec_sync_runs`: petición durable y presupuesto de páginas, páginas/filas y contadores inserted/updated/unchanged, estado/error tipo y fechas.

No se creó TvecPurchaseOrderItem: `items` es texto y contiene punto y coma dentro de descripciones, por lo que dividirlo crearía líneas falsas. La igualdad de filas/órdenes confirma la unidad actual. En cada comprobación de conteo se exige la misma unicidad: si cambia la granularidad, la ingesta se detiene para revisar el adaptador y modelar ítems correctamente, sin sumar importes repetidos.

No se creó una entidad de instrumento vigente sin datos suficientes. `/instruments` agrupa nombres históricos; no representa un catálogo habilitante. No hay relación ORM/SQL entre órdenes TVEC y Opportunity/UserOpportunity/MatchScoreHistory.

## 6. Arquitectura de integración

`TvecClient` reutiliza encabezados/token Socrata del cliente existente, con host/dataset fijos, timeout y reintentos propios. `tvec_ingest` combina runs durables, upsert agrupado y cursor transaccional. La API usa tablas TVEC; el frontend separa fuentes mediante componentes propios y reutiliza el listado SECOP existente.

Se añadieron guardias DEV opt-in sobre el mecanismo de identidad de instalación aislada ya existente. La tupla DB/broker/API debe coincidir exactamente con TVEC_DEV_TARGETS; se comprueba secreto suficiente, sesión real y marcador persistido con propósito isolated-development. **No es necesario habilitar evaluación V2 para TVEC.** production y staging son rechazados incluso con flags TVEC accidentalmente true.

La cola `tvec` no recibe tareas del beat. El overlay opcional proporciona un worker -Q tvec con concurrency=1 y excluye esa cola del worker general. Sin -Q, Celery consume task_queues completas: separar recursos requiere usar explícitamente esa configuración, no sólo declarar el nombre de cola. El overlay no está conectado a ningún workflow automático.

## 7. Sincronización y límites

Reconciliación por `identificador_de_la_orden ASC`, comparación textual estable y escape de comillas SoQL. La ingesta no acepta timestamps SECOP, filtros parciales arbitrarios o una fecha inicial como marca compartida.

Por defecto: TVEC_ENABLED=false, TVEC_INGEST_ENABLED=false, TVEC_DEV_TARGETS=[], página100, presupuesto máximo2 páginas/run, lease180 segundos. Settings restringe página1–200, máximo páginas1–5 y lease60–600. Cada run tiene presupuesto durable: los reintentos no reinician su contador ni amplían el volumen autorizado.

El cliente limita a cuatro intentos con timeout10s y backoff1/2/4 para red y 429/502/503/504. Otros HTTP fallan explícitamente. Un worker tiene soft/hard time limits90/120s y hasta tres reintentos controlados; latencias extremas pueden agotar el run y requerir diagnóstico/resume. No hay ejecución ilimitada ni fallback de red sobre el matcher.

Todas las consultas HTTP se hacen fuera de una transacción abierta. Un CAS global evita dos ingestas concurrentes del dataset. El token/vencimiento se verifica antes y después de escribir; registros, revisiones, contadores y cursor se confirman juntos. La carga de órdenes existentes usa una consulta por página, no una por fila.

IDs ausentes/repetidos, desorden, importes no finitos/fuera de precisión, fechas inválidas y deriva de esquema provocan rollback de la página. Se guarda sólo el tipo de error, sin raw/identidades/credenciales en logs. Mensajes repetidos de runs DONE son idempotentes. Tras interrupción se reanuda el run/cursor durables.

## 8. Reconciliación, historial y cobertura

No hay incremental temporal por orden verificado. `rowsUpdatedAt` se usa sólo para detectar generación del dataset; si cambia, se reinicia el barrido conservador, sin borrar órdenes/historia. Al llegar al final se comprueba que la generación no cambió y que las filas del ciclo coinciden con el conteo remoto único antes de registrar barrido completo.

Las órdenes que desaparezcan del dataset **no se borran** del histórico local. El total local puede ser mayor que un conteo remoto posterior: se muestran ambos como magnitudes separadas, nunca porcentaje de cobertura >100. `last_complete_at` acredita un barrido histórico; no garantiza fotografía actual perpetua. Cada indicador aclara que sólo cubre datos locales y fecha de actualización real. Ninguno modifica la cobertura del Cazador SECOP.

Limitaciones: no snapshot transaccional entre peticiones Socrata; una fuente que cambie durante muchos barridos puede forzar reinicios. El presupuesto piloto no es una carga completa de 169.444 órdenes. La programación/ventanas/retención física y detección de bajas requieren un diseño operativo posterior con autorización de volumen.

## 9. Diferenciación SECOP, TVEC y participación

- SECOP conserva filtros, estados, matching y acciones comerciales existentes. Las tarjetas muestran Proceso SECOP, Registro SECOP I o Contrato SECOP II según procedencia.
- TVEC muestra «Orden de compra TVEC» y «Compra registrada», sin score, plazo para ofertar, guardar como oportunidad, alerta de convocatoria o creación de propuesta.
- `fecha_vence` sólo aparece en detalle como vencimiento de orden, aclarando que no es plazo de oferta.
- Cotizaciones abiertas: **NO IMPLEMENTADAS**. No se verificó una fuente pública suficiente de eventos vigentes/requisitos/proveedores para exponerlas en esta integración; no se afirma que no pueda existir otra fuente.
- Vigencia del instrumento, habilitación previa y elegibilidad: **NO DETERMINADAS/POR VERIFICAR**. Los nombres históricos no prueban participación ni vigencia actual.

No cambian el matcher heredado, embeddings, matemáticas/pesos V2, licencias, pagos, usuarios ni suscripciones. Las pruebas verifican conservación de scores y triage e inexistencia de efectos TVEC en Opportunity. No se entrenan modelos ni se activa V2 comercial.

## 10. Diseño UX/UI

Selector Todas/SECOP/Tienda Virtual visible en Oportunidades, botones con aria-pressed y marca de selección no basada sólo en color. SECOP es el valor inicial para conservar el recorrido existente; Todas muestra secciones identificadas y paginadas independientemente, nunca un orden común por compatibilidad.

TVEC ofrece buscador, panel de filtros nativo accesible, resumen local, tarjetas y detalle. Vistas de demanda: órdenes, compradores, proveedores, instrumentos y periodos. Desde una agrupación se consultan sus compras mediante filtro exacto. El panel «Actualización y alcance» explica conteos, última reconciliación, moneda y limitaciones; la actualización de fuente permanece visible sin abrirlo.

La ausencia de moneda impide agregar importes o comparar crecimiento monetario: summary devuelve monetary_total=null y motivo explícito. Los periodos cuentan compras locales y no afirman tendencias futuras. Compradores/proveedores se agrupan por nombre registrado: no son un maestro jurídico de entidades/NIT; variantes de nombre pueden separar una entidad.

## 11. Responsive

QA Chromium/Next real en **390×844, 768×1024, 1440×900 y 320×760**, con API TVEC sintética. No se declara integración de frontend con TVEC real en DEV.

Móvil: selector, búsqueda, panel de filtros expandible por teclado/tacto, resumen compacto, tarjetas verticales y acciones de altura mínima44px. Desktop/tablet: filtros2–3 columnas y tarjetas hasta2 columnas. Sin tablas anchas ni truncado de descripciones esenciales; pruebas de scrollWidth<=innerWidth en cada estado capturado. El detalle conserva la navegación de regreso.

Se revisaron visualmente capturas y corrigieron padding de tarjetas, contraste de enlaces y posición de captura del detalle. Evidencias finales en `backend/benchmarks/tvec/`, con datos ficticios; las capturas de filtros y detalle enfocan su panel completo para evitar pantallas vacías o ilegibles.

## 12. Accesibilidad

Etiquetas de formulario asociadas, summary/details nativos, Enter para expandir, foco visible, estados de carga/status y error/alert, fuente seleccionada anunciada con aria-pressed y marca visual, links externos con aviso de nueva pestaña. Se comprobó navegación y conservación de filtros tras recarga/detalle.

Contrastes calculados con luminancia relativa sRGB sobre colores nuevos: texto claro15,99; secundario claro4,76; enlaces claros5,47; texto oscuro14,20; secundario oscuro6,61; enlaces oscuros6,56. Nuevos enlaces usan turquesa oscuro en modo claro y turquesa en oscuro. `contrast.json` registra alcance y resultados. Hay captura de modo oscuro.

Estas verificaciones cubren criterios aplicables, **no certificación completa WCAG 2.2 AA**, auditoría de todos los componentes heredados o validación exhaustiva con lectores de pantalla reales. La navegación móvil preexistente no se rediseñó.

## 13. API y contratos

| GET autenticado | Contrato |
|---|---|
| /api/tvec/orders | items,total,limit,offset,provenance,query_ms |
| /api/tvec/orders/{id} | order,provenance;404 si no existe |
| /api/tvec/buyers | Agrupaciones por nombre comprador, periodos/conteos/procedencia |
| /api/tvec/suppliers | Proveedores registrados, no participantes competitivos inferidos |
| /api/tvec/instruments | Agregaciones históricas, instrument_validity=NOT_VERIFIED_FROM_ORDERS |
| /api/tvec/summary | Conteos filtrados, periodos, monetary_total=null y motivo |
| /api/tvec/sync-status | Estado, errores, última reconciliación/procedencia |

Limit1–50; offset0–100000. Texto máximo200; nombres/ubicación/estado acotados; valores Decimal con límites y fechas/rangos validados. q busca subcadena literal sin convertir %/_ en comodines; comprador/proveedor/instrumento/actividad/departamento/ciudad/estado son coincidencias exactas del texto registrado. Rango inválido o límite excesivo devuelve422; sin resultados no se retira ningún filtro.

Los importes se serializan como string decimal para no perder precisión JSON. No se retorna raw_json, solicitante, NITs o información de usuarios. No se añadieron endpoints POST de ingesta para usuarios. La operación se realiza por CLI protegido después del preflight/autorización. No se aplican compatibilidad, perfil ni filtros SECOP a TVEC.

## 14. Seguridad, licencias y minimización

Todos los endpoints requieren usuario activo según autenticación existente y un destino TVEC DEV autorizado. No se agregaron roles ni límites comerciales; matriz Free/Pro organizacional **POR CONFIRMAR**. El acceso técnico disponible en el piloto se limita a autenticados, sin un bloqueo Pro inventado.

La API sólo lee tablas públicas TVEC, sin joins a perfiles, vectores, documentos o empresas. `solicitante` se excluye de la petición del adaptador y se descarta defensivamente incluso del raw local; los demás campos raw permitidos conservan procedencia, pero no se exponen en API. Sólo se usan fixtures anonimizados/enteramente ficticios en pruebas, benchmarks y capturas.

Las URLs del origen Socrata están fijadas, SQL está parametrizado y el cursor SoQL escapa comillas. No se publican credenciales ni valores de conexión. Las preferencias de fuente/filtros se guardan en sessionStorage y se limpian al cerrar sesión. La guardia comprueba DB/broker/API y marcador sin relajar los controles de evaluación anterior.

## 15. Cambios de frontend y persistencia

El listado SECOP anterior se extrae a `secop-opportunities.tsx`; conserva su contrato/acciones y añade sólo badge de fuente y conservación de parámetros de TVEC/retorno. La ruta Oportunidades contiene el selector y las secciones. No se cambian rutas API SECOP ni el algoritmo.

TVEC usa parámetros tv_* para no colisionar con q/filtros SECOP, guarda vista/página/filtros en URL y sessionStorage, soporta popstate/recarga y detalle con volver validado al listado. En Todas, callbacks SECOP preservan la fuente y los filtros TVEC actuales para evitar que una respuesta anterior reescriba la selección. La limpieza es explícita y sólo para TVEC.

La página de detalle existente SECOP conserva return URL sin afectar regreso a Alertas. Se aclara el texto de fuentes de la barra lateral; se mantiene la identidad y componentes visuales actuales. Los estados vacíos/error ofrecen modificar filtros o reintentar, sin cambiar la consulta silenciosamente.

## 16. Migraciones

Nueva revisión aditiva **0015_tvec_orders**, dependencia0014. Operaciones literales sobre cinco tablas e índices: official_id único; department/instrument/issued_at/status/seen_cycle y FK revision→order. No altera tablas SECOP ni datos históricos de clientes.

Startup excluye tvec_* de create_all y ALTER automáticos; se exige migración explícita para esos objetos. Permanece la limitación histórica de0001 que importa modelos actuales: en una base vacía puede crear tablas futuras antes de su revisión; las guardias idempotentes y las pruebas de downgrade/upgrade de0015 ejercitan también su creación literal. No se reescribieron migraciones anteriores ni se usó stamp.

Downgrade0015 sólo pasa si **las cinco tablas están vacías**. Cualquier orden, revisión, cursor, metadata o run bloquea retirada para conservar información. Rollback preferido: código/flags. El verificador existente evaluation_target.py admite ahora0014 o su extensión aditiva revisada0015, evitando romper aprovisionamiento anterior; la compatibilidad de ese chequeo se prueba en PostgreSQL. Las fórmulas V2 permanecen idénticas.

## 17. Archivos modificados/nuevos

Nuevos: `backend/app/services/tvec_client.py`, `tvec_guard.py`, `tvec_ingest.py`; `backend/app/routers/tvec.py`; `backend/app/data/tvec_schema_verified.json`; `backend/alembic/versions/0015_tvec_orders.py`; scripts `tvec_admin.py`, `test_isolated_tvec.py`, `benchmark_tvec.py`, `e2e_tvec.py`; tests `test_tvec.py`, `test_postgresql_tvec.py`, `test_redis_tvec.py` y fixture `fixtures/tvec_orders_synthetic.json`; `frontend/components/source-selector.tsx`, `secop-opportunities.tsx`, `tvec-explorer.tsx`; detalle `frontend/app/(private)/app/tienda-virtual/[id]/page.tsx`; `docker-compose.tvec-dev.yml`; evidencias `backend/benchmarks/tvec/` y este informe.

Ampliados respecto al respaldo de inicio de esta tarea: config/modelos/session/main, registro de cola/tarea Celery, `.env.example`, `evaluation_target.py`, arnés de worker descartable, listado/detalle SECOP, layout privado y limpieza de la nueva preferencia en logout. Los cambios acumulados contra HEAD de fases previas no se atribuyen íntegramente a TVEC. El inventario/hash de la validación registra exactamente las fuentes de esta entrega.

## 18. Pruebas ejecutadas

| Suite | Resultado local |
|---|---|
| Backend completo | **157 passed,26 skipped,1.540 warnings** |
| PostgreSQL TVEC real | **2 passed**,4 warnings |
| Redis/Celery TVEC real | **1 passed**,4 warnings; múltiples escenarios |
| PostgreSQL regresión anterior | **14 passed** (4+6+2+2),5/364/12/6 warnings |
| Redis/Celery regresión anterior | **8 passed** (6+1+1),32/8/6 warnings |
| Frontend | Build Next y TypeScript aprobados; lint sigue omitido por configuración heredada |
| E2E TVEC | Chromium real/Next local, API simulada; cuatro resoluciones y modo oscuro |
| E2E comercial anterior | Next/FastAPI/PG/Redis/Celery reales aislados; fuente/factores ficticios |

26 omisiones backend:16 PostgreSQL y9 Redis ejecutadas con runners aislados, más una prueba histórica opt-in Redis/SQLite no ejecutada. No se eliminaron pruebas ni se rebajaron aserciones correctas. Warnings no suprimidos: UTC naive, FastAPI on_event, Starlette/httpx, crypt/passlib y ciclo FK companies/users. La restricción RVM/ps del sandbox es ajena al código.

Cobertura TVEC: metadatos/esquema, cantidades/moneda/nulos/fechas, IDs y duplicados, no división falsa de items, HTTP429/red/reintentos, escape SoQL, cursor/reconciliación/actualización/revisiones, idempotencia y páginas atómicas, fencing antes/después de escritura, workers concurrentes y sin transacción durante HTTP, pérdida de la propia conexión PG, schema/índices/tipos/unique, downgrade protegido, filtros combinados, paginación, autenticación y negación en staging/production. El test de reconexión mata sólo la conexión PG del test; SIGKILL sólo el grupo de procesos creado por el arnés.

El vencimiento de lease largo se adelanta **sólo en la DB descartable** para evitar esperar180s; no es medición de180s reales. Redis sí se reinicia y recupera AOF, y el worker sí se detiene. La fuente TVEC de esos tests siempre es sintética: ninguna prueba ejecuta una sincronización real.

## 19. E2E y evidencias visuales

`scripts/e2e_tvec.py` captura42 PNG: SECOP, Todas, TVEC, filtros, búsqueda filtrada, detalle, compradores, vacío, carga y error en las cuatro resoluciones, una vista completa de Todas y una oscura390. Prueba teclado, selección anunciada, URL, paginación, detalle/regreso/recarga con filtro Meta preservado, vistas de demanda, reintento y ausencia de overflow/errores JS. Los envíos de API se interceptan; no se usan cuentas operativas.

`e2e_phase13.py` vuelve a comprobar perfil, matching/cobertura/cancelación, búsqueda/paginación, guardar/descartar, documento sintético/análisis, proyecto, alertas y diagnósticos V2/evaluación con servicios reales locales. No demuestra resultados estadísticos humanos ni autorización jurídica.

Logs, capturas, benchmarks, contraste y checks: `backend/benchmarks/tvec/validation.json` y archivos vecinos. Las evidencias distinguen fuente oficial de descubrimiento, API simulada y servicios de integración reales.

## 20. Benchmarks

PostgreSQL16.2 temporal,10.000 órdenes **sintéticas**,7 muestras por consulta, un cliente. Medianas: página20 filtrada2,061ms; página50 filtrada2,200ms; offset5000/20filas5,539ms; compradores agrupados5,395ms; resumen6,569ms. Cada llamada medida mantiene **5 consultas SQL**, incluso al pasar de20 a50 filas; no hay consulta por tarjeta.

Los índices soportan identidad/ordenación y filtros frecuentes. El substring textual y las agrupaciones pueden recorrer muchas filas; no se promete capacidad de millones, SLA, concurrencia de producción o caché distribuido. No se añadió caché de datos públicos para ocultar mediciones ni extensión PostgreSQL no verificada. La ingesta procesa lotes pequeños y reutiliza consulta agrupada de órdenes existentes.

## 21. Riesgos y pendientes

Fuente con frescura atrasada frente a su periodicidad declarada; sin cursor de cambios de negocio ni snapshot HTTP; posibles reinicios de barrido y filas desaparecidas conservadas; nombres compradores/proveedores no resueltos como identidad jurídica; moneda/categoría de producto/URL individual/vigencia/quotes no informadas o no verificadas. Se detiene la ingesta si aparecen varias filas por orden.

Pruebas de red y fallos del adaptador son simuladas, además del descubrimiento oficial y la lectura real final de una fila sin persistencia. La UI TVEC no se probó contra un DEV operativo con datos oficiales; se probó con API sintética y las capas DB/workers con servicios reales aislados. Falta auditoría completa WCAG/lectores de pantalla y carga concurrente elevada. Docker/Compose no están disponibles en esta máquina: el overlay sólo tiene validación YAML/colas/env estática, no arranque de imagen.

La identidad real DB/broker, el respaldo recuperable, capacidad/conexiones y migración actual de DEV están pendientes. No se declaró la integración desplegada. Ningún esquema histórico ni datos reales se usaron para ensayar rollback.

## 22. Procedimiento de despliegue DEV preparado, no ejecutado

1. Operador confirma destino dev.mysecop.co/proyecto licitaia-dev, DB/usuario/host, Redis aislado, API origin y almacenamiento. Obtener identidad de instalación verificable; no inferir DEV por nombre. No utilizar credenciales/volúmenes STG/PROD.
2. Revisar SHA remoto/local, inventario y diff de esta tarea. **No hacer push a develop:** dispara despliegue automático. Preparar revisión/artefacto en una rama sin pipeline de despliegue sólo cuando se autorice publicar. No se creó una rama ni commit en esta tarea.
3. Registrar revisión Alembic y esquema real por lectura autorizada; comparar contra copia aislada del backup. Respaldar DB/config/storage con permisos/cifrado y verificar restauración en una base nueva aislada. No introducir backups ni secretos en Git.
4. Construir las imágenes del código revisado antes de migrar, registrar digests y validar Compose `config --quiet` en host con soporte !override. No imprimir config con secretos.
5. Confirmar recursos: pool SQLAlchemy10+5 por proceso, matching global2, TVEC worker1 y sin scheduler TVEC; workers comerciales no deben consumir tvec si se exige separación física. El overlay opt-in `docker-compose.tvec-dev.yml` excluye esa cola del worker general.
6. Con archivo DEV protegido fuera del repo, definir TVEC_DEV_ENV_FILE, origen exacto y TVEC_DEV_TARGETS con database/broker/api_origin/identity; flags inicialmente false. Ninguna clave/URL con password figura en este informe.
7. **Detenerse y solicitar autorización operativa posterior al preflight.** El health público aprobado y las pruebas locales no sustituyen ese permiso ni el backup.
8. Tras autorización, coordinar escrituras/workers y aplicar exclusivamente en DEV `alembic upgrade head` de imagen nueva, comprobar0015, índices/FK/datos; nunca stamp. No dejar startup DDL competir con migraciones.
9. En ventana autorizada, TVEC_ENABLED=true y TVEC_INGEST_ENABLED=false para aprovisionar/verificar la identidad aislada, sin habilitar V2/evaluación. Operador: `python scripts/tvec_admin.py --register-identity <UUID_AUTORIZADO> --acknowledge-isolated-dev`, después `--verify-database`. Rechaza identidad incompatible y revisión distinta de0015; no sobreescribe.
10. Sólo con volumen expresamente autorizado, habilitar ingesta y arrancar worker -Q tvec. Ejecutar `python scripts/tvec_admin.py --create-run --max-pages 1 --acknowledge-isolated-dev` (página piloto100 por defecto). Guardar run_id; `--resume <RUN_ID>` sirve para interrupción del mismo presupuesto. No habilitar cron/beat ni una carga completa como smoke.
11. Comprobar procedencia, cursor, conteos y muestras sin datos privados; API/filtros/UI responsive y estado de SECOP/scores/triage. Apagar TVEC_INGEST_ENABLED tras el piloto, mantener registros/auditoría y decidir continuidad con métricas. Registrar evidencia y rollback disponible.

El CLI sin acciones opera offline y se deniega con defaults actuales; una opción de verificación abre conexión sólo si la configuración autorizada pasa primero. El CLI no migra ni despliega. Ninguno de los comandos operativos anteriores se ejecutó.

## 23. Procedimiento de rollback

Detener sólo publicaciones/worker TVEC del proyecto DEV, deshabilitar TVEC_INGEST_ENABLED y TVEC_ENABLED, revertir frontend/API/worker a imágenes conocidas compatibles. Conservar0015 y todas las tablas/historia; mantener SECOP y sus workers. No purgar Redis compartido, borrar órdenes, forzar downgrade, down -v, drop tables o restaurar sobre datos existentes.

La reversión de código no deshace órdenes importadas, revisiones, cursores, runs, metadata o marcador de identidad. Deben conservarse. Si se necesita recuperación de DB/storage, requiere respaldo y autorización aparte, restauración inicial en otro destino aislado y tratamiento explícito de escrituras posteriores al backup. Downgrade0015 sólo para tablas vacías descartables; probado así, no como estrategia operativa sobre información persistida.

## 24. Matriz de criterios de aceptación

| Criterio | Estado |
|---|---|
| Dataset/esquema/unidad verificados | Aprobado al corte;28 columnas, unicidad y frescura documentadas |
| Ingesta idempotente/aislada/recuperable | Aprobado local, fuente simulada, DB/Redis/workers reales |
| Órdenes fuera de Opportunity/ranking/cobertura/alertas | Aprobado por arquitectura y regresiones |
| Selector, filtros, tarjetas, detalle y persistencia | Aprobado en E2E sintético |
| Móvil/tablet/desktop | Aprobado en cuatro tamaños y capturas; no certificación total AA |
| Compradores/proveedores/instrumentos/periodos | Aprobado como historial local por nombre; no monetario ni vigencia |
| Seguridad/roles/planes | Guardias y autenticación aprobadas; matriz comercial POR CONFIRMAR, sin cambios de licencias |
| Matcher/modelo V2 intactos | Aprobado por hashes y pruebas |
| Migraciones/rollback | Aprobado sobre PG descartable; downgrade con datos denegado |
| Rendimiento | Medido con10k sintéticos,5 consultas constantes; límites explícitos |
| Regresión comercial | Backend/PG/Redis y E2E anterior aprobados |
| Identidad DB/broker y backup DEV | **Pendiente**, no comprobados operativamente |
| Publicación y autorización de despliegue | **No ejecutadas**, requieren orden posterior |
| Validación operativa DEV | **No terminada**; no afirmar despliegue por completar QA local |
| STG/producción | Sin operaciones/pipelines de esta tarea; fuera del alcance |

## 25. Recomendaciones para promoción futura

Completar preflight/autorización DEV y piloto acotado antes de proponer otra promoción. Verificar deriva/frescura y unicidad en más cortes, política de bajas/historia, moneda con fuente oficial adicional y catálogo de instrumentos con fechas/proveedores realmente verificables. Definir matriz Free/Pro con negocio sin introducir límites arbitrarios.

Evaluar ventanas de reconciliación, presupuesto diario, tiempos SQL y recursos del worker con evidencia; no multiplicar tareas o resetear cursores para ocultar faltas de cobertura. Cualquier RFQ activa necesita otra fuente/contrato y revisión de elegibilidad. Una futura asociación de patrones TVEC al perfil requerirá ranking/evaluación independientes, nunca reutilizar órdenes como ofertas abiertas.

STG y producción requieren autorización independiente. Antes de cada promoción repetir pruebas sobre el commit exacto, comparar schema, conservar rollback/backup y mantener flags/ingesta masiva apagados hasta aprobación específica. Esta entrega sólo prepara ese proceso y no dispara despliegues.
