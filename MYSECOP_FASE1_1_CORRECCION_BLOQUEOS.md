# MySECOP — Fase 1.1: corrección de bloqueos

Revalidación: **15 de noviembre de 2026**, zona America/Bogota. Este informe actualiza la evidencia anterior; los otros informes de Fase 1.1 conservan sus dictámenes históricos y no describen el estado actual.

## 1. Problemas originales

El mapeo de SECOP I usaba columnas inexistentes. La migración `0001` llama a `Base.metadata.create_all` con modelos actuales y, por ello, creaba por adelantado columnas y tablas que revisiones posteriores intentaban volver a crear. No se había ejecutado integración en PostgreSQL.

## 2. Correcciones realizadas

Se ajustó el mapeo de SECOP I a campos que aparecen en los metadatos oficiales, usando `uid` como identidad de **registro proceso–adjudicación**, no como identificador de convocatoria. La referencia del proceso y la adjudicación se conservan en `raw_json`; registros con un mismo proceso y adjudicaciones distintas no se fusionan. La fuente se clasifica como `HISTORICAL` y se excluye del conjunto de oportunidades potencialmente vigentes. No se borraron ni fusionaron registros existentes. Las filas sin UID fallan de forma segura sin avanzar el cursor de la página. Las nuevas pruebas para UID nulo y vacío verifican también el rollback de una fila válida anterior dentro del mismo lote. Las muestras de prueba son sintéticas, con campos reales y valores ficticios; no se incorporan registros personales consultados.

Las revisiones históricas `0003` a `0008` ahora comprueban si cada tabla, columna o índice ya existe antes de crearlo. Se trata de una modificación justificada de la ruta **upgrade** de esas revisiones: los entornos que ya las aplicaron no las vuelven a ejecutar; las bases nuevas y parcialmente avanzadas pueden evitar la duplicación. No se cambian datos ni se modificaron sus downgrades, salvo que la creación de la clave foránea de `0005` utiliza `batch_alter_table` cuando falta la columna. Un elemento ya existente con tipo o restricciones incorrectas **no se repara ni valida automáticamente** por una mera comprobación de nombre.

## 3. Mapeo de SECOP I

Fuente verificada: [metadatos oficiales e985-4d7e](https://www.datos.gov.co/api/views/e985-4d7e.json), mediante consultas públicas limitadas y sin guardar registros reales en la base del proyecto.

| Modelo / dato | Columna oficial | Significado y tratamiento |
|---|---|---|
| `source_id` | `uid` | Identificador de la relación entre proceso y adjudicación; identificador de fila de negocio para la fuente. |
| Proceso | `numero_de_constancia`, `numero_de_proceso` | Identificadores SECOP I y de la entidad; conservados en el JSON original. |
| Adjudicación / contrato | `id_adjudicacion`, `numero_de_contrato` | Referencias relacionadas, conservadas en JSON; no se confunden con apertura de convocatoria. |
| Entidad / NIT | `nombre_entidad`, `nit_de_la_entidad` | Datos de entidad compradora. |
| Ubicación | `departamento_entidad`, `municipio_entidad` | Ubicación de la entidad; no necesariamente lugar de ejecución. |
| Objeto / detalle | `objeto_a_contratar`, `detalle_del_objeto_a_contratar` | Descripción de la contratación. |
| Modalidad / tipo | `modalidad_de_contratacion`, `tipo_de_contrato` | Modalidad y tipo declarados por la fuente. |
| Valor | `cuantia_proceso` | Cuantía del proceso, no necesariamente valor final de contrato. |
| Estado | `estado_del_proceso` | Estado informado; no se usa para afirmar que recibe ofertas. |
| Fecha de registro | `fecha_de_cargue_en_el_secop` | Fecha de cargue en SECOP, usada como fecha disponible; no demuestra fecha de apertura ni cierre. |
| Actualización | `ultima_actualizacion` | Fecha de modificación declarada; se mantiene reconciliación por `:id`, sin asumir que la marca cubre todos los cambios. |
| Enlace | `ruta_proceso_en_secop_i` | Enlace proporcionado por la fuente. |

La clave de deduplicación es `(source, source_id)` bajo la restricción `uq_oportunidad_fuente`: para SECOP I es `(secop1, uid)`. Repetir la misma clave actualiza la fila conservando su ID y relaciones; adjudicaciones con UID distintos permanecen separadas aunque compartan proceso. No se reconstruye un UID faltante a partir del proceso ni se cambia automáticamente la identidad de filas antiguas. `sync_row_id` (`:id`) sirve para paginar, no para deduplicar el negocio.

Los campos originales y relaciones adicionales se conservan en `raw_json`. El UID no garantiza por sí solo deduplicación entre fuentes, ni identifica un proceso de manera canónica. No se han verificado cambios del UID o `:id` a lo largo de todo el ciclo de vida de los datos.

Una consulta pública limitada a dos filas devolvió UID, número de constancia e identificador de adjudicación en ambas; otra consulta con `uid IS NULL` y límite uno no devolvió filas. El 15 de noviembre se repitieron la descarga de metadatos (72 columnas) y una consulta limitada a dos filas con UID, referencias de proceso, adjudicación, contrato, estado y fechas; ambas contenían los cuatro identificadores. La consulta de nulos pertenece a la revisión anterior. Es una comprobación puntual de la fuente, no una garantía futura de unicidad o estabilidad.

## 4. Estrategia de migraciones

Se auditó la cadena lineal completa `0001` a `0010` (un solo head). `0001` usa modelos actuales; `0002` y `0009` ya tenían guardas de existencia. Se mantienen las guardas añadidas a `0003`–`0008`, sin congelar retrospectivamente el esquema de `0001`, lo que introduciría otro cambio en la instalación histórica. La estrategia evita DDL duplicado sin modificar datos en upgrade ni volver a ejecutar revisiones ya aplicadas.

Se probaron upgrade desde PostgreSQL vacío hasta `0002` y luego `head`; downgrade del esquema descartable sin datos hasta `0002`, inserción de un usuario ficticio y nuevo upgrade hasta `head`, conservando ese usuario; y downgrade/upgrade únicamente de `0010` al finalizar, conservando usuarios. El segundo recorrido ejercita las ramas con columnas y tablas ausentes. Solo se usaron downgrades históricos para construir el escenario de prueba descartable, nunca como procedimiento de mantenimiento. SQLite vacía también llegó a `head`. No se usó `stamp`.

La prueba ampliada exige columnas exactas por tabla y compara tipos con el comparador de Alembic para PostgreSQL (incluidos sinónimos como FLOAT/DOUBLE PRECISION), nulabilidad, claves primarias y presencia de índices, claves foráneas y restricciones únicas esperadas. Una primera comparación textual de tipos falló por ese sinónimo válido; se corrigió la prueba y la integración posterior pasó.

Limitaciones: no se comparan exhaustivamente defaults, acciones de FK, restricciones check ni objetos adicionales ajenos a los modelos; no se ensayaron todas las versiones históricas y combinaciones de esquemas reales. El guard de `0010` no repara una tabla preexistente incompleta. Revisar esas condiciones en una copia autorizada antes de cualquier promoción.

## 5. Evidencia PostgreSQL

Se utilizó PostgreSQL **16.2** mediante el paquete `pgserver` dentro de un entorno virtual y una carpeta temporal aislados, con socket local y base descartable `mysecop_test_phase11`. El 15 de noviembre se confirmó que no había `docker`, `postgres` o `initdb` en PATH; sí existía `/tmp/mysecop-audit-venv` con `pgserver` y el controlador. Se reutilizó ese entorno, sin instalar paquetes. El primer arranque fue bloqueado por el sandbox al abrir el archivo de coordinación de pgserver; la ejecución autorizada fuera del sandbox permitió usar la instancia aislada. No se instaló servicio global ni se conectó a ninguna base empresarial. Las pruebas opt-in `backend/tests/test_postgresql_sync.py` exigen una base vacía cuyo nombre empiece por `mysecop_test_`.

Se probaron dos sesiones concurrentes, bloqueo, expiración, renovación y pérdida del token, fallo entre páginas y reanudación, rollback del lote y cursor, terminación real de una conexión PostgreSQL antes de commit, repetición idempotente y preservación de una relación guardada. La pérdida de conexión se simuló con `pg_terminate_backend` solo en el backend de prueba. No se probó Redis/Celery distribuido ni caída completa del servidor.

## 6. Pruebas ejecutadas y resultados

- Suite backend general: **75 aprobadas, 4 omitidas**; las cuatro omitidas son las pruebas PostgreSQL opt-in cuando no se establece la URL temporal. Se conservaron **625 advertencias**. Resultado de esta ejecución: 8,31 segundos. `/tmp/mysecop-blockers-suite.log` corresponde a la ejecución anterior de 73 pruebas, no a esta revalidación.
- Integración PostgreSQL aislada: **4 aprobadas**, 5 advertencias, incluyendo el aviso del ciclo de claves `companies`/`users`. Resultado final de esta ejecución: 1,96 segundos. `/tmp/mysecop-pg-results.log` corresponde a la revisión anterior; la salida nueva se conserva en el historial de ejecución.
- Migración SQLite desde base vacía: upgrade hasta `head` aprobado. PostgreSQL: upgrade completo y downgrade/upgrade de `0010` aprobados dentro de la prueba aislada.
- Las pruebas de Socrata se basan en metadatos y consultas de lectura acotadas; la sincronización automática usa fuentes simuladas, no una carga real.

Reproducción en una base PostgreSQL descartable vacía ya levantada (no usar una base existente):

```bash
cd backend
MYSECOP_TEST_POSTGRES_URL='postgresql+psycopg2://USUARIO:CLAVE@HOST:PUERTO/mysecop_test_nombre_unico' \
  python -m pytest tests/test_postgresql_sync.py -q
```

El fixture ejecuta migraciones y modifica la base indicada; está protegido por el prefijo y exige que esté vacía. También requiere controlador PostgreSQL y Alembic en el entorno. La instalación temporal usada aquí no se añadió a las dependencias del proyecto. El ejecutor reproducible `backend/scripts/test_isolated_postgresql.py` crea una instancia nueva, informa su versión y detiene el servidor al finalizar; conserva el directorio temporal para inspección, sin eliminarlo. Con un venv que ya contenga `pgserver`, `psycopg2` y las dependencias backend, ejecutar desde backend:

```bash
/ruta/al/venv/bin/python scripts/test_isolated_postgresql.py
```

No requiere URL empresarial ni instala dependencias automáticamente. La suite general se ejecutó con `backend/.venv/bin/python -m pytest -q`; PostgreSQL por separado con `/tmp/mysecop-audit-venv/bin/python scripts/test_isolated_postgresql.py`. Las advertencias se muestran sin filtros: deprecaciones FastAPI/httpx/crypt/fechas, clave JWT corta de pruebas y ciclo de FK `companies`/`users`.

## 7. Resultados y limitaciones

Los tres bloqueos originales quedan resueltos dentro del alcance local verificado: mapeo SECOP I contrastado, rutas de migración ensayadas y PostgreSQL real ejecutado, pero no se certifica la Fase 1.1 completa: la semántica del cursor de última publicación en SECOP II, el volumen de reconciliación, los cambios mientras se recorren páginas y la disponibilidad del proveedor siguen sin validarse a escala. No se verificó que `uid` sea único y estable para todos los registros y versiones del dataset, solo su definición oficial y muestras acotadas. El sistema falla de forma conservadora ante ausencia de clave, pero puede requerir intervención si encuentra filas inválidas.

La prueba PostgreSQL cubre una versión y un esquema creado en esta ejecución; no sustituye probar upgrade sobre una copia autorizada de DEV ni una caída real de Celery/Redis. No se ejecutaron sincronizaciones masivas ni se comprobó cobertura de todos los datasets.

## 8. Archivos modificados

`backend/app/services/secop_client.py`, `backend/app/services/opportunity_status.py`, `backend/alembic/versions/0003_password_reset.py` a `0008_last_opportunity_search.py`, `backend/tests/test_secop.py` y `backend/tests/test_postgresql_sync.py`. En esta revalidación se ampliaron `backend/tests/test_postgresql_sync.py` y `backend/tests/test_secop.py`, y se añadió `backend/scripts/test_isolated_postgresql.py`. Se conservan los demás cambios locales previos, incluidos los del frontend y routers que ya existían al iniciar, sin reescribir el matcher, el frontend ni las funciones comerciales. No se hicieron commits, despliegues ni sincronizaciones masivas.

## 9. Riesgos pendientes

1. El cursor de SECOP II procesos puede no avanzar por todos los cambios; la reconciliación periódica sigue siendo necesaria y puede ser lenta.
2. La estabilidad de UID y `:id`, la colación, los nulos y el comportamiento de Socrata al mutar el dataset no están probados exhaustivamente.
3. Esquemas ya existentes con columnas de mismo nombre y tipos incorrectos requieren inspección; las guardas no corrigen discrepancias.
4. Faltan pruebas con Redis y workers Celery reales, reconexión de red, límites del proveedor y tiempos de reconciliación.
5. Persisten advertencias de deprecación y el ciclo de claves `companies`/`users`; no se ocultaron.

## 10. Dictamen de preparación para DEV

**Apto para validación controlada en DEV aislado, no para certificar la fase ni para producción.** Antes de conectar el ambiente a fuentes reales debe revisarse una copia autorizada del esquema, contar con respaldo, validar la configuración efectiva y acordar pruebas de lectura y sincronización acotadas. El término «apto» se limita a iniciar esa validación; no afirma cobertura completa ni corrección funcional con datos reales.

## 11. Procedimiento de rollback

Antes de cualquier despliegue futuro, respaldar la base y detener API y workers que usen el cursor. Revertir código y, solo con autorización y después de evaluar el estado, ejecutar downgrade de `0010` para eliminar la tabla de cursor. El downgrade pierde el progreso, no revierte oportunidades ya insertadas o actualizadas. Recuperar valores anteriores requiere un respaldo y procedimiento de restauración probados. No ejecutar downgrades históricos de columnas sin analizar el riesgo de pérdida de datos.

## 12. Inventario oficial de columnas

La siguiente tabla recoge las 72 columnas, tipos y descripciones de los metadatos oficiales, consultados nuevamente el 15 de noviembre de 2026. La presencia de una columna no implica que esté completa o se use en MySECOP.

| Campo | Tipo | Significado según metadatos |
|---|---|---|
| `uid` | text | Identificador único de la relación entre proceso y adjudicación, campo constituido por el número de constancia y el de adjudicación, separados por un guión |
| `anno_cargue_secop` | number | Valor Numérico para identificar el año en que el proceso fue cargado en la plataformaorma |
| `anno_firma_contrato` | text | Valor de texto que identifica la fecha de firma del contrato, en caso de no existir aún firma del contrato, el registro se marca como no firmado |
| `nivel_entidad` | text | Determina el primer grado de caracterización de la entidad de acuerdo a su orden: Nacional o Territorial |
| `orden_entidad` | text | Segundo nivel de caracterización, que detalla el orden definido para la entidad |
| `nombre_entidad` | text | Nombre de la Entidad del Estado que publicó el proceso de compra, Entidad compradora el proceso |
| `nit_de_la_entidad` | text | Identificador tributario de la entidad del Estado que publicó el proceso de compra, Entidad compradora |
| `c_digo_de_la_entidad` | number | Código de la Entidad, utilizado como identificador único en la plataforma SECOP I |
| `id_modalidad` | number | Identificador de la Modalidad de selección que se determinó para el proceso de compra actual, Ej: Licitación Pública, Contratación Directa. compra |
| `modalidad_de_contratacion` | text | Modalidad de selección que se determinó para el proceso de compra actual, Ej: Licitación Pública, Contratación Directa. |
| `estado_del_proceso` | text | El Estado del proceso a la fecha de publicación |
| `causal_de_otras_formas_de` | text | En caso de una contratación directa, el campo determina la causa por la cual se llega a la decisión de contratar directamente. |
| `id_regimen_de_contratacion` | number | Determina si se utilizan las Leyes 80 de 1993 y 1150 de 2007 o en su defecto un régimen especial ID del régimen bajo el cual la entidad desarrolla el proceso de compra pública |
| `nombre_regimen_de_contratacion` | text | Determina si se utilizan las Leyes 80 de 1993 y 1150 de 2007 o en su defecto un régimen especial |
| `id_objeto_a_contratar` | number | ID del Objeto de la contratación, basado en el catálogo de bienes y servicios UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `objeto_a_contratar` | text | Objeto de la contratación, basado en el catálogo de bienes y servicios UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `detalle_del_objeto_a_contratar` | text | Adicional al código que define el objeto del contrato, se registra un detalle de la definición del bien o servicio que se adquirirá dentro del proceso |
| `tipo_de_contrato` | text | Tipo de Contrato que se realizará, ejemplos: Fiducia, Obra, entre otros. |
| `municipio_de_obtencion` | text | Municipio en el que se desarrolla el proceso de compra pública |
| `municipio_de_entrega` | text | Municipio en el que se hace la entrega del bien o servicio |
| `municipios_ejecucion` | text | Municipios en los que se desarrollará el objeto del proceso de compra pública |
| `fecha_de_cargue_en_el_secop` | calendar_date | Fecha en la que se hizo el registro del proceso de compra en la plataforma, entregada en formato DDMMYYYY |
| `numero_de_constancia` | text | Identificador del proceso de compra, generado por SECOP I |
| `numero_de_proceso` | text | Identificador del proceso, de acuerdo con la nomenclatura de la entidad |
| `numero_de_contrato` | text | Identificador del contrato, de acuerdo con la nomenclatura de la entidad |
| `cuantia_proceso` | number | Valor por el cual se lanza el proceso de compra |
| `id_grupo` | text | ID de la Categorización inicial del bien o servicio definido en el proceso de compra, de acuerdo con sus características principales, constituye el primer nivel de clasificación UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `nombre_grupo` | text | Categorización inicial del bien o servicio definido en el proceso de compra, de acuerdo con sus características principales, constituye el primer nivel de clasificación UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `id_familia` | text | ID del segundo nivel de la Categorización del bien o servicio definido en el proceso de compra, de acuerdo con sus características principales, constituye el primer nivel de clasificación UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `nombre_familia` | text | Segundo nivel de la Categorización del bien o servicio definido en el proceso de compra, de acuerdo a sus características principales, constituye el primer nivel de clasificación UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `id_clase` | text | ID del tercer nivel de la Categorización del bien o servicio definido en el proceso de compra, de acuerdo a sus características principales, constituye el primer nivel de clasificación UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `nombre_clase` | text | Tercer nivel de la Categorización del bien o servicio definido en el proceso de compra, de acuerdo a sus características principales, constituye el primer nivel de clasificación UNSPSC, consultable desde https://www.colombiacompra.gov.co/clasificador-de-bienes-y-servicios |
| `id_adjudicacion` | text | Identificador de la adjudicación hechas en el proceso de compra |
| `tipo_identifi_del_contratista` | text | Tipo de Identificación del contratista seleccionado en la adjudicación |
| `identificacion_del_contratista` | text | Identificación del contratista seleccionado en la adjudicación |
| `nom_razon_social_contratista` | text | Nombre o Razón Social del contratista seleccionado en la adjudicación |
| `dpto_y_muni_contratista` | text | Departamento y Municipio en el cual opera el contratista seleccionado en la adjudicación |
| `tipo_doc_representante_legal` | text | En caso de que el adjudicado sea una persona jurídica, el tipo de identificación del representante legal de la empresa seleccionada en la adjudicación |
| `identific_representante_legal` | text | En caso de que el adjudicado sea una persona jurídica, registra la identificación del representante legal de la empresa seleccionada en la adjudicación |
| `nombre_del_represen_legal` | text | En caso de que el adjudicado sea una persona jurídica, registra el nombre del representante legal de la empresa seleccionada en la adjudicación |
| `fecha_de_firma_del_contrato` | calendar_date | Fecha en que se hace la firma del contrato correspondiente a la adjudicación del registro, entregada en formato DDMMYYYY |
| `fecha_ini_ejec_contrato` | calendar_date | Fecha en que inicia la ejecución del contrato, entregada en formato DDMMYYYY |
| `plazo_de_ejec_del_contrato` | number | Valor sobre el cual se determina la duración del contrato |
| `rango_de_ejec_del_contrato` | text | Unidad en la que se define el plazo, pueden ser días, meses o años |
| `tiempo_adiciones_en_dias` | number | Tiempo adicionado al contrato, en días |
| `tiempo_adiciones_en_meses` | number | Tiempo adicionado al contrato, cuando es más de un mes |
| `fecha_fin_ejec_contrato` | calendar_date | Fecha en que finaliza la ejecución del contrato, entregada en formato DDMMYYYY |
| `compromiso_presupuestal` | text | En caso de tener registro presupuestal, el campo muestra el código correspondiente |
| `cuantia_contrato` | number | Valor por el cual se firma el contrato |
| `valor_total_de_adiciones` | number | Valor de la suma de las adiciones hechas al contrato |
| `valor_contrato_con_adiciones` | number | Valor total del contrato, incluyendo las adiciones |
| `objeto_del_contrato_a_la` | text | Objeto del contrato al momento de la firma |
| `proponentes_seleccionados` | text | Listado de los proponentes seleccionados en el proceso de compra |
| `calificacion_definitiva` | text | Calificación definitiva de los proponentes dentro del proceso de compra |
| `id_sub_unidad_ejecutora` | text | Identificador y nombre de la Sub Unidad de ejecucion de presupuesto asignada al proceso de compra |
| `nombre_sub_unidad_ejecutora` | text | Identificador y nombre de la Sub Unidad de ejecucion de presupuesto asignada al proceso de compra |
| `ruta_proceso_en_secop_i` | url | Ruta del proceso de compra en SECOP, para hacer consulta de la información detallada |
| `moneda` | text | Moneda en la cual estan registradas las cuantías del proceso de compra |
| `es_postconflicto` | number | Marcador que indica si el proceso de compra pública está enmarcado en las acciones de postconflicto del acuerdo de paz del año 2017 |
| `marcacion_adiciones` | number | Marcación de si el proceso tiene adiciones registradas |
| `posicion_rubro` | text | Posición (Identificador) del Rubro presupuestal |
| `nombre_rubro` | text | Nombre del Rubro Presupuestal al que corresponde el proceso |
| `valor_rubro` | number | Valor del Rubro presupuestal asignado al proceso |
| `sexo_replegal` | text | Sexo del Representante legal de la entidad compradora |
| `pilar_acuerdo_paz` | text | Pilar, del acuerdo de paz del año 2016, sobre el cual se desarrolla el proceso de compra |
| `punto_acuerdo_paz` | text | Punto del acuerdo de paz del año 2016, al que se relaciona el objeto de contratación del proceso de compra |
| `municipio_entidad` | text | Municipio en el que se encuentra registrada la entidad estatal compradora |
| `departamento_entidad` | text | Departamento en el que se encuentra registrada la entidad estatal compradora |
| `ultima_actualizacion` | calendar_date | Para suplir requerimientos de timestamp, se registra la última fecha de modificación del proceso de compra, entregados en formato DDMMYYYY |
| `fecha_liquidacion` | calendar_date | Fecha en que fue liquidado el contrato |
| `cumpledecreto248` | text | Indica si el requerimiento del bien o servicio tiene caracteristicas que lo catalogan como candidato a recibir el tratamiento estipulado en el decreto 248 del año 2021, que busca impulsar el desarrollo de los pequeños agricultores |
| `incluyebienesdecreto248` | text | Indica si el proceso incluye articulos directamente relacionados con el decreto 248 del año 2021 |
