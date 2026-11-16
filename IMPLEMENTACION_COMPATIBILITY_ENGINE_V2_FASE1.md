# Compatibility Engine V2 — Fase 1: avance parcial

## 1. Resumen ejecutivo

Se implementaron mejoras locales para preservar filtros explícitos, distinguir la vigencia desconocida y actualizar registros existentes de SECOP sin romper sus asociaciones. **La fase 1 no está terminada**: el cursor incremental persistente, el recálculo reanudable y otros criterios de aceptación siguen pendientes. No se han realizado despliegues ni conexiones a fuentes externas o bases productivas.

Revisión adicional: el ranking por perfil ahora se ordena en SQL y recorre candidatos en lotes de 200, aunque la afinidad final y el cómputo del total siguen requiriendo recorrer todos los candidatos en Python. Se evita asignar un score artificial al crear una relación para guardar o preparar una oferta. Fechas con offset explícito se convierten a UTC; las fechas sin zona permanecen flotantes. Los registros históricos con puntuación cero no se modifican: no es posible distinguir con seguridad un cero calculado de uno anteriormente asignado por defecto.

## 2. Hallazgos confirmados

La inspección partió de `develop`, commit `cac56d0`. Se confirmó la repetición silenciosa de búsquedas sin el filtro de puntuación, las diferencias de vigencia, el límite de 1.500 sin orden explícito y la actualización parcial de registros. La ausencia de cursor persistente efectivo sigue presente.

## 3. Arquitectura implementada

`backend/app/services/opportunity_status.py` incorpora una clasificación conservadora con estado original y motivo; la usan la condición de búsqueda y la evaluación de alertas. El frontend informa cuando no hay evidencia suficiente para confirmar vigencia. No se cambió la fórmula del matcher ni el proveedor de embeddings.

## 4. Archivos modificados

- `backend/app/services/opportunity_status.py`: clasificación y condición SQL de vigencia.
- `backend/app/services/alerts.py`: uso de clasificación común y orden determinista inicial del recálculo.
- `backend/app/routers/opportunities.py`: condición común, campo de vigencia, filtros explícitos y coherencia de puntuación cero.
- `backend/app/services/ingest.py`: actualización de metadatos y regeneración del vector cuando cambia el texto.
- `frontend/app/(private)/app/oportunidades/page.tsx`: mantiene el filtro solicitado y muestra vigencia por confirmar.
- `backend/tests/test_opportunity_status.py` y `backend/tests/test_secop.py`: pruebas del estado y reingesta.
- `backend/app/db/models.py` y `backend/app/routers/agents.py`: nuevas relaciones de oportunidad sin puntuación utilizan `NULL`.
- `backend/tests/test_opportunities_search.py` y `backend/tests/test_dashboard_ranking.py`: comprueban ausencia de puntuación inventada, aislamiento del estado entre dos usuarios y desempate de páginas con puntuaciones iguales.
- `backend/app/services/secop_client.py`: interpretación de fechas ISO con zona explícita.

## 5. Migraciones

No hay migraciones nuevas ni se ejecutaron migraciones sobre ambientes. Las capacidades pendientes pueden requerir migraciones reversibles y pruebas con PostgreSQL.

## 6. Cambios de API

Las respuestas de oportunidad incluyen `vigencia` con `status`, `reason`, `original_state`, `source`, `closing_date` y `updated_at`; es un campo aditivo. La casilla de puntuadas admite puntuaciones de cero y la búsqueda ya no retira el filtro silenciosamente. Los criterios de perfil ya no se omiten para oportunidades guardadas o en proyecto. Estos cambios pueden disminuir resultados respecto al comportamiento anterior.

## 7. Reglas de vigencia

El servicio reconoce estados terminales explícitos, cancelación, fechas futuras de publicación y cierre vencido. Solo clasifica `OPEN` cuando el estado reconocido y un cierre futuro están presentes; sin evidencia suficiente retorna `UNKNOWN`. Los registros de contratos no se tratan como convocatorias abiertas. La lista general conserva registros `UNKNOWN` identificados como «Vigencia por confirmar en SECOP»; no se presenta esa clasificación como apertura confirmada. Las variantes y equivalencias de cada fuente todavía requieren validación exhaustiva; no se garantiza que cada fuente provea una fecha de cierre verificable.

## 8. Reglas de normalización

Se normalizan mayúsculas, espacios y tildes para clasificación de estados. La normalización integral por catálogo de localidades, modalidades, UNSPSC, identificadores, fechas y cuantías con `Decimal` está **pendiente**. La fecha de cierre no se infiere de publicación ni se sustituye por la hora actual.

## 9. Ingesta incremental

La reingesta actualiza todos los metadatos enumerados en `ingest.py`, conserva asociaciones e identifica cambios de texto para regenerar el vector. No elimina un cierre ya registrado si la fuente no informa uno. El cursor persistente con desempate, solapamiento y recuperación transaccional **no está implementado**; la paginación actual no garantiza cobertura incremental completa. No se ejecutaron sincronizaciones reales.

## 10. Cobertura y recálculo

El subconjunto actual se ordena por identificador para evitar selección arbitraria. Permanece el límite de 1.500, sin métricas completas de cobertura, reanudación, versionado ni procesamiento asíncrono por lotes. No debe afirmarse que todas las oportunidades fueron puntuadas. Cambios a esos flujos requieren diseño y pruebas adicionales.

## 11. Deduplicación

Se conserva la unicidad por fuente e identificador y las relaciones existentes. La identificación canónica entre fuentes y la detección de posibles duplicados **están pendientes**; no se fusionan procesos automáticamente.

## 12. Métricas

Se mantienen los registros de sincronización existentes. Las métricas de cobertura, resultados por vigencia, duración de consultas, latencias p50/p95/p99 y registros modificados frente a no modificados **no se implementaron en esta entrega**.

## 13. Pruebas ejecutadas

- Backend completo: `PYTHONDONTWRITEBYTECODE=1 /tmp/mysecop-audit-venv/bin/python -m pytest -q -p no:cacheprovider --tb=short`, **62 aprobadas**, SQLite y servicios simulados; 625 advertencias visibles en `/tmp/mysecop-fase1-tests.log`, sin evaluación de producción.
- Frontend: `./node_modules/.bin/tsc --noEmit --incremental false`, **aprobado**.
- No ejecutadas: integración PostgreSQL, pruebas de carga, E2E visual, servicios Socrata y validación del ambiente DEV desplegado.

Docker no está instalado en este entorno y no se pudo levantar PostgreSQL aislado. Tampoco se midieron concurrencia, rendimiento o cobertura de datos reales. Las advertencias incluyen API de fechas `utcnow`, ciclo de claves foráneas al crear tablas de prueba, ciclos de vida de FastAPI, compatibilidad de TestClient y longitud de la clave JWT de pruebas; requieren revisión separada. No fueron desactivadas en esta ejecución.

### Criterios de aceptación

| Criterio | Estado | Evidencia o trabajo pendiente |
|---|---|---|
| Filtros explícitos sin retirada silenciosa | Parcial | Quitado el fallback del frontend; quedan variantes textuales y pruebas combinadas. |
| Vigencia centralizada | Parcial | Servicio compartido; catálogo y equivalencia SQL/Python por fuente pendientes. |
| Cierre desconocido explícito | Parcial | Etiqueta en listado; faltan verificaciones de procedencia en todos los consumidores. |
| Orden determinista y paginación | Parcial | Orden por puntuación e ID; afinidad y total se recorren por lotes en Python. No se ha medido el costo. |
| Cobertura real del recálculo | Pendiente | Sigue el límite de 1.500; no hay reanudación ni medición de cobertura. |
| Ingesta incremental idempotente y segura | Pendiente | No existe cursor persistente ni pruebas de interrupción entre páginas. |
| Actualización de registros | Parcial | Reingesta y cambio de vector probados con fuente simulada; falta invalidación de puntuaciones y concurrencia. |
| Trazabilidad y observabilidad | Parcial | Historial SyncRun existente; faltan métricas de cobertura, latencia, obsolescencia y estados. |
| Funciones comerciales y aislamiento | Parcial | Suite existente y una prueba entre usuarios aprobadas; sin prueba completa entre organizaciones ni PostgreSQL. |
| Despliegue reversible | Pendiente | Sin migraciones nuevas ni despliegue; requiere completar pruebas y revisar recuperación de datos actualizados. |

## 14. Riesgos pendientes

Falta validar catálogos por fuente y fechas con evidencia de origen, coherencia completa SQL/Python, paginación de recomendaciones en memoria, aislamiento funcional entre organizaciones, tratamiento de estados no reconocidos, exactitud monetaria y obsolescencia de puntuaciones. Las condiciones implementadas no garantizan exhaustividad ni calidad de los datos de origen.

## 15. Pasos para despliegue

Antes de promover cambios, completar los componentes pendientes, ejecutar las suites y pruebas PostgreSQL/E2E, revisar los cambios de comportamiento y verificar cobertura y permisos. Seguir el flujo DEV → STG → producción con autorización expresa para cada promoción. Esta entrega no se desplegó ni se subió a Git.

## 16. Rollback

Revertir el commit que contenga estos cambios y volver a desplegar la versión anterior conforme al flujo de ambientes. No hay migraciones nuevas que revertir. La reingesta ya ejecutada en cualquier ambiente actualiza registros de fuente y vectores; revertir el código por sí solo no restaura datos anteriores, por lo que cualquier recuperación de datos requeriría respaldo y análisis específicos.

## 17. Fase 2

Postergar el modelo matemático avanzado y el aprendizaje de ranking hasta terminar y validar esta fase, tener datos y evidencias confiables, versionar puntuaciones, definir un objetivo observable y disponer de etiquetas suficientes. Un índice de compatibilidad no equivale a una probabilidad de adjudicación.
