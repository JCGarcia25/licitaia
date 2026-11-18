# TVEC — recorrido completo de RFQ abiertas en DEV

## Alcance autorizado

Recorrer todas las páginas del listado oficial integrado con filtro Producción y
persistir únicamente RFQ explícitas, dentro del plazo publicado y con detalle
coincidente. La consulta de preparación encontró 47 páginas: 46 completas de 15
filas y una última de 2, aproximadamente 692 eventos. Son observaciones de origen,
no un resultado operativo ni un número fijo impuesto al recorrido.

No se completa el histórico de órdenes ni se descargan documentos. El portal
separado de Simuladores Web no está integrado. La cobertura se refiere al listado
público en Producción recorrido, no a toda TVEC ni a habilitación empresarial.

## Implementación

0017_tvec_full_scan añade una columna JSON nullable a los snapshots: cursor,
generación, límites de paginación, firmas de cabecera, IDs vistos, contadores y
candidatas abiertas en staging. No cambia tablas comerciales, matcher ni órdenes.

Cada tarea usa como máximo dos páginas nuevas, más la cabecera para verificar que
la paginación no cambió, y detalles sólo de RFQ candidatas. Guarda cursor y staging
atómicamente. No mantiene transacción abierta durante HTTP. Lease CAS de 5 minutos,
fencing antes del commit y protección de generaciones para tareas repetidas.
La siguiente tarea continúa la misma generación después de 2 segundos.

Un cambio en la cabecera o total de páginas reinicia la generación sin mezclar
resultados, con hasta tres reinicios. Duplicados entre páginas, reducción de página,
formato inesperado, timeout o más de 1000 páginas detienen el avance; no se afirma
que el recorrido terminó. El cursor previamente confirmado queda conservado.
Las fechas ausentes se excluyen como no verificables; un formato nuevo no se adivina.

RFI, tipos ambiguos, RFQ cerradas/futuras/adjudicadas y detalles contradictorios se
descartan antes de persistir eventos. Sólo se guardan contadores e IDs de control
para esos descartes, sin sus textos/documentos. Se preservan los registros antiguos
ya existentes; no se borran. Sólo una publicación completa cambia la lista visible.
Si una candidata venció o su verificación tiene más de 45 minutos al publicar, queda
fuera. El GET vuelve a filtrar fechas y antigüedad en cada consulta.

El frontend diferencia publicación parcial, recorrido en curso y recorrido completo
del listado integrado. Conserva elegibilidad pendiente y enlace oficial. La lista
anterior se mantiene durante el barrido, sometida a sus filtros de vigencia/edad.
Los refrescos de 15 minutos continúan una generación en curso o inician una nueva;
no crean barridos paralelos. Una entrega repetida de una generación terminada no
reanuda ni inicia otra. El periodo mínimo de 1 minuto evita redelivery inmediata.

La fuente es HTML paginado y diferido, no una API transaccional de Coupa. Recorrer
sus páginas con límites y cabecera estables no certifica un snapshot global en tiempo
real. Las RFQ sin marcador inequívoco siguen fuera de la lista; no se inventa su tipo.

## Despliegue y validación

Se usa el flujo GitHub Actions de DEV con respaldo restaurado en PostgreSQL temporal,
migración aditiva y verificación de identidad DB/Redis/origen. La herramienta de
operación espera al final del recorrido y comprueba por HTTPS autenticado la marca
de cobertura completa antes de declararlo verificado. No dispara el piloto histórico.

Pruebas preparadas y ejecutadas antes de publicar: suite backend completa; casos de
reanudación tras fallo de red, publicación final, filtrado sólo de abiertas, reinicio
ante cambios de cabecera, generación repetida y JSON persistente. PostgreSQL real
temporal valida upgrade desde 0016 con datos, dos workers, expiración de lease,
rollback, preservación de órdenes/puntajes y downgrade protegido. HTML de estas
pruebas de concurrencia es sintético; la ejecución DEV usa fuente/DB/Redis/Celery reales.
Build y TypeScript, más Chrome con API sintética en 320/390/768/1440, prueban estados
completo/en curso, búsqueda, histórico, errores y consulta vencida.

Los resultados exactos, advertencias y logs quedan en MYSECOP_TVEC_RECORRIDO_COMPLETO_DEV.json
y backend/benchmarks/tvec/full-scan/. No se consideran ejecutadas las integraciones
opt-in omitidas en la suite normal. Las deprecaciones heredadas siguen registradas.

## Rollback

Desactivar el refresco de cotizaciones DEV y volver al flujo acotado anterior,
conservando 0017 y las guardias que reconocen su revisión. Mantener el último
snapshot publicado; no borrar candidatas, eventos ni órdenes. No ejecutar downgrade
0017 si scan_progress contiene datos: se bloquea para conservar el cursor y la
información de control. No restaurar un backup sobre la base activa como rollback
rutinario. STG/producción requieren autorización independiente.

## Estado

Preparado localmente. El recorrido real DEV se documentará al terminar GitHub Actions;
no se declara completo únicamente por haber publicado código o llegado a dos páginas.
