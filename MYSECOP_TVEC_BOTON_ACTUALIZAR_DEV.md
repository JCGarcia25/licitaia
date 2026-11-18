# TVEC — botón de actualización compartida en DEV

## Comportamiento

«Actualizar cotizaciones TVEC» solicita el recorrido existente en segundo plano.
GET /api/tvec/quotations/refresh-status devuelve estado compartido, avance,
última publicación y espera restante. POST /api/tvec/quotations/refresh responde
202 con aceptación o reutilización, sin hacer scraping dentro de la petición HTTP.
Ambos requieren usuario activo, flags de refresco y destino DEV/identidad verificados.
No admiten parámetros para ampliar páginas, cambiar fuentes o activar órdenes.

Si existe recorrido RUNNING/SCANNING, se muestra y no se publica otra tarea.
Si la última publicación tiene menos de 5 minutos, se devuelve COOLDOWN. Una reserva
Redis SET NX de 300 segundos, por huella DB/broker/origen, limita solicitudes de
usuarios y procesos diferentes antes de publicar en la cola tvec. Es global para
la fuente de ese DEV, no por empresa ni por navegador. Se mantiene el refresco de
15 minutos y los lotes/fencing/filtros de RFQ vigentes del motor existente.

Se confirma la reserva con Lua CAS sin renovar su TTL tras enviar la tarea. Un fallo
de envío ambiguo conserva la reserva y se muestra UNCONFIRMED, no «iniciado».
Un fallo de Redis/broker devuelve 503 genérico sin credenciales. Reintentar no genera
otra publicación mientras exista reserva. Un reintento tras ERROR conserva el ID de
la generación pendiente; el estado del nuevo resultado distingue cola pendiente de
un fallo anterior. No se consultan backends de resultados fuera del destino revisado.

La interfaz muestra avance compartido, espera con contador y errores. Consulta el
estado cada 3 segundos mientras espera y cada 30 en reposo; no consulta la fuente
oficial desde el navegador. El polling no activa el bloqueo global de la página.
Al terminar recarga los resultados en segundo plano con la búsqueda/filtros actuales.
No altera la URL, el histórico, la elegibilidad pendiente, el matcher ni licencias.

## Persistencia y rollback

No se añade una migración: se conserva head 0017. La reserva Redis expira y el avance
sigue en PostgreSQL. Si falla la aplicación, quedan los mecanismos existentes de
reanudación y actualización automática. El rollback consiste en revertir el botón,
los dos endpoints y el coordinador, conservando 0017, eventos y cursor. Las tareas
ya aceptadas pueden terminar; no se borran registros ni se restaura la base como
rollback rutinario. Las claves temporales expiran a los 5 minutos.

## Validación

Suite backend completa: 171 aprobadas, 29 omitidas, 1541 advertencias heredadas.
Cinco pruebas nuevas cubren dos usuarios, autenticación, reutilización, cooldown,
fallos de envío, incertidumbre, Redis caído, flags y reintento tras fallo anterior.
Redis y publicación son simulados en esas pruebas unitarias.

Integración PostgreSQL/Redis real en instancias temporales: tres pruebas aprobadas,
incluidas las dos regresiones de cotizaciones/recorrido y ocho solicitudes concurrentes
con exactamente una reserva aceptada y una invocación al publicador. El publicador
es simulado en esa prueba de concurrencia; Redis NX/Lua y PostgreSQL son reales.

Chrome real con API sintética, 320/390/768/1440: solicitud única, progreso, bloqueo,
cooldown, resultados renovados, filtros preservados, recuperación al reabrir la
vista y ausencia de overlay bloqueante durante polling. Build y TypeScript aprobados.
No se considera ejecutada una integración opt-in por aparecer omitida en la suite.
Deprecaciones Python/Node y ciclo FK heredado permanecen registrados; lint conserva
su configuración previa de omisión.

El despliegue DEV usa GitHub Actions existente, respaldo completo con restauración,
verificación de 0017 y prueba por HTTPS autenticado: dos POST consecutivos deben
aceptar/reutilizar de forma segura y la segunda solicitud no publicar otra tarea.
Si la fuente ya está fresca se valida COOLDOWN; no se fuerza una carga innecesaria.
Si se acepta se espera a la publicación completa. Los tokens del smoke quedan en
memoria y expiran en un minuto; no se cambian cuentas ni se imprimen credenciales.

## Estado operativo

Pendiente de terminar GitHub Actions. El resultado real y sus limitaciones quedarán
en MYSECOP_TVEC_BOTON_ACTUALIZAR_DEV.json y backend/benchmarks/tvec/refresh-button/.
