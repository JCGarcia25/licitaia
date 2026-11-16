# MySECOP Compatibility Engine V2 — Fase 2

## Auditoría y plan previos — 15 de noviembre de 2026

Rama develop, HEAD cac56d0, head Alembic 0012_failed_match_inputs. Se conservan los cambios locales de fases previas. Perfil por usuario con company_id, texto libre de actividad/experiencia/capacidades, preferencias y UNSPSC; no contiene indicadores financieros acreditados ni contratos estructurados. Document y Analysis son privados por user_id; los requisitos heurísticos tienen citas/tipo/confianza, no certifican cumplimiento ni completitud. Los servicios heredados de elegibilidad/viabilidad usan heurísticas distintas: no se reutilizarán sus puntajes como evidencia verificada. El matcher actual, sus pesos, embeddings y consumidores públicos se conservarán.

Plan: servicio puro V2 con siete criterios, agregación con desconocidos e intervalos; catálogo UNSPSC con procedencia; contratos progresivos de evidencia; elegibilidad separada; shadow runs/resultados privados con límite, arrendamiento y tarea Celery independiente; diagnóstico interno bajo flag desactivado; evaluación pareada/etiquetado ciego; pruebas matemáticas, integración y regresiones.

Criterios previos de comparación: Precision@10 no inferior frente al legado, explicaciones trazables, reducción de índices altos con evidencia insuficiente, sin deterioro significativo por sector y coste shadow acotado. No son resultados ni parámetros óptimos. Piloto >=100 pares, muestra representativa y >=20 consultas/empresas independientes como umbral metodológico inicial para bootstrap; no garantiza potencia. Sin etiquetas humanas suficientes, toda superioridad y activación principal quedan pendientes.

Decisión matemática previa: se conserva el denominador de pesos aplicables al calcular un límite inferior sustentado y un límite superior de sensibilidad; UNKNOWN no recibe subscore. La afinidad observada sobre criterios conocidos se identifica como condicional, nunca como índice completo. La cobertura mide masa de criterios/componentes observados, no veracidad jurídica. Las declaraciones permanecen explícitas; VERIFIED exige procedencia revisada. Umbrales iniciales: cobertura mínima 25% para publicar un índice provisional y afinidad contractual suficiente (léxica >=0,20, semántica real >=0,45 o coincidencia UNSPSC de clase/producto). Son hipótesis de diseño versionadas, no calibradas.

## 1. Resumen ejecutivo

Se implementó un motor experimental separado, determinista y versionado, con siete criterios, índice conservador, cobertura de información, intervalo de sensibilidad, elegibilidad independiente y trazabilidad. Incluye snapshots privados de evidencia, extracción literal acotada, tareas shadow con arrendamiento, API interna, diagnóstico web y exportación pareada sin etiquetas.

**Dictamen: apto para evaluación técnica en DEV aislado; no autorizado como motor principal.** Flag desactivado por defecto; producción queda excluida explícitamente incluso con el flag encendido. No hubo despliegue, commits, sincronización SECOP ni cambios al matcher, sus pesos, licencias o pagos. Los avances locales anteriores se conservaron. No se afirma superioridad ni certificación operativa o jurídica.

## 2. Arquitectura implementada

- `backend/app/services/compatibility_v2.py`: características, evidencia, criterios, agregación, elegibilidad, explicación y versiones; sin SQL, red o LLM.
- `compatibility_unspsc.py` y `app/data/unspsc_v14_codes.json`: pertenencia al catálogo y jerarquía numérica.
- `compatibility_documents.py`: observaciones documentales literales con hash, cita y referencia.
- `compatibility_shadow.py`: selección limitada, snapshot inmutable, comparación con score heredado vigente, cursor, fencing por token/lease, persistencia y exportación privada.
- `compatibility_evaluation.py`: comparación pareada sobre el evaluador existente y bootstrap por empresa.
- `app/compatibility_schemas.py`, `app/routers/compatibility.py`: contratos aditivos y autorización.
- `app/workers/tasks.py`: tarea `process_compatibility_shadow`, cola `compatibility-shadow`, independiente del recálculo comercial.

Se reutilizan Opportunity, CompanyProfile, Document, Analysis, UserOpportunity, hashes de fases anteriores y el evaluador de rankings. V2 nunca escribe UserOpportunity, MatchScoreHistory, embeddings heredados, alertas o preferencias comerciales.

## 3. Modelo matemático

Para criterio i: peso wᵢ, fracción informada rᵢ en [0,1] y subíndice observado sᵢ en [0,1]. UNKNOWN tiene rᵢ=0 y sᵢ=null, no una puntuación cero. Un componente parcial puede tener 0<rᵢ<1. Sólo se excluyen criterios NOT_APPLICABLE con revisión y procedencia vigentes.

T = Σ pesos aplicables; K = Σ(wᵢrᵢ); A = Σ(wᵢrᵢsᵢ).

- Límite inferior sustentado L = 100 A/T.
- Límite superior de sensibilidad U = 100(A+T−K)/T.
- Cobertura = 100 K/T.
- Afinidad observada condicional = 100 A/K, sólo si K>0; nunca sustituye silenciosamente al índice completo.

Con toda la información disponible, rᵢ=1 y L=U=C, la media ponderada solicitada. Con información parcial, `compatibility_score=L` sólo cuando supera las condiciones de suficiencia; `score_status=PROVISIONAL` identifica expresamente su naturaleza conservadora. El intervalo no es un IC estadístico. Si no hay masa aplicable, límites e índice quedan null.

`contribution` conserva wᵢrᵢsᵢ en unidades de peso. `normalized_contribution=100wᵢrᵢsᵢ/T` expresa puntos del índice; su suma es L. La API expone `normalization_weight=T`; la vista muestra contribuciones normalizadas.

## 4. Definición de pesos

| Criterio | Peso inicial |
|---|---:|
| Afinidad contractual | 25 |
| Experiencia | 20 |
| Financiera y organizacional | 15 |
| Técnica y operativa | 15 |
| Geografía | 10 |
| Cuantía comercial | 10 |
| Preferencias de modalidad | 5 |

Hipótesis sin calibración humana. `ModelConfig` valida claves exactas, pesos finitos no negativos y masa positiva. Settings admite `COMPATIBILITY_V2_WEIGHTS` como JSON, pesos internos, jerarquía y umbrales; su cambio altera la versión. Los pesos internos de afinidad son léxico 0,5, semántico 0,3 y UNSPSC 0,2. Su masa desconocida permanece en el intervalo.

## 5. Tratamiento de datos faltantes

Estados: VERIFIED_MATCH, VERIFIED_MISMATCH, PARTIAL_MATCH, UNKNOWN y NOT_APPLICABLE. Las preferencias declaradas son comparaciones parciales, no hechos jurídicos verificados. Un desacuerdo declarado no se convierte en incumplimiento verificado. Rango presupuestal invertido o inválido produce UNKNOWN; valores contradictorios de un mismo hecho/unidad producen UNKNOWN, sin seleccionar la versión favorable.

Umbrales iniciales: cobertura mínima 25%; puerta contractual léxica >=0,20, semántica real >=0,45 o UNSPSC clase/producto. Sin puerta contractual, índice null aunque haya coincidencias geográficas y presupuestales. Sin cobertura mínima, índice null y estado INSUFFICIENT_INFORMATION. Son protecciones experimentales pendientes de calibración, no parámetros óptimos. Incluso con índice null se conservan límites y explicación de lo observado.

La cobertura mide disponibilidad de componentes comparables, incluyendo declaraciones, y **no** porcentaje de cumplimiento jurídico o evidencia acreditada.

## 6. Evaluación de elegibilidad

Evaluación separada con ELIGIBLE_VERIFIED, NOT_ELIGIBLE_VERIFIED, PENDING_VERIFICATION y NOT_EVALUABLE. Un requisito excluyente con incumplimiento verificado determina NOT_ELIGIBLE_VERIFIED sin reducir artificialmente la afinidad ni recomendar participación.

Una comparación verificada exige fuentes, revisión identificada, hash documental, fecha de revisión y vigencia, además de operador y valores/unidades comparables. No se convierten strings numéricos en indicadores certificados. Para ELIGIBLE_VERIFIED se necesita además un checklist completo revisado, IDs únicos y todos los requisitos demostrados. Ausencia de requisitos identificados devuelve NOT_EVALUABLE; extracción incompleta o evidencia no revisada devuelve PENDING_VERIFICATION.

Los requisitos de Analysis se leen únicamente para el usuario y oportunidad propios, con la última revisión identificada; se mapean como DOCUMENTED pendiente. Los tipos jurídicos/documentales no se contabilizan como capacidad técnica. El estado heredado “Cumple” o “revisado” nunca basta como prueba. La API nueva no permite enviar VERIFIED, revisores, checklist completo ni NOT_APPLICABLE. La rama de evidencia verificada está probada con fixtures confiables; un proceso operativo de revisión documental autenticada queda como ampliación futura, no existe una autocertificación accesible al usuario.

## 7. Integración UNSPSC

Fuente oficial consultada y descargada el 15-11-2026: [clasificador CCE](https://operaciones.colombiacompra.gov.co/clasificador-de-bienes-y-servicios) y [XLS versión 14](https://operaciones.colombiacompra.gov.co/sites/cce_public/files/cce_clasificador/clasificador_de_bienes_y_servicios_v14_1.xls). La página oficial describe segmento, familia, clase y producto; no se infiere una equivalencia jurídica de esos niveles.

Se almacenan 53.316 identificadores numéricos únicos de productos y ancestros, sin redistribuir descripciones traducidas. SHA256 del XLS: `17cb46de130bd7d1a7200c1b9be80e5072dd5470794a9cbc858081880436615a`. Reconstrucción: `scripts/build_unspsc_catalog.py archivo.xls app/data/unspsc_v14_codes.json`, con xlrd sólo en el entorno temporal de auditoría.

Puntajes configurables: producto 1, clase 0,7, familia 0,4, segmento 0,15. Un código agregado terminado en 00 no cuenta como coincidencia exacta de producto. Se exige pertenencia real al catálogo, no sólo un prefijo de ocho dígitos. Códigos ausentes/nuevos fuera de v14 devuelven INSUFFICIENT, no incumplimiento. Sin ancestro compartido se informa NONE; no se inventan relaciones “relacionadas” sin catálogo que las pruebe. La relación jurídica habilitante se evalúa aparte.

El archivo oficial contiene una restricción sobre explotación comercial de su traducción. Se evita copiar esa traducción; la revisión de condiciones de distribución para una activación comercial sigue pendiente. No se afirma disponer del catálogo más reciente.

## 8. Afinidad semántica

Normalización de tildes/mayúsculas, términos informativos, coincidencias de frases y exclusiones conservadoras por cláusula en ambas entradas. El subíndice léxico es la fracción de términos contractuales informativos presentes y no excluidos. Las frases son evidencia explicativa del solapamiento, sin bonus numérico oculto. No es un analizador lingüístico exhaustivo de negación.

El núcleo admite pares de vectores con proveedor efectivo OpenAI, modelo text-embedding-3-small, 1.536 dimensiones, versión común y hashes exactos de ambos textos. Rechaza fake, origen desactualizado, dimensiones incorrectas, NaN, norma inválida y vectores nulos. Calcula coseno con normalización estable. Un vector fake no aporta masa semántica.

**Alcance operativo actual:** shadow no genera embeddings ni llama al proveedor; funciona léxicamente y con UNSPSC. No se atribuyen automáticamente los vectores heredados al texto V2 sin procedencia completa. El adaptador puro para pares reales está probado con vectores de fixture, sin llamadas reales OpenAI. Integrar un caché semántico V2 con procedencia completa y validar su calidad con un proveedor real queda pendiente. La degradación se muestra expresamente.

## 9. Experiencia empresarial

Texto libre conserva carácter DECLARED; hechos opcionales pueden ser STRUCTURED; la extracción devuelve DOCUMENTED con citas; sólo una revisión confiable y vigente puede producir VERIFIED. `evidence_summary` distingue estas disponibilidades. Ausencia o imposibilidad de comparar requisitos mantiene UNKNOWN; un contrato descrito por palabras parecidas no acredita experiencia.

La extracción reconoce etiquetas explícitas de tipo de contrato, objeto, valor literal, fecha/plazo, contratante, actividades y certificaciones. No transforma montos o fechas ambiguas en hechos acreditados ni atribuye automáticamente documentos a la empresa. Se limita a archivos propios, almacenamiento privado, 25 MB, 50 páginas PDF y 20.000 caracteres analizados; revisa expansión de archivos Office hasta 40 MB. No hay OCR o interpretación contractual automática. Los snapshots anteriores se conservan.

## 10. Capacidad técnica y financiera

La ampliación aditiva es `CompatibilityEvidenceProfile`: hechos privados por usuario, categoría, clave, valor, unidad y nivel; observaciones documentales referenciadas. Permite avanzar sin exigir un formulario adicional a todos los usuarios. Los hechos cuantitativos se comparan con requisitos identificados mediante eq/gte/lte sólo tras revisar ambas fuentes; cifras no comparables quedan desconocidas.

Presupuesto mínimo/máximo se usa exclusivamente como preferencia comercial, nunca liquidez, endeudamiento, capacidad residual o patrimonio. Las declaraciones de departamentos no certifican cobertura operativa. El catálogo de indicadores sectoriales y un formulario de contratos acreditados/revisión formal no se implementan como si ya hubiera datos confiables.

## 11. Explicabilidad

Cada criterio incluye valor empresarial, valor contractual, fuente, estado, fracción de información, subíndice nullable, peso, contribución bruta/normalizada, razón, fecha y versión. Las razones identifican los componentes efectivamente disponibles. Se conserva el detalle léxico y de jerarquía; requisitos pendientes e incompatibilidades se devuelven aparte. Las explicaciones se generan desde el cálculo, sin LLM.

Se versionan configuración/código/catálogo, perfil, oportunidad, evidencia, requisitos/checklist, metadatos semánticos y fecha lógica. El snapshot histórico permanece estable aunque el perfil se edite posteriormente. El timestamp de persistencia se conserva en Result.created_at; evaluated_at expresa la fecha lógica del snapshot. Un snapshot no debe presentarse como recomendación actual sin una nueva ejecución.

## 12. Implementación shadow mode

`COMPATIBILITY_V2_SHADOW_ENABLED=false` por defecto; ambientes permitidos: development, testing, isolated-integration, y rol admin con propiedad por user_id. No existe paso a perfil organizacional compartido.

Muestra por defecto 20, límite configurable hasta 100; lotes por defecto 5, máximo 20; lease 120 segundos, configurable 10–600. Selección determinista por ID entre candidatos potencialmente vigentes. Es una muestra de diagnóstico, no una muestra estadística representativa. Sólo un run activo por usuario, serializado mediante bloqueo corto de su perfil en PostgreSQL.

Se congela perfil, evidencia, requisitos y oportunidades. Se compara con el score heredado sólo si todas sus versiones siguen vigentes al congelar. Sin ese score, legacy_score y diferencia son null: V2 no recalcula el legado ni realiza llamadas externas para llenar huecos. Se persiste en tablas separadas y nunca se sobrescribe historial anterior.

Cada lote adquiere lease con CAS, libera transacción antes del cálculo y confirma bajo cursor/token/lease vigentes. Un worker tardío no puede escribir tras perder el arrendamiento. Repeticiones son idempotentes por cursor y UNIQUE(run_id, opportunity_id). Cambio de modelo marca SUPERSEDED. Interrupciones se recuperan desde el cursor durable mediante resume después del lease. No hay heartbeat de shadow: los lotes son pequeños y puramente locales; si exceden lease, se rechaza su commit. Una recuperación que necesite intervalos mayores debe reducir lote/ajustar lease y repetir.

No se agregó beat ni recálculo doble automático. Un worker explícito `-Q compatibility-shadow --concurrency=1` acota el coste y separa la cola. Desactivar el flag impide nuevos cálculos y escrituras de resultados; un lote que observa la desactivación al confirmar queda DISABLED. Si estaba interrumpido antes de observarla, queda a la espera de expiración/resume. El recálculo comercial sigue independiente.

## 13. API

Prefijo `/api/internal/compatibility-v2`, JWT + admin + flag/ambiente, siempre limitado al propio user_id:

| Método/ruta | Contrato |
|---|---|
| GET /runs | Últimas 20 ejecuciones propias |
| POST /runs | Encola muestra limitada, 202 |
| GET /runs/{id} | Diagnóstico y comparaciones persistidas |
| POST /runs/{id}/resume | Reencola ejecución pendiente/interrumpida |
| GET /runs/{id}/evaluation | Exportación pareada privada, sólo COMPLETED, sin etiquetas |
| POST /evidence | Nuevo snapshot de hechos declarados/estructurados; conserva observaciones documentales |
| POST /documents/{id}/extract | Extracción literal de documento propio |

Contrato `CompatibilityOut`: compatibility_score nullable, score_status, eligibility_status, evidence_coverage, sensitivity_interval, criteria, explanations, warnings, pending_requirements, model_version, input_versions, evaluated_at. Subscores y contribuciones UNKNOWN son null; legacy_score/difference también pueden ser null. El esquema rechaza campos adicionales de autoverificación y valores no finitos. IDs ajenos devuelven 404; sin JWT, 401; sin flag/ambiente, 404; sin rol, 403. Los endpoints actuales conservan sus contratos.

La exportación usa hashes comunes del snapshot para comparar ambos motores, conserva versiones originales del legado aparte y anonimiza el cluster mediante el secreto de instalación. No contiene documentos completos ni etiquetas humanas; sigue siendo información privada. No se envió a terceros.

## 14. Frontend interno

Ruta directa `/app/diagnostico-compatibilidad`, sin añadirla a navegación comercial. Permite crear una muestra de diez, consultar estado y actualizar resultado. Compara legado/V2, cobertura, sensibilidad, elegibilidad, criterios y advertencias. Sin habilitación muestra indisponibilidad y no activa cálculos. Revisión E2E en 1440×1000 y 390×844; la tabla desplaza dentro de su contenedor, sin desbordamiento de página. No se cambió la UI pública para mostrar V2.

## 15. Migraciones

Nueva revisión `0013_compatibility_shadow`, descendiente de `0012_failed_match_inputs`:

- compatibility_evidence_profiles: snapshots privados append-only.
- compatibility_shadow_runs: perfil/entradas congeladas y cursor/lease.
- compatibility_shadow_results: comparación e índice explicable por run/oportunidad.

FK a usuarios/oportunidades existentes; no se duplica la tabla Opportunity. No se alteran columnas o scores comerciales. Definiciones literales en 0013; si la creación histórica mediante metadata ya creó una tabla, no se vuelve a crear. No se reescribieron migraciones históricas en esta fase ni se utilizó stamp. Se verificó esquema/modelos y upgrade desde vacío, downgrade vacío y upgrade desde esquema anterior con score conservado.

Downgrade 0013 sólo permite retirar tablas vacías. Si existe evidencia/run/resultado, aborta antes de eliminar información. Rollback operativo recomendado: deshabilitar V2 y conservar tablas; no borrar historial para forzar un downgrade.

## 16. Pruebas ejecutadas

Ver `backend/benchmarks/phase2/validation.json` para resultados finales y hashes de evidencia. Resultado final: **127 aprobadas, 20 omitidas y 1.573 advertencias** en backend; **12 aprobadas** en PostgreSQL real (4+6+2; 5+364+12 advertencias); **7 aprobadas** en Redis/Celery real (6+1; 32+8 advertencias). TypeScript exit 0; dos modos E2E aprobados. Las 20 omisiones son 12 PG y 7 Redis ejecutadas separadamente, más una prueba histórica opt-in Redis/SQLite no ejecutada. Logs íntegros y capturas en `backend/benchmarks/phase2/`, además de `/tmp/mysecop-phase2-*.log`; no se suprimieron advertencias.

- Suite backend completa: pruebas de propiedad con 250 configuraciones reproducibles, límites, monotonía, determinismo, desconocidos, N/A, versiones, jerarquías, contradicciones, negación, fake/NaN/normas, elegibilidad y separación de requisitos.
- Seguridad/API: flag/producción/rol, aislamiento entre usuarios, rechazo de autoverificación, documento ajeno, límites, exportación sin etiquetas y preservación del legado.
- PostgreSQL 16.2 real temporal: migraciones de fases anteriores y V2; workers simultáneos, ausencia de bloqueo durante cómputo, fencing tras vencimiento, recuperación, rollback precommit, conexión terminada realmente, idempotencia y downgrade protegido.
- Redis/Celery reales temporales: regresión de seis escenarios y tarea shadow real, mensajes duplicados, cursor durable, reinicio Redis/worker y flag desactivado. No son mocks de broker o base.
- TypeScript `tsc --noEmit`.
- E2E real Next/FastAPI + PG/Redis/Celery: flujos comerciales existentes, modo V2 apagado y diagnóstico V2 habilitado con sólo fixtures sintéticos; diez comparaciones, scores comerciales conservados, desktop/móvil y sin errores JS.

Los datos empresariales, documentos y vectores usados en pruebas son sintéticos; las propiedades legales/estadísticas no se validan por esa razón. Los fixtures del bootstrap simulan metadatos de etiquetas humanas exclusivamente para probar código, no constituyen juicios humanos recolectados.

Se corrigieron fallos iniciales detectados durante la validación: contaminación del fixture compartido con oportunidades nuevas, referencia al PID de una conexión ya devuelta al pool, selector E2E ambiguo con el anunciador de Next y patrón de certificación singular/tildada. Se mantuvieron las aserciones comerciales, sin ajustar el matcher para obtener un aprobado.

Advertencias heredadas observadas: datetime.utcnow, on_event de FastAPI, integración Starlette/httpx y crypt/passlib, además de SAWarning por el ciclo FK preexistente companies/users; se detallan cantidades en la evidencia. La carga de shell también informa restricción de `ps` desde el script RVM; no afecta resultados. Los errores de reconexión Redis del escenario de pérdida de broker son esperados, visibles y seguidos por recuperación aprobada. Su resolución requiere trabajo separado; no se ocultaron con filtros.

## 17. Comparación inicial con matcher heredado

`backend/benchmarks/phase2/synthetic-20.json` ejecuta ambos algoritmos reales sobre 20 pares sintéticos acotados. El legado recibe vectores fake precalculados; V2 rechaza semántica fake y usa léxico/catálogo. Los valores resultantes son índices distintos con cobertura distinta: no se interpretan como mejora de relevancia.

Medición local de CPU, incluyendo primera carga: legado media ≈0.040 ms; V2 media ≈0.378 ms, primera llamada ≈6.391 ms, p95 ≈0.101 ms. El primer arranque pesa en la media y puede superar el p95 con sólo veinte observaciones. Consultar JSON para cifras exactas/versiones. No incluye SQL, broker, red o coste documental; no extrapolar a producción ni comparar contra el benchmark sintético de scoring constante de Fase 1.3.

El modo shadow registra duración total por par y tiempos de características, afinidad, elegibilidad, criterios y agregación/versionado. No genera LLM ni embeddings y, por tanto, no introdujo costes externos medidos. El coste operativo completo a volumen real queda pendiente.

## 18. Métricas disponibles y pendientes

Disponibles técnicamente: cobertura, tasa de abstención, tiempos, componentes y exportación pareada. `scripts/compare_compatibility.py legacy.jsonl v2.jsonl labels.jsonl queries.jsonl` reutiliza ranking_evaluation.py; valida mismos pares, versiones y ventana antes de calcular.

P@5/P@10 quedan sin valor si los resultados devueltos no tienen juicios; Recall@20/NDCG@10/FPR exigen universo completo según evaluador previo. Unknown no se convierte en irrelevancia. Bootstrap pareado por cluster empresarial, 2.000 remuestras, semilla 20261115: mínimo inicial 100 juicios humanos y 20 clusters utilizables por estimación. Sectores insuficientes no reciben IC. No se garantiza potencia por alcanzar ese mínimo.

**Juicios humanos reales recolectados en esta fase: 0.** P@5, P@10, NDCG, Recall, FPR e IC reales comparativos permanecen pendientes. No se entrenó un modelo supervisado ni se demostró superioridad. Los datos sintéticos del benchmark no se entregan como dataset de evaluación humana.

Protocolo, separación de afinidad/elegibilidad/calidad documental, ciego, resolución por tercer revisor, holdout, estratificación y criterios previos: `backend/evaluation/phase2-labeling.md`. Plantillas nuevas `phase2.queries.template.jsonl` y `phase2.human-labels.template.jsonl` contienen placeholders sin etiquetas inventadas.

## 19. Riesgos

Pesos/umbrales y funciones sin calibrar; coincidencias léxicas limitadas; catálogo v14 sin relaciones transversales ni garantía de actualidad; condiciones de redistribución por revisar; no OCR; indicadores y requisitos rara vez revisados; cobertura declarativa puede ser alta sin cumplimiento; exportación sigue siendo privada; muestra por ID no representa sectores; instantánea histórica no equivale a recomendación vigente; recuperación shadow explícita, sin heartbeat/beat; SQLite no prueba locks PostgreSQL; arranque heredado create_all sigue siendo deuda histórica y no reemplaza Alembic para despliegues.

La vía de semántica real y un flujo operativo de revisión documental quedan pendientes de integración validada. Son límites explícitos; no se simularon pruebas externas ni cumplimiento legal para ocultarlos.

## 20. Criterios de aceptación

| Criterio | Estado técnico |
|---|---|
| Motor separado y cálculo determinista/versionado | Implementado y probado |
| Contribuciones y fuentes explicables | Implementado y probado |
| Ausentes sin imputación e intervalos explícitos | Implementado y probado |
| Elegibilidad independiente y excluyentes no compensables | Implementado; revisión operativa futura |
| Persistencia separada e historial conservado | Probado en PG/Redis/E2E |
| Flag off y funcionamiento comercial preservado | Probado en regresión y E2E |
| Pruebas matemáticas, shadow y seguridad | Ejecutadas |
| Evaluación estadística y etiquetado preparados | Implementado; etiquetas reales pendientes |
| Costes/limitaciones y activación/rollback documentados | Documentado; operación real no certificada |

La implementación inicial permite evaluación DEV. No equivale a validación humana, superioridad comercial, activación general ni certificación jurídica.

## 21. Procedimiento de validación DEV

1. Copia aislada con datos sintéticos o autorizados, respaldos propios y sin URL/credenciales empresariales. Revisar diff completo: la rama conserva cambios locales de fases previas.
2. En venv backend, ejecutar `alembic upgrade head`; comprobar `0013_compatibility_shadow`, tablas/FK/modelos y scores previos. Nunca stamp.
3. Ejecutar pytest; con dependencias QA temporales disponibles, `scripts/test_isolated_postgresql.py` y `scripts/test_isolated_phase13.py`. Instalan cero servicios globales; crean DB mysecop_test_* descartables. Node frontend: `node_modules/.bin/tsc --noEmit`.
4. Con flag apagado verificar 404 del diagnóstico y flujos comerciales. Reiniciar API y worker con flag true únicamente en DEV; usar cuenta admin propia. Arrancar worker explícito: `celery -A app.workers.celery_app.celery_app worker -Q compatibility-shadow --concurrency=1`.
5. Abrir ruta interna y crear diez pares; comprobar NULL/PROVISIONAL, límites, fuentes y elegibilidad pendiente. Comparar UserOpportunity/alertas antes y después: deben conservarse.
6. Interrumpir worker de pruebas; esperar lease y reenviar resume. Confirmar cursor, unicidad y ausencia de sobrescrituras. Desactivar flag y reiniciar API/worker: ninguna tarea V2 debe escribir resultados nuevos.
7. Exportar `/runs/{id}/evaluation` a almacenamiento privado. No usar la muestra por ID como evaluación representativa; preparar piloto estratificado ciego >=100 pares y suficientes empresas, adjudicar desacuerdos, reservar holdout. Sólo entonces ejecutar evaluación pareada.
8. E2E disponibles: `scripts/e2e_phase13.py` y `MYSECOP_E2E_V2=1 scripts/e2e_phase13.py`, con Playwright QA en entorno temporal. Revisar capturas y logs.

## 22. Estrategia de activación y rollback

Activación futura sólo tras revisar etiquetas independientes, potencia, sectores, falsos positivos con evidencia insuficiente, costes reales y revisión documental/procedencia semántica. Los umbrales se ajustan con desarrollo separado del holdout. Esta implementación no contiene un selector que sustituya el ranking comercial por V2.

Rollback operativo: poner COMPATIBILITY_V2_SHADOW_ENABLED=false, reiniciar API y worker shadow y detener exclusivamente la cola compatibility-shadow; dejar intactos workers matches y servicios comerciales. Conservar ejecuciones/evidencias/resultados para auditoría. Verificar 404 interno y endpoints comerciales. Si se desea revertir código, retirar únicamente los archivos/conexiones V2 de esta fase mediante revisión del diff, sin resetear avances previos. Mantener 0013 aplicada mientras haya datos. Sólo una base aislada con las tres tablas vacías admite `alembic downgrade 0012_failed_match_inputs`; la prueba confirma que con historial aborta sin borrarlo.

## 23. Recomendaciones siguientes y archivos de esta fase

Prioridad: recopilar juicios reales; validar negaciones y afinidad por sector; revisar vigencia/licencia de catálogo; integrar cache semántico con procedencia exacta; diseñar revisión documental con permisos/auditoría; indicadores financieros tipados y contratos estructurados con fuentes; medir coste SQL/worker con datos autorizados. No habilitar decisiones automáticas como consecuencia de las pruebas sintéticas.

Diseño multiempresa futuro, no implementado: administrador organizacional, miembros con permisos explícitos, perfil común versionado, preferencias privadas separadas, auditoría de revisiones y separación de documentos/datos comerciales. Requerirá una migración deliberada y autorizada; actualmente incluso miembros de la misma empresa conservan scores/evidencia privados por usuario.

Archivos nuevos principales:

- `backend/app/services/compatibility_v2.py`, `compatibility_unspsc.py`, `compatibility_documents.py`, `compatibility_shadow.py`, `compatibility_evaluation.py`.
- `backend/app/compatibility_schemas.py`, `backend/app/routers/compatibility.py`.
- `backend/app/data/unspsc_v14_codes.json`.
- `backend/alembic/versions/0013_compatibility_shadow.py`.
- `backend/scripts/build_unspsc_catalog.py`, `benchmark_compatibility_v2.py`, `compare_compatibility.py`.
- `backend/tests/test_compatibility_v2.py`, `test_compatibility_shadow.py`, `test_compatibility_evaluation.py`, `test_postgresql_compatibility.py`, `test_redis_compatibility.py`.
- `backend/evaluation/phase2-labeling.md`, `phase2.queries.template.jsonl`, `phase2.human-labels.template.jsonl`.
- `backend/benchmarks/phase2/` y este informe.
- `frontend/app/(private)/app/diagnostico-compatibilidad/page.tsx`.

Archivos existentes ampliados en esta fase: `.env.example`, `backend/app/core/config.py`, `db/models.py`, `main.py`, `workers/tasks.py`, `workers/celery_app.py`, `scripts/test_isolated_postgresql.py`, `scripts/test_isolated_phase13.py`, `scripts/e2e_phase13.py` y `tests/test_redis_operations.py` (parámetros opcionales del arnés; defaults del legado conservados). `matcher.py`, `embeddings.py`, `eligibility.py`, `viability.py`, pagos y licencias no se modificaron en esta fase.
