# TVEC — habilitación y piloto controlado en DEV

Autorización: 2026-11-17, habilitar la ingesta y desplegar controladamente,
tras proponer al usuario una primera carga de una página, hasta 100 órdenes.

Se mantiene GitHub Actions como único acceso operativo al servidor. Sólo develop
activa este cambio. La configuración DEV fija TVEC_INGEST_ENABLED=true,
TVEC_PAGE_SIZE=100 y TVEC_MAX_PAGES=1. No se añade calendario ni sincronización masiva.
El preflight permite esta configuración habilitada sólo con identidad verificada,
ninguna ejecución PENDING/RUNNING y ningún lease vigente; conserva el respaldo
PostgreSQL completo con restauración comprobada antes de migrar/desplegar.

El marcador [tvec-pilot-100] en el mensaje del push autoriza el paso de piloto
únicamente para esa publicación DEV. Despliegues ordinarios no inician cargas.
backend/scripts/tvec_dev_pilot.py usa un UUID determinista para esta autorización:
un reintento reutiliza la ejecución y su presupuesto persistente de una página.
Se usa el worker Celery real, broker Redis real, PostgreSQL real y el cliente
oficial sin simulaciones. Si falla, no se crea otro run ni se amplía el presupuesto.
Se esperan los resultados y se verifican contadores, unicidad, cursor y liberación
del lease. Se vuelve a entregar el mismo run DONE al worker y se comprueba que
termina sin avanzar el cursor ni cambiar los contadores o añadir registros.

No se modifica el matcher, modelos comerciales ni frontend. La habilitación permite
futuras ejecuciones manuales de hasta 100 órdenes; no autoriza lanzarlas en bucle.
Un fallo en el piloto deja el estado conservado para diagnóstico, sin borrar datos.
Un fallo en activación restaura la configuración previa, igual que en el despliegue
anterior. Las órdenes cargadas no se convierten en oportunidades SECOP.

## Rollback

Desactivar TVEC_INGEST_ENABLED en DEV y recrear API/worker/beat mediante el flujo
operativo existente. Si hay una tarea activa, esperar su finalización acotada antes
de desplegar; conservar el run, cursor y registros. Revertir sólo este cambio y
volver a desplegar restablece los valores anteriores con la ingesta apagada.
No ejecutar downgrade 0015 después de cargar datos: su protección lo bloquea.
No restaurar un backup sobre la base activa como rollback ordinario, ni borrar datos.

## Evidencia

El resultado final, enlaces CI/deploy, conteos, cursor y prueba de entrega duplicada
se guardan en MYSECOP_TVEC_DEV_INGESTION.json cuando termine la ejecución real.
La validación anterior local de PostgreSQL/Redis se conserva en el informe de
integración; no se presenta como una nueva ejecución en este despliegue.
