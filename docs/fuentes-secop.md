# Fuentes SECOP verificadas

Verificación realizada el **2026-10-27** contra las fuentes oficiales. Este
documento es la referencia de todos los identificadores y campos usados por el
conector (`app/services/secop_client.py`). Ningún endpoint o campo fue inventado.

## Datasets verificados en datos.gov.co (plataforma Socrata)

| Fuente | ID Socrata | URL oficial | Uso en LicitaIA |
|---|---|---|---|
| SECOP II — Procesos de Contratación | `p6dx-8zbt` | https://www.datos.gov.co/Estad-sticas-Nacionales/SECOP-II-Procesos-de-Contrataci-n/p6dx-8zbt | Fuente principal del Agente 1 (procesos abiertos) |
| SECOP II — Contratos Electrónicos | `jbjy-vk9h` | https://www.datos.gov.co/Estad-sticas-Nacionales/SECOP-II-Contratos-Electr-nicos/jbjy-vk9h | Análisis histórico de contratos (~5,7 M filas) |
| SECOP I — 202002 | `e985-4d7e` | https://www.datos.gov.co (Socrata foundry `e985-4d7e`) | Procesos legacy cuando corresponda |
| SECOP Integrado (referencia) | `rpmr-utcd` | https://www.datos.gov.co/Estad-sticas-Nacionales/SECOP-Integrado/rpmr-utcd | Referencia cruzada (no se ingiere por defecto) |

## API y paginación (verificado en dev.socrata.com)

- Endpoint de datos: `https://www.datos.gov.co/resource/{dataset}.json`
- Paginación: `$limit` (máximo/default 1.000 por solicitud) + `$offset`
- Filtros: `$where` (p. ej. sobre la fecha de actualización) y `$order`
- Identificación: header `X-App-Token` (SODA 3.0/2.x) — da un límite por aplicación
  en lugar de por IP; sin token el throttle es mucho menor. Al excederlo la API
  responde **HTTP 429** → el conector reintenta con backoff exponencial (sin evasión).
- Portal: https://dev.socrata.com/docs/app-tokens.html y https://dev.socrata.com/docs/queries/limit.html

## Campos reales verificados (muestra viva de la API, 2026-10-27)

`p6dx-8zbt` (49 columnas verificadas, ~9,4 M filas): `id_del_proceso`, `entidad`,
`nit_entidad`, `departamento_entidad`, `ciudad_entidad`, `nombre_del_procedimiento`,
`descripci_n_del_procedimiento`, `modalidad_de_contratacion`, `tipo_de_contrato`,
`codigo_principal_de_categoria`, `precio_base`, `estado_del_procedimiento`,
`estado_resumen`, `fase`, `fecha_de_publicacion_del`, `fecha_de_ultima_publicaci`,
`urlproceso`, `adjudicado`, `valor_total_adjudicacion`, `proveedores_invitados`, …

`jbjy-vk9h` (80 columnas verificadas): `id_contrato`, `nombre_entidad`, `nit_entidad`,
`objeto_del_contrato`, `valor_del_contrato`, `fecha_de_firma`, `fecha_de_fin_del_contrato`,
`estado_contrato`, `modalidad_de_contratacion`, `proveedor_adjudicado`, `urlproceso`,
`ultima_actualizacion`, `es_pyme`, …

## Limitaciones confirmadas (TODO verificado, no suposiciones)

1. **`p6dx-8zbt` NO expone fecha de cierre del proceso.** Solo expone
   `fecha_de_publicacion_del` y `fecha_de_ultima_publicaci`. Por eso los
   recordatorios de cierre y el indicador "próximos a cerrar" usan la fecha de
   cierre **analizada en pliegos** (Agente 2) o **ingresada manualmente** por el
   usuario. La fuente oficial permanece como referencia definitiva.
2. **Fecha de actualización del dataset ≠ estado del expediente**: la columna
   `fecha_de_ultima_publicaci` refleja actualizaciones de registro en el portal,
   no el estado real del proceso; el estado real se lee de
   `estado_del_procedimiento` y el vínculo `urlproceso` lleva al expediente original.
3. **Anexos/pliegos no vienen en el dataset**: la API de datos abiertos no entrega
   los documentos del proceso. LicitaIA permite adjuntarlos manualmente (PDF/DOCX/XLSX)
   o procesar enlaces públicos accesibles legalmente. No se evade ningún mecanismo
   de seguridad (CAPTCHA, autenticación, etc.).
4. **SECOP I (`e985-4d7e`)**: el nombre exacto de la columna de marca de tiempo
   (`fecha_de_ultima_publi`) requiere verificación en tiempo de ejecución; el
   conector hace fallback a ingesta por páginas sin filtro si no existe. TODO(verificado-en-producción).
5. **`opciones.colombiacompra.gov.co/transparencia/datos-json`** responde, pero el
   portal recomienda los datasets Socrata de datos.gov.co como vía primaria; el
   listado oficial de conjuntos está en
   https://www.colombiacompra.gov.co/transparencia/datos-abiertos/conjuntos-de-datos-abiertos
   y el manual oficial en
   https://www.colombiacompra.gov.co/wp-content/uploads/2024/09/manual_de_datos_abiertos_actualizado.pdf

## Obligaciones implementadas

- Ingesta incremental con `$where` sobre la fecha de actualización y `$order`.
- Upsert idempotente (restricción única `source + source_id`) → sin duplicados.
- Registro de `published_at` (fuente), `captured_at` (ingesta) y `updated_at`.
- Enlace directo al proceso original (`url_oficial` = `urlproceso`).
- Gestión de procesos cancelados/retirados (marca `cancelled`, penalización en score).
- Respeto de límites: `X-App-Token`, paginación de 1.000, backoff ante 429.
- Auditoría de cada corrida en la tabla `sync_runs` (visible en /api/sync/runs).
