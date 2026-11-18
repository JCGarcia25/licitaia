# MySECOP — Cotizaciones TVEC vigentes en DEV

## Alcance

Fuente pública: https://operaciones.colombiacompra.gov.co/eventos-cotizacion-tvec
Detalles: https://operaciones.colombiacompra.gov.co/detalle-cotizacion/<id>
Consulta inicial oficial (17-11-2026): 2 páginas, 30 eventos; 8 RFQ con detalle
coincidente, 6 RFI y 16 eventos incompletos, sin marcador inequívoco o sin detalle
coincidente excluidos. Lectura acotada; no se amplió el historial de 100 órdenes.
No se verificó una API documentada. Se adapta el HTML oficial con validación de esquema.

## Selección y participación

Una cotización visible exige marcador RFQ inequívoco en el título (sin RFI), campos
requeridos completos, estado Producción, inicio <= ahora < cierre, ausencia de
adjudicación y coincidencia del detalle público en ID/título/entidad/instrumento/
fechas/estado. Es evidencia textual explícita, no un campo estructurado de tipo RFQ.
Las RFI, nombres genéricos y contradicciones no se convierten en cotizaciones.
No se interpreta valor cero como presupuesto. No se guarda el nombre del comprador.

La elegibilidad siempre es PENDING_VERIFICATION: depende del instrumento, proveedor,
categoría y región. No se modificó el matcher ni se calcularon puntajes de participación.
El enlace es «Consultar evento en la fuente oficial», no una promesa de poder ofertar.
Referencia de participación: https://operaciones.colombiacompra.gov.co/ciudadanos/preguntas-frecuentes/acuerdos-marco?page=1
Guía pública y corte de actualización: https://www.colombiacompra.gov.co/wp-content/uploads/2024/08/cce-gam-gi-63-_guia_general_de_los_acurdo_marco_de_precioc_v2_23-05-2024_1.pdf

## Arquitectura y límites

0016_tvec_quotations agrega dos tablas separadas de órdenes y SECOP: eventos y estado
de snapshot. Actualización por Celery/Redis cada 15 minutos sólo con flags DEV y
lista exacta DB/broker/origen más identidad existente verificada. Tope 2 páginas de
15 filas y hasta 30 detalles por actualización; sin documentos adjuntos, barrido total
ni ingesta histórica adicional. Timeout, respuesta limitada a 1,5 MB, reintentos
acotados para red/429/5xx; sin seguir redirecciones a otros dominios.

Lease de 5 minutos con adquisición CAS; HTTP fuera de transacciones; publicación
atómica y fencing antes del commit. Una tarea duplicada ocupada no consulta la fuente.
Los registros ausentes de la última muestra quedan ocultos, sin borrarlos. Los fallos
conservan la última publicación y anotan error; después de 45 minutos se ocultan
cotizaciones de consultas vencidas. También se excluyen cierres vencidos al consultar.

El GET autenticado /api/tvec/quotations filtra/busca/pagina en la base local. El
frontend actualiza esta lectura cada minuto; no dispara scraping por usuario.
Fuente, hora de consulta, cobertura parcial y elegibilidad se muestran en pantalla.
Las fechas oficiales sin offset se interpretan como hora de Colombia y se almacenan
UTC; se declara esa interpretación. No se garantiza estado transaccional de Coupa.
No se incluyen eventos del portal separado de Simuladores Web ni todos los eventos
anteriores a las dos páginas consultadas. No se declara cobertura completa de TVEC.

## Interfaz

Tienda Virtual abre Cotizaciones vigentes; el historial permanece accesible como
Inteligencia de mercado · histórico. Búsqueda y selección persistidas en URL/sesión;
parámetros tq_* separados de tv_* y SECOP. Estados de carga/error/reintento/vacío/
consulta vencida y enlaces oficiales. No se cambian frontend público ni Contacto.

## Migraciones y despliegue

Cadena 0015 -> 0016 aditiva, sin reescribir historia ni stamp. Migraciones desde
base vacía y desde 0015, columnas/tipos/índices y puntajes existentes verificados en
PostgreSQL temporal. El downgrade 0016 se bloquea si cualquiera de las dos tablas
contiene datos. Herramientas de verificación reconocen explícitamente 0016.
GitHub Actions existente: preflight aislado, respaldo completo con restauración real,
upgrade, activación flags, reinicio sólo DEV y primera actualización con worker real.
No se habilita el marcador del piloto histórico de 100 órdenes en esta publicación.

## Pruebas previas a publicar

- Suite backend: 162 aprobadas, 27 omitidas y 1541 advertencias.
- Nuevas pruebas sintéticas: 5; parser, RFI/ambiguos, inconsistencias, fechas, filtros,
  TTL, desapariciones, errores y fencing. HTTP simulado en estas pruebas.
- PostgreSQL real aislado: 1 nueva integración (migraciones/paridad, dos workers,
  expiración de lease, rollback y downgrade protegido) y 14 regresiones históricas.
  El cliente remoto es simulado en las pruebas de concurrencia.
- Adaptador real contra fuente oficial: 30 filas y sus detalles RFQ; sin persistencia.
- Build y TypeScript aprobados. Navegador Chrome real, API sintética, 320/390/768/1440:
  nueva vista, búsqueda persistente, histórico, errores/reintento y consulta vencida.
- Regresión histórica de navegador documentada con resultado final junto a evidencia.

Advertencias pendientes: datetime.utcnow/on_event/crypt, Starlette TestClient, ciclo
FK companies-users y deprecaciones Node. Lint sigue omitido por configuración previa.
Los logs conservan advertencias; no se presentan las pruebas omitidas como ejecutadas.

## Rollback

Desactivar TVEC_EVENTS_ENABLED y TVEC_EVENTS_REFRESH_ENABLED en la configuración de
activación DEV, recrear API/worker/beat y volver a mostrar el histórico como vista
principal. Conservar tablas/datos de 0016 y compatibilidad de revisión en tvec_admin.py
y evaluation_target.py. No revertir esas guardias a una versión que rechace 0016.
No ejecutar downgrade con snapshots/eventos presentes ni restaurar el respaldo sobre
la base activa como rollback rutinario. No borrar las 100 órdenes existentes.

## Estado operativo

Preparado y validado localmente. La publicación DEV y evidencia final se registran
al finalizar GitHub Actions en MYSECOP_TVEC_COTIZACIONES_DEV.json.
