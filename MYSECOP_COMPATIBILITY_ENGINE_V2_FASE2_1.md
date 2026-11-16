# MySECOP Compatibility Engine V2 — Fase 2.1

Cierre de validación local: 16 de noviembre de 2026.

Auditoría previa: develop, HEAD cac56d0; cambios locales previos conservados; head de archivos Alembic 0013. Configuración local inspeccionada sin abrir conexiones: SQLite ./licitaia.db, Redis localhost:6379/0, environment development, shadow false, proveedor fake sin clave externa. No es un destino DEV autorizado ni se han inspeccionado/alterado bases remotas.

Plan previo: guardia de destinos DB/broker/API e identidad persistida; campañas privadas con universo/versiones/retención y consentimiento; muestreo estratificado reproducible y deduplicación por proceso; asignaciones ciegas independientes y adjudicación de tercer revisor; adaptador semántico aislado con caché privado/reserva de coste; informes A/B/C que reutilizan evaluadores; UI interna; migración aditiva y pruebas locales aisladas. Sin despliegue o migraciones sobre DEV operativo.

Criterios previos, sin observar resultados: margen material P@10 de 0,02, IC95 pareado por empresa y mínimo inicial 100 pares/20 clusters utilizables (no garantía de potencia); no inferioridad sólo si límite inferior >=−0,02; evaluación sectorial y de riesgos/coste separada. Aporte semántico exige mejora medible y coste bajo presupuesto configurado, sin automatizar activación. Los datos sintéticos sólo validan procedimiento; sin etiquetas humanas reales, calidad comercial inconclusa. Pesos V2 permanecen intactos. Holdout reservado antes de etiquetar; informes cerrados inmutables, sin reajustes posteriores.

## 1. Resumen ejecutivo

Se implementó una plataforma interna de experimentación separada del ranking comercial: campañas con universo congelado, muestreo estratificado, dos revisiones ciegas, adjudicación de tercer revisor, informe sellado y ablación A/B/C. La evaluación permanece desactivada por defecto y exige destino DB/broker/API expresamente autorizado, identidad persistida de la base y permisos por usuario.

Estados de entrega, que no deben confundirse:

| Ámbito | Estado |
|---|---|
| Implementación local | Terminada, con límites expresos descritos abajo |
| Validación técnica local aislada | Ejecutada; resultados y logs en sección 12 |
| Despliegue y migración en DEV operativo | Pendientes; no ejecutados |
| Juicios humanos sobre datos reales autorizados | Pendientes; recolectados en esta entrega: **0** |
| Validación estadística/comercial | Inconclusa, no terminada |
| Activación productiva | No autorizada y bloqueada en la plataforma |

No hubo despliegue, commits, operaciones sobre producción, sincronización SECOP, cambios en licencias/pagos o sustitución del matcher. No se modificaron pesos con fixtures.

## 2. Arquitectura implementada

- `app/services/evaluation_guard.py`: preflight sin conexión para destinos no permitidos; comprobación de sesión, origen API e identidad DB antes de operaciones de evaluación.
- `evaluation_platform.py`: campañas, snapshots/versiones, consentimiento, cursor/lease, cálculo por lotes, asignaciones, vistas ciegas y juicios sellados.
- `evaluation_sampling.py`: marco deduplicado por proceso, estratos, probabilidades de inclusión y reserva de empresas para holdout.
- `evaluation_semantic.py`: proveedor externo opt-in, caché privado, reservas de presupuesto, procedencia y ausencia explícita de resultado ante fallos.
- `evaluation_reporting.py`: consenso/adjudicación, métricas pareadas, concordancia y casos de diagnóstico; informes inmutables.
- `app/evaluation_schemas.py`, `app/routers/evaluation.py`: contratos y permisos aditivos.
- Tarea `app.workers.tasks.process_evaluation_campaign`, cola `evaluation`, sin beat automático. Lease de 120 segundos; cinco pares locales por lote, un par por lote semántico.
- Página interna `/app/evaluacion-interna`, sin enlace en navegación pública.

No se duplicaron tablas de oportunidades, usuarios o suscripciones. Las copias de características son snapshots privados de evaluación para conservar entradas históricas, no nuevos perfiles comerciales compartidos. Se conservan hashes de perfil/oportunidad, modelo V2, pipeline completo, rúbrica, universo, selección y fecha.

## 3. Componentes reutilizados

Se reutilizan CompanyProfile, Opportunity, UserOpportunity, CompatibilityShadowRun/Result, AuditLog, el clasificador de vigencia, hashes/versiones y la configuración de V2. El score A real se recupera de un snapshot heredado vigente al capturarse, verificando la oportunidad y la identidad del perfil; si éste cambió, se exige un snapshot nuevo. Se conservan sus versiones originales y los learning_weights acreditados por esa versión, sin ajustarlos.

Para ficción, A ejecuta `matcher.score_opportunity` con vectores fake explícitos de 64 dimensiones y marca ese baseline como control técnico. B usa `compatibility_v2.evaluate` sin semántica. C reutiliza exactamente el mismo núcleo/configuración y añade únicamente un par semántico válido. Las entradas comunes se mantienen iguales entre A/B/C; la vista humana suprime identificadores y puntuaciones.

`compatibility_evaluation.compare` y `ranking_evaluation.evaluate` siguen siendo las implementaciones de métricas. La única ampliación del comparador previo es un argumento opt-in para fixtures `synthetic_test`, desactivado por defecto. Los cálculos matemáticos del matcher y V2 no se reescribieron. MatchScoreHistory permanece intacto; las campañas no escriben UserOpportunity, alertas o embeddings comerciales.

## 4. Muestreo y prevención de sesgo

Configuración por defecto: universo máximo 500 pares, muestra máxima 100; límites configurables hasta 1.000 y 200 respectivamente. Una muestra menor al objetivo de cien se conserva como insuficiente, sin fabricar pares.

Estratos: sector, modalidad, banda de cuantía, departamento, vigencia, banda A, banda B, cobertura y disponibilidad documental. Bandas de score 40/70, cobertura 25/65 y cuantía COP 100 millones/1.000 millones: decisiones de diseño, no cortes calibrados. No se seleccionan sólo scores altos. Las procedencias distinguen marco propio y búsqueda independiente; los fixtures permiten representar exclusivos A/B, búsqueda independiente y selección aleatoria, sin convertir esa procedencia en una etiqueta humana.

Entrada real: snapshots propios completos o snapshots concedidos expresamente por su dueño. `additional_opportunity_ids` incorpora candidatos públicos recuperados mediante búsqueda independiente, con `independent_search_reference` obligatoria. Si no existe score A vigente para un candidato adicional, se registra null; no se inventa ni se recalcula silenciosamente. Los documentos privados de otros usuarios no se buscan sin autorización. Los candidatos adicionales no heredan requisitos documentales que no fueron congelados.

Se usa un identificador estable de **proceso SECOP II**, no UID SECOP I ni ID contractual. Primero se fija un representante determinista por proceso a nivel de campaña; se registran pares excluidos y se declara el marco resultante. Esto evita contar adjudicaciones/duplicados del mismo proceso como independientes, aunque puede reducir representación empresarial. La inferencia se limita a ese marco; no representa automáticamente todo SECOP.

Primero se calculan los top-20 A/B del marco congelado por consulta: BOTH, A_ONLY, B_ONLY y NEITHER, separados de la búsqueda independiente. Una referencia no ejecutada se identifica como UNCOMPUTED_REFERENCE, no como exclusividad de V2. Se reserva representación para cada grupo disponible cuando el presupuesto alcanza su número; luego se estratifica dentro de cada grupo. El manifiesto registra grupos disponibles/seleccionados y las probabilidades condicionales a la asignación de plazas.

Dentro de cada grupo primario: con H estratos y n>=H se asigna al menos una plaza por estrato y se distribuye el resto de forma reproducible; inclusión de cada unidad h: n_h/N_h. Con n<H se eligen n estratos uniformemente y una unidad por estrato: inclusión n/(H N_h). Semilla y orden canónico permiten reproducir la selección. Las probabilidades no se usan para presentar métricas sin ponderar como estimadores poblacionales.

Identidad estadística real: las FK de organización consistentes del perfil/cuenta agrupan miembros de la misma empresa. Identidades ausentes o contradictorias se colapsan en un único grupo no verificado; no se cuentan cuentas como empresas independientes. Esos grupos y su procedencia se registran. Además se retienen los IC si hay identidades empresariales no verificadas en el manifiesto, aunque se alcance el número nominal de clusters. Antes de inferir, el operador debe validar organizaciones e independencia; no se modifica ni migra la pertenencia empresarial.

Holdout por empresa completa, no por fila. Una empresa no aparece en desarrollo y holdout. La rúbrica y el margen primario se sellan antes de juicios. Con veinte empresas y reserva del 20%, sólo cuatro quedan en holdout: el piloto inicial normalmente no basta para IC confirmatorios. Debe ampliarse el conjunto; no se rebajan mínimos después de ver resultados.

Plantilla lista para importar: `backend/evaluation/phase21/pilot-synthetic-100.json`, cien pares ficticios, veinte empresas ficticias, varios sectores/modalidades/cuantías/vigencias y sin etiquetas, documentos o credenciales reales. Las etiquetas de procedencia del fixture son escenarios diseñados, no trazas de recuperadores reales.

## 5. Evaluación humana

Rol explícito `evaluation_reviewer`; el administrador no puede autoevaluar. Cada asignación expone sólo alias, actividad/productos/preferencias autorizadas, objeto/descripción/modalidad/valor/vigencia, requisitos disponibles y enlace oficial HTTPS permitido. No retorna scores, ranking, estratos, contribuciones V2, cobertura calculada o etiquetas de otros revisores. Tampoco retorna el snapshot completo mediante un serializador genérico.

Se registra relevancia estricta 0–3, elegibilidad, calidad documental, motivo, pendientes, referencia de sustento, fecha, asignación y versión de rúbrica. Opiniones VERIFIED exigen referencia; no se convierten en certificaciones ni se escriben al motor comercial. Las fuentes incompletas siguen siendo desconocidas.

Nombres/NIT no están en el perfil de matching exportado a revisores; se añaden alias y redacción de correos, URLs e identificadores con prefijos comunes. Esto es **pseudonimización**, no garantía de anonimato irrevertible: el dueño debe revisar texto libre y autorizarlo antes de usar datos reales. Los extractos documentales requieren permiso separado, se acotan y se muestran como extracción no verificada. Nunca se incluye una descarga de documentos privados en el informe.

Los juicios de campañas sintéticas se identifican como `synthetic_test` en la evaluación y se excluyen de evidencia comercial/humana real. Las campañas autorizadas reales requieren doble evaluación/adjudicación antes de contar un juicio final. Los fixtures automatizados de esta entrega no constituyen evaluaciones humanas recolectadas.

## 6. Control de desacuerdos

Dos plazas primarias por muestra y usuarios distintos. Se compara relevancia, elegibilidad, calidad y pendientes; diferencias sólo de redacción del motivo no fuerzan discrepancia. Si coinciden las dimensiones, se admite consenso; si difieren, el par queda sin juicio final hasta una adjudicación independiente.

El tercer revisor no puede ser dueño de los datos, administrador de la campaña, revisor primario ni alguien con exposición registrada a los scores de ese par. Recibe contexto ciego; no scores ni respuestas previas que orienten su decisión. La resolución conserva tanto juicios primarios como la adjudicación y su procedencia.

No hay endpoint de edición de juicios. UNIQUE por asignación evita duplicados; el cierre se serializa con las entregas mediante bloqueo de campaña. Juicios, adjudicaciones, informes y exposiciones tienen además protección ORM contra modificación. Un error se corrige mediante una nueva campaña auditada, sin borrar o sobrescribir la evidencia original. No se promete resistencia a un administrador que altere SQL directamente fuera de la aplicación.

## 7. Integración semántica experimental

Tres brazos: A heredado; B V2 sin semántica; C V2 con semántica real. No se usa fake para C y nunca se copia B a C cuando falta el proveedor. C queda null con motivo si está desactivado, no autorizado, fuera de presupuesto, obsoleto o fallido.

Adaptador compatible con proveedor efectivo OpenAI, text-embedding-3-small, 1.536 dimensiones; valida respuesta, norma, finitud, modelo, versión e identidad de ambos textos. Usa el proveedor/configuración existente, pero registra consumo explícito, fija endpoint oficial y desactiva reintentos ocultos del SDK. Referencia técnica consultada: [guía oficial de embeddings](https://developers.openai.com/api/docs/guides/embeddings) y [API oficial de creación](https://developers.openai.com/api/reference/python/resources/embeddings/methods/create).

Caché por administrador autorizado **y dueño de la fuente**, hash textual y versión; sin compartir vectores privados entre empresas. No se reutilizan vectores obsoletos, de otra versión o fuera de retención. Una reserva fallida/ambigua no se vuelve a cobrar automáticamente. El refresco de una entrada expirada con la misma clave requiere una estrategia explícita posterior; esta versión prefiere abstenerse a reintentar sin control.

Antes de cada llamada: identidad del ambiente, consentimiento de campaña y del dueño de cada fuente, referencia de revisión de condiciones del proveedor, versión/tarifa congeladas, máximo de llamadas y coste. Reserva durable antes de salir a red; límite conservador por bytes UTF-8, texto <=6.000 bytes. Tiempo de espera diez segundos, sin locks durante red. Usage y coste estimado se registran según tarifa configurada, sin afirmar que sea la tarifa vigente del proveedor. Reservas con uso desconocido permanecen visibles como tales y consumen presupuesto conservador.

Sólo se envían sector/actividad/productos/keywords autorizados y texto público del objeto/descripción. No se envían requisitos, extractos, documentos, indicadores financieros, contraseñas o tokens de usuarios. Se permite ficción o datos expresamente autorizados; no se realizaron llamadas reales en esta entrega. Las pruebas del adaptador sustituyen únicamente la red por respuestas controladas, y así se reportan.

Desactivación: flag global false + reinicio de procesos; además, `POST /campaigns/{id}/stop-semantics` persiste una parada inmediata para la campaña y no inicia nuevas llamadas. Una petición ya en vuelo puede haber consumido tokens; se audita y se descarta su uso para el brazo C. No existe reactivación silenciosa de esa campaña. Caché y presupuestos no afectan al recálculo comercial.

## 8. Métricas y fórmulas

Positivos: relevancia 2/3. P@k = relevantes entre primeras k posiciones / k, con k=5/10; posiciones no devueltas cuentan como vacías, pero un resultado sin etiqueta no se etiqueta como irrelevante: la métrica queda null cuando corresponde. Se incluye el marco completo de cada consulta, no sólo filas muestreadas, para evitar evaluar un ranking artificial de los ejemplos juzgados.

La ejecución completa se registra por brazo/consulta. Un B realmente calculado que se abstiene en todo un universo completamente juzgado recibe P@k/Recall/NDCG cero, no desaparece del promedio. Un brazo C no ejecutado por falta de proveedor/presupuesto conserva métricas null. Las conclusiones del holdout exigen ejecución completa de los brazos comparados; intervalos descriptivos sobre un subconjunto ejecutable no se generalizan al holdout completo.

DCG@10 = Σ (2^rel−1)/log2(posición+1); NDCG=DCG/IDCG. Recall@20 = relevantes recuperados en veinte / relevantes del universo. FPR = FP/(FP+TN), a umbral predeclarado 70. Recall/NDCG/FPR sólo se emiten con referencia suficientemente completa según el evaluador existente; FPR puede quedar null si hay abstención. Se informa cobertura y abstención aparte.

Concordancia: acuerdo exacto y kappa ponderada cuadrática: κ=1−D_observado/D_esperado, pesos de desacuerdo (i−j)^2/9, con marginales de los dos revisores. Sin variación esperada suficiente, κ=null. Es descriptiva; no se inventa un IC para concordancia.

Comparación pareada por consulta, bootstrap por empresa (2.000 remuestras, semilla fija), mínimo inicial cien juicios humanos y veinte clusters **utilizables para esa métrica**. Mismos IDs, versiones y ventana en los brazos. IC percentil 95%; sectores insuficientes quedan sin IC. Son mínimos metodológicos, no prueba de potencia o independencia externa.

Margen primario de Fase 2.1 previamente declarado: −0,02 en ΔP@10 del holdout. Si límite inferior >=−0,02: no inferioridad material compatible con el diseño; si límite superior <−0,02: no cumplido; en otro caso, inconcluso. El comparador heredado conserva su regla descriptiva de margen cero; el informe identifica la regla de campaña aplicada a la decisión, evitando mezclarlas. NDCG y cortes sector/modalidad son exploratorios, sin afirmaciones confirmatorias múltiples.

Se emiten métricas por sector y rankings **condicionales por modalidad**, además de diferencias P@10/NDCG. Los casos incluyen rangos A/B/C, dirección de cambio acorde con la relevancia, falsos positivos/negativos entre etiquetas conocidas y abstención por información faltante. Diferencia de score por sí sola no significa mejora. Errores de recuperación se marcan no evaluables sin trazas independientes suficientes; la procedencia no demuestra causalidad. No se inventa atribución entre recuperación y scoring.

Ningún índice ni IC se interpreta como probabilidad de adjudicación. Criterios de seguridad, cobertura y costes conservan estados técnicos/no evaluables separados de las conclusiones estadísticas. El sistema nunca habilita V2 automáticamente, aunque aparezca una diferencia favorable.

## 9. Seguridad

Preflight compara destino exacto DB/broker/API, no sólo environment=DEV. Exige host/socket, base y usuario PostgreSQL explícitos; no admite defaults ambientales PGHOST/PGDATABASE/PGUSER. Redis requiere host/base explícitos o socket absoluto. Las credenciales se excluyen de la identidad de destino y nunca se imprimen. En PostgreSQL comprueba la base efectiva y un UUID/fingerprint persistido con propósito isolated-development. También comprueba la URL de la sesión real. API usa su origen efectivo; emisor y worker validan su broker real. Producción, destinos no listados o marker ausente/diferente fallan cerrados. El preflight de ruta se ejecuta antes de consultar autenticación contra una base no autorizada.

Esta misma comprobación de tupla/marker protege ahora las escrituras y los workers del diagnóstico shadow de Fase 2: su flag por sí solo ya no basta. Requiere 0014 e identidad aprobada antes de volver a habilitarlo en DEV; no altera el matcher ni el recálculo comercial.

La configuración inspeccionada seguía sin autorización; `scripts/evaluation_target.py` devolvió DENIED sin conectar. No se contactó un supuesto DEV para “probar” sus credenciales. El registro de identidad requiere comando explícito, UUID coincidente, aceptación de DEV aislado y esquema 0014; no se autoaprovisiona desde una petición web.

Admin sólo administra campañas propias. Revisores sólo leen asignaciones propias. Los miembros de una misma empresa no heredan acceso. La identidad de consulta conserva usuario/perfil/evidencia, separada del cluster estadístico organizacional; agrupar dependencias no mezcla perfiles o rankings privados.

Los datos de otro usuario requieren EvaluationDataGrant emitido por su dueño autenticado y ligado al hash del snapshot; es revocable y expira. El dueño no puede evaluar su propio perfil. Se requiere secreto de instalación revisado de al menos 32 caracteres para habilitar cualquier evaluación o diagnóstico protegido, incluidos los pseudónimos. Las fixtures usan un secreto fuerte exclusivamente de prueba. Consentir un snapshot no autoriza enviar documentos a un proveedor.

Retención por defecto treinta días, máximo noventa: al vencer se revocan accesos y ejecución; no se borra historial automáticamente. Una política de archivo/cifrado/purga física requiere revisión específica y no se simula aquí. Acciones create/grant/revoke/freeze/assign/judge/close/external_reserve/semantic_stop/identity_provision quedan en AuditLog con IDs/hashes y sin documentos o secretos.

## 10. Interfaz administrativa

`frontend/app/(private)/app/evaluacion-interna/page.tsx` separa modos Revisor/Administración; el servidor decide permisos, no el selector visual. Administración importa JSON autorizado, crea/resume campañas, consulta progreso/consumo, asigna dos revisores, identifica desacuerdos, asigna tercero y cierra para producir/exportar informe sin identificadores directos ni documentos. No muestra scores al revisor ni permite editar juicios sellados.

El informe sólo se entrega al dueño después del cierre. El revisor no obtiene acceso al informe mediante cambio de modo o URL. El formulario valida relevancia, razón y referencias; errores de estado/permisos no registran una respuesta parcial. Selectores tienen nombres accesibles. No se añadió navegación pública o cambios al dashboard comercial.

API principal, prefijo `/api/internal/evaluation`:

- GET/POST `/campaigns`; GET `/campaigns/{id}`.
- POST `/campaigns/{id}/resume`, `/assign`, `/stop-semantics`, `/close`.
- GET `/campaigns/{id}/report`.
- GET `/assignments`, `/assignments/{id}`; POST `/assignments/{id}/judgments`.
- POST `/data-grants`, `/data-grants/{id}/revoke`; sólo el dueño puede conceder/revocar su snapshot.

## 11. Modelos y migraciones

Nueva `0014_evaluation_platform`, descendiente de 0013, con definiciones literales: EvaluationEnvironmentIdentity, EvaluationCampaign, EvaluationSample, EvaluationAssignment, EvaluationJudgment, EvaluationAdjudication, EvaluationReport, EvaluationEmbedding, EvaluationExposure y EvaluationDataGrant. FK a usuarios/snapshots existentes, unicidad de muestras/asignaciones/juicios, leases y cursor persistidos. El AuditLog existente se reutiliza.

No se reescribieron migraciones históricas ni se usó stamp. El arranque `init_db` excluye expresamente las tablas evaluation_* de create_all y del ajuste automático de columnas; 0014 requiere migración autorizada. Las fixtures SQLite las aprovisionan explícitamente sólo en sus bases descartables. Se verificó upgrade vacío, downgrade con tablas vacías, reupgrade con esquema/score heredado existente y correspondencia modelos/tablas en PostgreSQL. Downgrade con identidad, campañas u otra evidencia aborta antes de borrar datos. No se aplicó 0014 a DEV operativo.

La preparación se confirma por cursor/token/lease; un worker tardío no escribe después de takeover. Las llamadas externas no retienen locks. Reserva de coste confirmada antes de red evita duplicar consumo tras una caída ambigua. Reanudación es explícita: tras caída, esperar lease/confirmar destino y solicitar resume; no se agregó un coordinador masivo de evaluación.

## 12. Pruebas ejecutadas

Resultado final: **148 aprobadas, 23 omitidas y 1.516 advertencias** en backend; **14 aprobadas** en PostgreSQL real (4+6+2+2; 5+364+12+6 advertencias), **8 aprobadas** con Redis/Celery/PG reales (6+1+1; 32+8+6 advertencias); TypeScript exit 0 y E2E combinado aprobado. Las 23 omisiones son 14 PG y 8 Redis ejecutadas separadamente, más una prueba histórica opt-in Redis/SQLite no ejecutada. Ver versiones de fuentes, logs íntegros, capturas e informe JSON de ejemplo **sintético** en `backend/benchmarks/phase21/validation.json` y archivos vecinos.

- Suite backend completa, incluidos invariantes matemáticos y evaluadores anteriores, muestreo reproducible de cien pares, deduplicación, holdout por empresa, ciego, permisos, doble revisión, discrepancias, cierre, inmutabilidad, expiración y autorizaciones revocadas.
- Adaptador semántico con red **simulada**: dimensiones/modelo, caché por propietario, fallos sin reintento automático, límites de coste, flags y parada persistente. No son pruebas contra OpenAI real ni prueba de su calidad.
- PostgreSQL real temporal: regresiones anteriores + campañas, locks, fencing, rollback y recuperación de cursor, esquema y downgrade protegido.
- Redis/Celery reales temporales: colas separadas, duplicados, reinicios y recuperación tras matar un worker durante cálculo. Para evitar esperar 120 segundos se adelanta únicamente el lease en la DB descartable; no se modifica reloj/arrendamiento de un servicio operativo. La regresión previa también prueba espera real de leases de diez segundos del matcher.
- TypeScript `tsc --noEmit`.
- E2E real Next/FastAPI/PG/Redis/Celery, únicamente cuentas/perfiles/opiniones ficticias: flujos comerciales previos, creación/asignación, dos revisores en contextos separados, comprobación de ausencia de scores, desacuerdo, tercer adjudicador, cierre/exportación e integridad de scores/triage comerciales; desktop/móvil sin errores JS.

Advertencias no suprimidas: deprecaciones datetime.utcnow y FastAPI on_event, Starlette/httpx, crypt/passlib, ciclo FK companies/users y advertencias de claves cortas detectadas en las primeras corridas. Esas claves de fixtures se reforzaron al exigir el guard >=32; no se silenció el mecanismo de advertencias. Las claves E2E/operativas reales no se copian. Los mensajes de pérdida Redis/reintentos en el escenario de fallo son esperados y se conservan en los logs. El shell RVM también informa restricción de ps en el sandbox.

Se corrigieron durante QA un selector ambiguo con el indicador de Next, nombres accesibles de selects y emails de fixture con dominio reservado rechazados por el contrato `/auth/me`. También se corrigió la interpretación de sockets Redis al canonizar destinos y una carrera de la prueba heredada de recuperación: ahora espera a todos los trabajos del coordinador antes de exigir cero slots globales, manteniendo esa aserción. No se cambió autenticación ni el matcher para ocultar esos fallos.

## 13. Comparaciones disponibles

Informes A/B y B/C pareados por desarrollo/holdout; sectores, modalidad condicional, concordancia, cobertura, abstenciones y casos con variaciones de rango. Se conservan consumo conocido, reservas máximas y llamadas con uso desconocido. Puede repetirse el cálculo sobre el mismo snapshot y juicios; el informe cerrado se conserva con hash de versión.

La muestra ficticia preparada permite probar el protocolo completo, no demostrar calidad comercial. Las pruebas de bootstrap existentes usan fixtures explícitos y no se convierten en resultados humanos reales. El informe distingue SYNTHETIC_PROCEDURE_ONLY/INCONCLUSIVE de estimaciones humanas pareadas suficientes.

## 14. Comparaciones pendientes por falta de etiquetas

No hay pares reales autorizados adjudicados ni evaluadores humanos reales incorporados durante esta ejecución. Precisión, recall, NDCG, FPR, diferencias e IC **reales** siguen pendientes, al igual que beneficio/coste real de semántica, no inferioridad comercial, desempeño sectorial y seguridad de elegibilidad verificada. Ningún peso se ajustó con datos sintéticos ni con holdout.

Muchos top-k no tendrán todas sus etiquetas en un piloto estratificado pequeño; las métricas quedarán null en vez de evaluar sólo la muestra favorable. Deben ampliar etiquetas sobre el universo y sobre empresas independientes, manteniendo trazabilidad de selección. Cien pares es un piloto metodológico, no una conclusión estadística.

## 15. Riesgos y limitaciones

La pseudonimización de texto no elimina todo identificador indirecto; requiere revisión del dueño. El catálogo UNSPSC heredado v14 y su distribución conservan las limitaciones de Fase 2. No hay OCR, certificación jurídica ni inferencia automática de requisitos completos. Fuente real inicial limitada a identificadores de proceso SECOP II; SECOP I/adjudicaciones no se introducen como oportunidades abiertas.

El baseline A de ficción usa hashing y se identifica como tal. Un score heredado no verificable queda ausente o exige nueva captura; no se sustituye por un cálculo que parezca histórico. Los cortes de score no están calibrados entre motores; ranking, abstención y evidencia deben analizarse conjuntamente.

La evaluación offline usa desempate determinista por ID pseudónimo y no reproduce por sí sola todos los filtros/ordenamientos del serving comercial. La inferencia sólo cubre el marco deduplicado declarado; los cortes sectoriales múltiples son exploratorios. La variación de un score o rango no demuestra causalidad. La atribución a recuperación necesita trazas adicionales. Las capacidades de archivo físico, refresco controlado de caché expirada, cotas globales de gasto entre múltiples campañas y medición de coste SaaS real necesitan revisión operativa antes de ampliar uso. Esta implementación ya limita tamaño, lotes, llamadas y presupuesto **por campaña**, con proveedor apagado por defecto.

La identidad del destino debe ser revisada por el operador; una allowlist/marker no sustituye el control de red/credenciales o respaldo del ambiente. No se auditó la infraestructura externa ni se certifica que una máquina ajena no tenga otros procesos conectados a producción.

## 16. Procedimiento de despliegue DEV — preparado, no ejecutado

1. Operador autorizado: identificar hosts reales de API/DB/Redis, base, usuario de servicio, proxy y workers; confirmar separación de producción y respaldo recuperable de DEV. No copiar cuentas, passwords, tokens o documentos desde producción. Revisar diff completo: la rama conserva trabajo local de fases anteriores.
2. Crear configuración DEV explícita. `DATABASE_URL` y `REDIS_URL` se entregan por el gestor de secretos; la allowlist puede omitir passwords. Mantener proveedor externo apagado y cero llamadas.

```dotenv
ENVIRONMENT=development
# SECRET_KEY: configurar un secreto fuerte >=32 caracteres mediante gestor de secretos.
EVALUATION_ENABLED=true
EVALUATION_API_ORIGIN=https://DEV_API_HOST
EVALUATION_DEV_TARGETS=[{"database":"postgresql+psycopg2://DEV_USER@DEV_DB_HOST:5432/DEV_DB_NAME","broker":"rediss://DEV_REDIS_HOST:6379/DEV_REDIS_INDEX","api_origin":"https://DEV_API_HOST","identity":"UUID_REVISADO_DE_36_CARACTERES"}]
EVALUATION_SEMANTIC_ENABLED=false
EVALUATION_EXTERNAL_MAX_CALLS=0
EVALUATION_MAX_UNIVERSE=500
EVALUATION_MAX_SAMPLE=100
```

3. En el entorno backend configurado ejecutar primero `python scripts/evaluation_target.py`: sólo valida configuración y no abre conexión. Debe coincidir exactamente la tupla aprobada. No sustituir placeholders con producción ni relajar orígenes con comodines. El origen de Request detrás del proxy debe corresponder al aprobado.
4. **Sólo tras autorización operativa y respaldo**, revisar `alembic current` (esperado 0013) y `alembic heads` (0014), y ejecutar manualmente `alembic upgrade head`. No stamp. Inspeccionar FK/columnas/índices, scores/relaciones previos y timezone UTC de las sesiones PostgreSQL, conforme a la convención DateTime heredada. Estos comandos no fueron ejecutados aquí contra DEV.
5. Registrar identidad, también manual y sólo en ese destino aprobado:

```sh
python scripts/evaluation_target.py --register-identity UUID_REVISADO_DE_36_CARACTERES --acknowledge-isolated-dev
python scripts/evaluation_target.py --verify-database
```

El script no sobrescribe identidad diferente ni despliega/migra. Exige revisión 0014 y deja auditoría de provisión.

6. Levantar API/frontend de DEV mediante su procedimiento revisado; mantener matcher comercial/alertas existentes. Arrancar un worker dedicado, sin beat: `celery -A app.workers.celery_app.celery_app worker -Q evaluation --concurrency=1 --prefetch-multiplier=1`. Verificar que su broker efectivo es el aprobado y que otros workers no consumen evaluation accidentalmente.
7. Crear cuentas **nuevas de prueba**, sin cambiar suscripciones o roles de clientes. Autorizar admin y tres evaluation_reviewer mediante IAM/procedimiento administrativo auditado; no hay autoasignación pública de roles. Abrir ruta interna e importar pilot-synthetic-100.json. Revisar doble ciego, discrepancias y recuperación antes de datos reales.
8. Campaña real: dueño emite grant de snapshot de DEV, referencia de autorización, revisión de texto y permiso documental separado; usar perfiles/opciones públicas autorizadas. Revisar retención y seed/holdout antes de asignar. No clonar producción. Incluir búsquedas independientes y los escenarios disponibles, registrando ausencias en vez de inventarlas.
9. Semántica, si se autoriza: revisar condiciones y tarifa con el dueño, habilitar proveedor/configuración real compatible, fijar límites pequeños, referencia y permiso externos explícitos en campaña/grants. Revisar primero qué textos se enviarían. Verificar caché/coste; stop-semantics permite detener sin tocar el ranking. No habilitarla automáticamente desde un rol.
10. Recoger dos juicios por par y resolver desacuerdos; cerrar para sellar. Revisar métricas, tamaños efectivos, abstenciones y sectores; ampliar muestra cuando sean insuficientes. Reservar un holdout nuevo para cualquier calibración futura. No activar V2 comercial por el resultado de este procedimiento.

## 17. Procedimiento de rollback

Desactivar `EVALUATION_ENABLED`, `EVALUATION_SEMANTIC_ENABLED` y la cola/worker evaluation, conservando workers matches/colas comerciales. Para un experimento en curso, ejecutar primero stop-semantics si hay un operador autenticado; una llamada en vuelo puede completar consumo, que debe auditarse. Reiniciar API/worker para flags globales. Verificar 404 en API interna y funcionamiento comercial.

Mantener 0014 y datos de auditoría. No borrar campañas, marker, juicios, cachés o informes para forzar downgrade. `alembic downgrade 0013_compatibility_shadow` sólo admite las diez tablas vacías, únicamente en un destino aislado autorizado; con historial aborta antes de borrar. Para revertir código, revisar y retirar sólo cambios de Fase 2.1, sin resetear fases anteriores o datos comerciales. No se ejecutó rollback en DEV operativo.

## 18. Matriz de criterios de aceptación

| Criterio | Implementación/validación local | Validación operativa o estadística |
|---|---|---|
| Selección reproducible/estratificada | Cumplido con seed, probabilidades y frame | Representatividad real pendiente |
| Juicios ciegos | Cumplido; API y E2E sin scores | Personas reales pendientes |
| Permisos/aislamiento | Cumplido; destino, owner, reviewer y grant | IAM/red DEV pendientes |
| Desacuerdos/tercer revisor | Cumplido; historia inmutable | Concordancia humana pendiente |
| Métricas correctas | Cumplido con fixtures y evaluador reutilizado | Calidad real no evaluable |
| Pares/bootstrap/holdout | Cumplido, reproducible y separado por empresa | IC reales inconclusos |
| Ablación semántica aislada | Cumplido técnicamente, red simulada | Proveedor/beneficio real pendientes |
| Campañas sin producción | Cumplido; configuración no autorizada denegada | DEV operativo no desplegado |
| Versiones/historial | Cumplido; 0014 aditiva y rollback protegido | Respaldo DEV pendiente |
| Regresión | Cumplida según sección 12/evidencia | No certifica operación productiva |
| Procedimiento DEV | Preparado, no ejecutado | Requiere autorización del operador |
| Documentación | Entregada | Calibración/activación no autorizadas |

Las condiciones técnicas cumplidas no convierten en cumplidas las hipótesis de calidad. No inferioridad, mejora semántica, falsos positivos de alto score, elegibilidad verificada y sostenibilidad deben declararse no evaluables o inconclusos mientras no exista evidencia suficiente. Si un IC muestra deterioro material, el informe puede marcar no cumplido; nunca cambia pesos o activa otro motor por ello.

## 19. Recomendaciones para calibración posterior y archivos

Recoger juicios independientes reales con trazas de recuperación y resolución documentada; revisar validez de constructo de relevancia/elegibilidad/evidencia; medir desacuerdos por sector; ampliar empresas y holdout según variabilidad/potencia. Ajustar sólo con desarrollo separado; no usar el conjunto final ni resultados sintéticos para optimizar pesos. Revisar precio real, retención y beneficio semántico por sector antes de proponer otra fase. No entrenar LambdaMART con esta evidencia.

Archivos nuevos principales: `backend/app/services/evaluation_{guard,sampling,platform,semantic,reporting}.py`, `backend/app/evaluation_schemas.py`, `backend/app/routers/evaluation.py`, `backend/alembic/versions/0014_evaluation_platform.py`, `backend/scripts/evaluation_target.py`, `backend/scripts/e2e_evaluation_flow.py`, `backend/tests/evaluation_test_support.py`, `backend/tests/test_evaluation_platform.py`, `test_postgresql_evaluation.py`, `test_redis_evaluation.py`, `backend/evaluation/phase21/pilot-synthetic-100.json`, `backend/benchmarks/phase21/` y la página interna.

Ampliados: config/modelos/main, arranque DB (exclusión del nuevo esquema automático), fixtures SQLite explícitas, guardia del diagnóstico shadow/API/worker anterior, colas/tareas Celery, compatibilidad del evaluador con fixtures opt-in, runners PG/Redis/E2E, arnés de worker descartable y `.env.example`. No cambiaron `matcher.py`, las funciones/pesos de `compatibility_v2.py`, `embeddings.py`, licenciamiento, pagos o el orden público del ranking. No hay commits nuevos.
