# MySECOP — Recordatorios de cierre por oferta y guardados persistentes

Fecha: 18 de noviembre de 2026. **Implementado y verificado localmente; sin commit ni despliegue.** Base: develop `c9b622d`. Los cambios están conservados en el proyecto original, sin sobrescribir sus avances anteriores.

## Comportamiento

Cada tarjeta del Preparador de Ofertas incluye «Recordatorio de cierre». Abre un diálogo accesible para elegir fecha y hora en Colombia (America/Bogota, UTC−5). Se envía al correo de la cuenta, sin permitir escribir direcciones de terceros. Admite consultar, actualizar y cancelar un recordatorio activo por oferta. Un enlace del correo permite abrir la oferta mediante `?oferta=id`.

Cuando no existe `Opportunity.fecha_cierre`, el diálogo informa:

> No podemos programar este recordatorio porque no encontramos la fecha de cierre del proceso. Consulta el expediente en SECOP; podrás crear la alerta cuando la fecha esté disponible.

No se usan fechas estimadas del cronograma ni se permite introducir una fecha de cierre inventada. El servidor rechaza programación sin cierre, en el pasado, después del cierre o sin zona horaria. El usuario debe tener acceso Pro, correo verificado y servicio SMTP configurado, coherente con las restricciones del preparador y las alertas por correo. Los errores se presentan con mensajes orientados a la acción.

La tarea de envío comprueba cada minuto los registros vencidos de programación. Antes del correo vuelve a comprobar propietario, cuenta activa, acceso Pro, correo, estado de la oferta, cancelación del proceso y fecha de cierre. Si el cierre cambió o desapareció, bloquea el envío y solicita revisión. Las ofertas archivadas o presentadas no generan envíos pendientes. El recordatorio es independiente de las preferencias del resumen diario; programarlo es una solicitud expresa de ese envío.

Se conserva en UTC la hora seleccionada y se muestra en horario de Colombia. La precisión operativa es por minuto y depende de disponibilidad de workers y correo; se recomienda anticipación al cierre. «Enviado» significa aceptación por el servidor SMTP, no confirmación de lectura o entrega en bandeja.

## Persistencia y concurrencia

Tabla `offer_closing_reminders` con una fila por oferta: propietario, fecha programada, cierre conocido, destinatario, estado, intentos, token de toma, fecha de aceptación y próximo reintento. La fecha original del usuario no se reemplaza por la fecha de un reintento técnico.

Un worker toma atómicamente la fila antes del SMTP; otro worker no puede reclamarla de nuevo. No se mantiene una transacción o bloqueo de fila durante el contacto con SMTP. Los fallos conocidos anteriores al envío o rechazos temporales admiten hasta tres intentos, separados cinco minutos y sujetos a revalidación del cierre.

SMTP y PostgreSQL no ofrecen una transacción conjunta: no se promete exactamente una entrega en todas las caídas posibles. Ante resultado ambiguo o una toma abandonada durante más de cinco minutos, el estado pasa a «Envío sin confirmar» y no se reenvía automáticamente. El usuario recibe advertencia de posible duplicado si decide programarlo de nuevo. Una oferta con envío en curso no puede modificarse, cancelarse o eliminarse hasta resolver ese estado.

## Guardar procesos

Se añadió `UserOpportunity.is_saved`, separado del triage. Crear una oferta conserva el guardado y marca el proceso como guardado; retirarlo de guardados conserva la oferta y su estado. El guardado es propio de cada usuario y no altera puntajes, razones, versiones del matcher o datos de otros usuarios.

Las búsquedas GET y POST priorizan guardados en SQL antes de ordenar los demás resultados y paginar. Los guardados deben cumplir los filtros, permisos y reglas de vigencia; no se fuerza la aparición de procesos que no coinciden. También se priorizan en el listado del preparador. El resumen solicita `prioritize_saved=false` para conservar su orden por compatibilidad.

Se mantiene la compatibilidad de los estados antiguos: la migración recupera guardadas/proyectos donde existe ese estado y el serializador admite registros antiguos con el nuevo campo nulo. No se elimina el estado de proyecto al dejar de guardar.

## Migración y despliegue posterior

Nueva revisión `0018_offer_closing_reminders`, sobre `0017_tvec_full_scan`. Añade el indicador guardado y la tabla de recordatorios, con índices y relación por oferta. Es idempotente frente al arranque histórico basado en los modelos actuales. No modifica migraciones aplicadas ni utiliza stamp.

Los verificadores de destinos que listaban revisiones conocidas se actualizaron para aceptar 0018, conservando las mismas restricciones de entorno y destino. No se habilitó TVEC en otro entorno.

Para poner en DEV: usar el flujo existente, ejecutar Alembic upgrade head antes del código nuevo, mantener SMTP configurado y verificar worker/beat y un buzón QA autorizado. El despliegue no se realizó durante esta tarea. No se enviaron correos a usuarios reales para las pruebas.

El downgrade conserva datos: se bloquea si hay recordatorios o un guardado independiente que no pueda representarse sin pérdida en el triage antiguo. Revertir interfaz o workers no requiere borrar recordatorios ni revertir esquema; preparar imágenes compatibles con 0018. No forzar un downgrade ni eliminar información para hacer pasar una reversión.

## Pruebas ejecutadas

| Prueba | Resultado y alcance |
|---|---|
| Suite backend completa | 208 aprobadas, 33 optativas omitidas, 1646 advertencias |
| API/servicio nuevos | Incluidos en la suite: cierre desconocido, horario inválido, conversión UTC, persistencia, actualización, cancelación, otro usuario, SMTP, caducidad, cambio de cierre y límite de reintentos |
| Guardados | Persistencia, idempotencia, prioridad anterior a paginación GET/POST, continuidad al crear oferta, retirada sin perder proyecto, listado del preparador y filtro de otro usuario |
| PostgreSQL nuevo | 2 aprobadas: instalación desde esquema 0017, legado preservado, upgrade/downgrade vacío, bloqueo de downgrade poblado, dos workers y ausencia de bloqueo sobre SMTP |
| PostgreSQL/Redis/Celery nuevo | 1 aprobada: futuro no se envía, activación al vencer y dos entregas simultáneas producen un solo mensaje sintético |
| PostgreSQL histórico | 14 aprobadas en cuatro módulos de regresión |
| TVEC PostgreSQL/Redis | 4 aprobadas con fuentes sintéticas; nueva revisión compatible |
| Frontend | Build y TypeScript correctos; diff check correcto |
| Navegador con API real local | 8 combinaciones: 320, 390, 768, 1440 px, temas claro/oscuro; programar, volver a abrir, cancelar, ausencia de cierre, foco/Escape, guardados primeros y sin desbordamiento |
| Accesibilidad automática | Sin infracciones axe en el diálogo de los escenarios evaluados |

Los tests de envío usan dobles de SMTP o un buzón de captura; PostgreSQL, Redis y los workers de integración son procesos reales descartables. No equivalen a entrega externa a una bandeja real ni validan credenciales SMTP de DEV. Las pruebas de navegador usan usuarios y datos sintéticos con API/Next reales locales. No se probaron Safari, dispositivos físicos ni accesibilidad completa con lector de pantalla.

Las advertencias de deprecación y la advertencia histórica del ciclo de claves foráneas users/companies se conservaron en logs. Los fallos inyectados de red/DB de regresiones son casos negativos controlados, no incidencias observadas en producción. La suite base omite integraciones optativas; se ejecutaron por separado las relacionadas indicadas, sin afirmar que se repitieran todas las optativas del repositorio.

## Evidencias y archivos

Evidencias y capturas en `backend/benchmarks/offer-reminders/`. Manifiesto de ejecución: `MYSECOP_RECORDATORIOS_OFERTAS.json`.

- `backend/app/db/models.py`
- `backend/app/main.py`
- `backend/app/routers/agents.py`
- `backend/app/routers/opportunities.py`
- `backend/app/workers/celery_app.py`
- `backend/app/workers/tasks.py`
- `backend/scripts/evaluation_target.py`
- `backend/scripts/tvec_admin.py`
- `backend/scripts/tvec_quotations_admin.py`
- `backend/tests/isolated_match_worker.py`
- `frontend/app/(private)/app/ofertas/page.tsx`
- `frontend/app/(private)/app/page.tsx`
- `frontend/app/globals.css`
- `frontend/components/secop-opportunities.tsx`
- `scripts/tvec-dev-deploy.sh`
- `backend/alembic/versions/0018_offer_closing_reminders.py`
- `backend/app/routers/offer_reminders.py`
- `backend/app/services/offer_reminders.py`
- `backend/app/services/saved_opportunities.py`
- `backend/scripts/e2e_offer_reminders.py`
- `backend/scripts/test_isolated_offer_reminders.py`
- `backend/tests/test_offer_reminders.py`
- `backend/tests/test_postgresql_offer_reminders.py`
- `backend/tests/test_redis_offer_reminders.py`
- `backend/tests/test_saved_opportunities.py`
- `frontend/components/offer-reminder-dialog.tsx`
