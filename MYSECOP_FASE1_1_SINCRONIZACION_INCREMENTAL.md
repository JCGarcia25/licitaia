# MySECOP — Fase 1.1: sincronización incremental SECOP

## Estado y alcance

Implementación local integrada con la API de sincronización y Celery, probada con fuente simulada y SQLite. **No está certificada para DEV ni PostgreSQL o Socrata reales.** No se ejecutaron despliegues, commits, sincronizaciones externas ni operaciones sobre producción.

## Arquitectura y modelo

`SyncCursor` (`backend/app/db/models.py`) mantiene una fila compartida por fuente con identificador de dataset, clave de progreso, marca máxima, modo, estado, último éxito, contadores y arrendamiento. `SyncRun` mantiene la auditoría por usuario; los contadores de uso comercial siguen independientes. El cursor controla la ingesta común, no concede acceso a historiales de otros usuarios.

La migración reversible `backend/alembic/versions/0010_sync_cursor.py` crea `sync_cursors`. No modifica ni elimina registros existentes durante upgrade. La creación detecta la tabla preexistente porque la migración inicial histórica utiliza los modelos actuales en `create_all`.

## Paginación y reconciliación

El cliente usa `fetch_cursor_page`: selecciona `:id` de Socrata como `sync_row_id`, ordena en modo incremental por `(marca temporal, :id)` y solicita claves posteriores con `$where`, sin `$offset`. Los campos declarados por el proyecto son:

| Fuente | Dataset | Marca declarada | Estrategia |
|---|---|---|---|
| SECOP II procesos | `p6dx-8zbt` | `fecha_de_ultima_publicaci` | Incremental más reconciliación por `:id`. |
| SECOP II contratos | `jbjy-vk9h` | `ultima_actualizacion` | Incremental más reconciliación por `:id`. |
| SECOP I | `e985-4d7e` | `fecha_de_ultima_publi`, no verificada | Reconciliación continua por `:id`; no se usa esa fecha como cursor incremental. |

Tras agotar una exploración incremental se inicia un barrido de reconciliación por `:id` para detectar registros sin fecha o cambios fuera de la ventana. Al terminar ese barrido, SECOP II vuelve al modo incremental desde la última marca máxima menos 15 minutos; SECOP I reinicia su barrido. Una ejecución limitada por páginas reanuda el mismo modo y clave en la siguiente. La reconciliación de datasets extensos puede tardar muchas ejecuciones y no garantiza visibilidad inmediata de cambios antiguos.

Las fechas de los campos de origen y su significado como actualización, disponibilidad y unicidad/orden de `:id` **no se han verificado contra Socrata durante esta tarea**. En especial, una fecha de publicación puede no cambiar cuando se edita otro campo. No se debe habilitar esta versión en un ambiente conectado sin validar los metadatos y comportamiento reales de cada dataset. Si el proveedor devuelve claves ausentes, repetidas o fuera de orden, se detiene la página y se conserva el progreso confirmado.

## Transacciones y fallos

`sync_source` procesa una página por transacción. Los inserts o actualizaciones, estadísticas de la corrida y cursor se confirman juntos. Si falla la descarga, normalización, generación de vector o persistencia, se revierte el lote actual, se registra el error y se conserva el cursor del último lote confirmado. Al reintentar se procesa nuevamente ese lote. Los registros existentes se actualizan manteniendo su identificador, relaciones y fecha de cierre no provista por la fuente; el vector solo se regenera si cambió el texto. No se borran registros.

El cliente reintenta hasta cuatro intentos para 429, 502, 503, 504 y errores temporales de red, con espera exponencial. Se registran número de páginas, insertados, actualizados, sin cambios y errores; `duplicates` se mantiene por compatibilidad e incluye actualizados y sin cambios. El contador acumulado del cursor mide filas procesadas, no registros únicos ni cobertura completa.

## Concurrencia y recuperación

Cada fuente utiliza un arrendamiento en base de datos con token aleatorio y vencimiento de diez minutos, adquirido mediante actualización condicional. Antes de confirmar un lote, se verifica y renueva el token dentro de la misma transacción. Si otro ejecutor reemplazó el arrendamiento, el lote se revierte. Una caída deja el bloqueo hasta su vencimiento y permite reanudar desde la última página confirmada. Si una página tarda más de diez minutos, la ejecución puede perder el bloqueo y deberá reintentarse; no hay renovación durante la descarga o el procesamiento.

El scheduler existente usa `sync_source`; se agregó la tarea Celery `app.workers.tasks.sync_secop_source_task`, que acepta fuente y máximo de páginas. La API manual conserva su contrato. Consultas parciales con `since` o `extra_where` se rechazan en este servicio para no contaminar el cursor compartido: ningún consumidor revisado las pasa actualmente.

## Archivos de esta fase

- `backend/app/db/models.py` y `backend/alembic/versions/0010_sync_cursor.py`.
- `backend/app/services/secop_client.py` y `backend/app/services/ingest.py`.
- `backend/app/workers/tasks.py`.
- `backend/tests/test_incremental_sync.py` y `backend/tests/test_secop.py`.

Se conservaron los cambios locales previos ajenos a esta fase.

## Pruebas y limitaciones

Pruebas con SQLite y cliente simulado: primera carga, cambio, repetición sin duplicados, conservación de relación de usuario, empates de marca, fallo entre páginas y reanudación, fallo al persistir sin avance, reconciliación SECOP I, bloqueo de ejecuciones concurrentes y 429 en el cliente. La comprobación por claves valida la consulta generada, no su aceptación real por Socrata. La suite backend completa terminó con **68 pruebas aprobadas** y 623 advertencias; el informe se conserva en `/tmp/mysecop-full-tests.log` en esta máquina.

Migración `0010` aplicada y revertida sobre SQLite aislado después de marcar la base de prueba en `0009`. La cadena completa desde una base SQLite vacía falla previamente en `0003_password_reset`: `0001` crea columnas de los modelos actuales y `0003` intenta agregarlas nuevamente. Es una limitación preexistente que debe resolverse o verificarse en una copia segura antes de una instalación nueva.

PostgreSQL y Docker no están disponibles en este entorno: **no se probaron bloqueo, migración ni aislamiento con PostgreSQL**. No se probaron respuestas reales, metadatos o colaciones de Socrata, ni carga con millones de registros. Las advertencias de la suite incluyen deprecaciones de FastAPI y fechas, ciclo de claves de modelos y configuración de prueba; no se silenciaron.

## Validación posterior en DEV

1. Revisar los cambios y las credenciales/configuración del entorno, verificando que apunte exclusivamente a DEV.
2. En una base PostgreSQL aislada restaurada desde una copia autorizada, ejecutar upgrade/downgrade de la migración y pruebas de concurrencia con dos sesiones y pérdida de conexión.
3. Verificar con consultas acotadas y autorización los metadatos de cada dataset, `:id`, alias, tipos y semántica de cada marca de tiempo; medir primera carga, reconciliación y 429. Evitar sincronizaciones masivas no autorizadas.
4. Probar worker y API con pocos registros, interrupción y reinicio, contadores, reintento y duplicados; verificar que una ejecución bloqueada no consuma cuota gratuita.
5. Solo después de pruebas aprobadas y revisión, seguir el proceso de promoción de ambientes autorizado.

## Rollback

Antes de desplegar, respaldar la base. Revertir el código y restaurar el servicio anterior según el flujo de ambientes; si se decide revertir el esquema, ejecutar downgrade de `0010` **solo después de detener los procesos que usen el cursor**. El downgrade elimina el estado de progreso, no las oportunidades. Una reingesta posterior puede repetir páginas y el rollback del código no restaura valores de oportunidades ya actualizadas; la recuperación de esos valores requiere el respaldo apropiado.
