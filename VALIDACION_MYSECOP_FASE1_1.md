# Validación técnica — MySECOP Fase 1.1

## 1. Resumen ejecutivo

**Dictamen: NO APTO PARA DEV conectado a SECOP.** Las pruebas locales están aprobadas, pero la fuente SECOP I tiene un mapeo de columnas incompatible con sus metadatos reales y no hay validación PostgreSQL. Hay además diferencias entre fecha de publicación y fecha de modificación que impiden certificar cobertura incremental.

Se consultaron públicamente los metadatos y páginas pequeñas de las tres fuentes, sin importar datos ni ejecutar sincronizaciones. Las pruebas automatizadas utilizaron SQLite y respuestas simuladas. No se realizaron despliegues, commits ni acciones sobre producción.

## 2. Estado de cada dataset

| Fuente | Comprobación real | Resultado y límites |
|---|---|---|
| [SECOP II procesos — p6dx-8zbt](https://www.datos.gov.co/api/views/p6dx-8zbt.json) | 59 columnas; todos los nombres de `FIELD_MAP` aparecen en metadatos. `fecha_de_ultima_publicaci` es `calendar_date`. | La descripción oficial indica **última publicación**, no actualización general. No demuestra que un cambio de cualquier campo avance el cursor. La consulta acotada encontró al menos un registro con la fecha nula. |
| [SECOP II contratos — jbjy-vk9h](https://www.datos.gov.co/api/views/jbjy-vk9h.json) | 95 columnas; todos los nombres de `FIELD_MAP` aparecen. `ultima_actualizacion` es `calendar_date`. | La descripción indica última actualización del contrato; no se verificó su comportamiento tras una modificación. La consulta acotada encontró al menos un nulo. |
| [SECOP I — e985-4d7e](https://www.datos.gov.co/api/views/e985-4d7e.json) | 72 columnas. Existe `ultima_actualizacion` de tipo `calendar_date`; el mapeo del código no coincide. | No existen `id_del_portafolio`, `nom_entidad`, `nit_entidad`, `tipo_de_proceso`, `fecha_de_publicacion` ni `fecha_de_ultima_publi`. El campo `uid` identifica una relación proceso–adjudicación; no se debe asumir sin análisis que equivale a una convocatoria. La consulta acotada de nulos no encontró uno: no demuestra ausencia total. |

Para SECOP I el `source_id` actual queda vacío, por lo que `_save_row` detiene el lote y conserva el cursor. Corregirlo requiere definir la identidad y procedencia de registros de adjudicación, revisar asociaciones y fuentes antiguas y crear pruebas; no se debe cambiar ciegamente por `uid`.

## 3. Consultas comprobadas y pendientes

Con `curl` y TLS del sistema se hicieron consultas públicas limitadas a una o dos filas, sin mostrar información de procesos o personas. Python `urllib` local falló por cadena de certificados; no se desactivó la verificación TLS. Las tres fuentes aceptaron `:id AS sync_row_id`, ordenamiento por `:id`, `$where :id > ...` y devolvieron `:id` en JSON como cadena. En la pequeña muestra, la página siguiente por `:id` coincidió con el segundo registro.

También aceptaron consultas por fecha y `:id`. En la muestra de SECOP II procesos se observaron dos filas con la misma marca temporal y la consulta compuesta devolvió una fila posterior. En contratos y SECOP I el filtro compuesto respondió correctamente pero no devolvió filas en esa muestra; no prueba exhaustividad ni todos los empates. Las consultas exactas del cliente con `$select=*, :id AS sync_row_id`, `$order` y límite uno respondieron para las tres fuentes. No se verificó que `:id` sea inmutable durante todo el ciclo de vida de cada dataset, ni que las fechas y `:id` tengan siempre la misma colación o precisión con todos los datos.

Ejemplos reproducibles de solo lectura acotada:

```bash
curl -fsS 'https://www.datos.gov.co/api/views/p6dx-8zbt.json'
curl -fsS --get 'https://www.datos.gov.co/resource/p6dx-8zbt.json' \
  --data-urlencode '$select=:id as sync_row_id,fecha_de_ultima_publicaci' \
  --data-urlencode '$where=fecha_de_ultima_publicaci IS NOT NULL' \
  --data-urlencode '$order=fecha_de_ultima_publicaci DESC, :id ASC' \
  --data-urlencode '$limit=2'
```

Repetir con los identificadores y campos de la tabla anterior; usar muestras pequeñas y no almacenar ni distribuir datos personales. La reconciliación incluye filas con fechas nulas, pero su cobertura y duración a escala real permanecen **no verificadas**.

## 4. PostgreSQL

No se encontró Docker ni ejecutables locales `postgres`/`initdb`; no se identificó una instancia PostgreSQL aislada autorizada. **No se ejecutaron pruebas PostgreSQL**, de dos workers PostgreSQL ni de migración en ese motor. SQLite no prueba los bloqueos, aislamiento, fallos de conexión ni semántica transaccional de PostgreSQL.

Procedimiento propuesto en una instancia efímera creada expresamente para pruebas, nunca en producción:

1. Preparar una base descartable en `0009_landing_visits`, con respaldo y credenciales propias de prueba; definir `DATABASE_URL` solo para ese proceso y comprobar host, puerto y nombre de base.
2. Desde `backend`, ejecutar `alembic upgrade 0010_sync_cursor`, inspeccionar la tabla y sus tipos, luego `alembic downgrade 0009_landing_visits` y repetir el upgrade. El downgrade borra el cursor: solo en base descartable.
3. Adaptar el fixture aislado `backend/tests/test_incremental_sync.py` para dos sesiones PostgreSQL: competir por el mismo cursor; interrumpir al primer worker durante descarga y transacción; verificar que solo el propietario confirme; dejar vencer el token y reanudar. El fixture actual crea SQLite directamente y **no se convierte en prueba PostgreSQL solo cambiando `DATABASE_URL`**.
4. Probar caídas de conexión y de worker antes y después de commit, reintentos, unicidad e idempotencia con fuente simulada. Conservar resultados sin secretos.

## 5. Concurrencia y arrendamientos

`backend/app/services/ingest.py` adquiere un token por fuente mediante actualización condicional, exige token y vencimiento vigente antes del commit de cada página y conserva registros y cursor en una transacción. Se añadió una renovación periódica en un hilo con sesión independiente: solo renueva el mismo token si aún está vigente. Si falla la renovación se registra la advertencia; el control de token del commit sigue siendo obligatorio. Se detiene el hilo al terminar.

Pruebas simuladas en SQLite: dos ejecuciones simultáneas, recuperación de bloqueo vencido, cambio de propietario antes del commit (el lote no se confirma) y renovación durante una consulta lenta. **No demuestran** comportamiento bajo bloqueos o particiones PostgreSQL, reloj divergente entre servidores, conexiones agotadas ni procesamiento real prolongado. Si las renovaciones fallan o el proceso pierde el token, el lote se revierte y se reintenta desde el último cursor confirmado.

## 6. Migraciones

`0001_initial.py` ejecuta `Base.metadata.create_all` con los modelos actuales, de modo que una base nueva recibe columnas de migraciones futuras; `0003_password_reset` después intenta agregarlas y falló en SQLite por columna duplicada. Esto también hace que `sync_cursors` pueda existir antes de `0010`, cuyo upgrade comprueba si la tabla existe. `0010` aplicada y revertida aisladamente sobre SQLite después de marcar la base en `0009` funcionó; esa prueba no valida toda la historia ni PostgreSQL.

No se modificaron migraciones históricas. Propuesta: ensayar en bases desechables una línea base congelada o una estrategia de instalación nueva con inspección y verificación de esquema; validar por separado bases ya migradas. No usar `stamp` para fingir un esquema compatible en DEV. El guard de existencia de `0010` tampoco valida que la tabla preexistente tenga todas las columnas esperadas.

## 7. Pruebas y advertencias

La suite completa se ejecutó en Python 3.12 con pytest, servicios simulados y SQLite; el resultado exacto está en el mensaje final y el log local `/tmp/mysecop-validation-final.log`. Las pruebas nuevas también cubren renovación, vencimiento y pérdida de titularidad. No se ejecutaron pruebas de extremo a extremo de API/Celery con PostgreSQL ni carga real de Socrata.

Las advertencias anteriores se agrupan así (el total de pytest cuenta instancias repetidas):

| Categoría | Origen observado | Evaluación |
|---|---|---|
| Deprecaciones | `datetime.utcnow`, `crypt`, `FastAPI.on_event`, compatibilidad TestClient/httpx | Requieren migración progresiva; pueden afectar futuras versiones. |
| Configuración de pruebas | JWT de pruebas con clave corta | Advertencia del entorno aislado; no prueba la longitud de claves de ningún servidor. |
| Modelos | Dependencia circular de claves foráneas `companies`/`users` al ordenar `create_all` | Riesgo de inicialización y migraciones; no se alteró el modelo histórico. |
| Riesgo funcional | Fecha de última publicación, columnas faltantes en SECOP I, contrato de `:id`, reloj y límites de arrendamiento | Los tres primeros proceden de revisión y consultas; los demás requieren pruebas adicionales. No todas estas observaciones son advertencias emitidas por pytest. |
| Otros | Advertencias de bibliotecas | Revisar el log completo antes de actualizar dependencias. |

## 8. Riesgos pendientes

1. El mapeo de SECOP I es incompatible y puede detener su sincronización completa.
2. PostgreSQL, migraciones en bases reales y propiedad de bloqueos no están probados.
3. Los campos de fecha no garantizan cambios monotónicos; la reconciliación puede demorar mucho y no garantiza captura inmediata de modificaciones históricas o eliminaciones.
4. No hay evidencia de consistencia de snapshot Socrata ni de comportamiento de `:id` ante reemplazo de filas, cambios simultáneos y todos los valores.
5. La renovación depende de otra conexión de base de datos; errores de conexión, contención y divergencia de reloj requieren pruebas. El arrendamiento no sustituye a los controles de transacción.
6. La migración histórica desde cero no es reproducible sin resolver la colisión de `0001` y `0003`.

## 9. Recomendaciones

Corregir y probar el modelo de identidad de SECOP I sin fusionar convocatorias y adjudicaciones; validar por separado cada campo del dataset. Ejecutar pruebas PostgreSQL aisladas y de fallos reales de worker/DB. Resolver la cadena de migraciones con una estrategia compatible y ensayada sobre copias desechables. Medir reconciliación y límites de recursos con datos simulados representativos; definir métricas de cobertura y antigüedad. Ejecutar una prueba DEV acotada solo cuando estos bloqueos estén resueltos y haya un plan de reversión.

## 10. Dictamen final

**NO APTO PARA DEV conectado a SECOP.** Existe código integrado y validado parcialmente con simulaciones y consultas públicas de lectura, pero la fuente SECOP I falla por su mapeo y faltan pruebas PostgreSQL y de migraciones completas. La validación externa limitada no certifica corrección integral ni cobertura de los datasets.
