# Decisiones de arquitectura (ADRs) — LicitaIA

Cada decisión registra contexto, decisión y consecuencias. Los componentes son
sustituibles cuando exista una alternativa técnica mejor.

## ADR-001 — Backend: Python + FastAPI con API REST documentada (OpenAPI)
**Contexto:** productos SaaS con agentes de IA y analítica de datos.
**Decisión:** FastAPI (tipado Pydantic, OpenAPI automática en `/docs`), SQLAlchemy 2.0.
**Consecuencias:** ecosistema ideal para embeddings/RAG; contracto OpenAPI sirve al frontend Next.js.

## ADR-002 — Frontend: Next.js + TypeScript + Tailwind + estilo shadcn/ui + Recharts
**Contexto:** se requiere landing comercial y app privada, responsive, claro/oscuro.
**Decisión:** Next.js App Router; componentes UI propios en el estilo shadcn (Card/Button/Badge/Input/Select)
para evitar dependencia del CLI; Recharts para analítica.
**Consecuencias:** un solo lenguaje visual; exportación PPTX/PDF no aplica (producto web).

## ADR-003 — Persistencia: PostgreSQL + pgvector; Redis para caché/colas
**Contexto:** búsqueda semántica sobre millones de procesos SECOP.
**Decisión:** Postgres 16 con extensión pgvector (imagen `pgvector/pgvector:pg16`) para índices vectoriales;
Redis para colas Celery y caché. En desarrollo sin Docker, SQLite funciona por paridad de modelos.
**Consecuencias:** los embeddings se almacenan como JSON en el modelo y se calcula coseno en proceso;
al migrar a pgvector se sustituye por `vector` + índice ANN (interfaz `app/services/embeddings.py` sin cambios).

## ADR-004 — Embeddings con proveedor configurable (fake → OpenAI)
**Contexto:** el MVP debe funcionar sin claves externas, pero en producción se busca calidad semántica.
**Decisión:** `EMBEDDING_PROVIDER=fake` (hashing determinista de bolsas de palabras, reproducible, sin red)
por defecto; `openai` (text-embedding-3-small) en producción con `OPENAI_API_KEY`. El matching combina
búsqueda léxica verificable (keywords/UNSPSC/ubicación/cuantía/modalidad) con similitud semántica.
**Consecuencias:** el score y las razones son explicables; la semántica real se activa sin cambios de código.

## ADR-005 — Agentes como servicios puros + routers delgados
**Contexto:** cuatro agentes (Cazador, Analista, Evaluador, Preparador) con evolución independiente.
**Decisión:** la lógica vive en `app/agents/*` y `app/services/*` (funciones puras, testeables); los routers
solo hacen orquestación y persistencia. Celery ejecuta el trabajo programado; `run_or_delay` permite
ejecución en línea cuando Redis no está disponible (desarrollo).
**Consecuencias:** tests unitarios sin HTTP; los agentes son reutilizables por workers y API.

## ADR-006 — Analista de pliegos: extracción con citas + modo heurístico/LLM
**Contexto:** no se puede inventar requisitos ni concluir cumplimiento sin evidencia.
**Decisión:** extracción de texto PDF/DOCX/XLSX con patrones auditables; cada hallazgo guarda
documento + página/sección + cita literal + nivel de confianza; estados permitidos
`Cumple / No cumple / Por verificar / Información insuficiente`; el resultado queda en estado
`borrador` y exige validación humana. `LLM_PROVIDER=openai` permite potenciar la extracción con
salidas estructuradas validadas (RAG sobre fragmentos del documento).
**Consecuencias:** trazabilidad completa; el sistema declara "Información insuficiente" en lugar de inventar.

## ADR-007 — Migraciones: Alembic con metadata como fuente única
**Contexto:** evitar divergencia entre modelos y migraciones.
**Decisión:** `0001_initial` delega en `Base.metadata.create_all`; migraciones posteriores se escriben a mano.
**Consecuencias:** paridad garantizada entre desarrollo y producción; cambios de esquema siempre vía Alembic en producción.

## ADR-008 — Seguridad y cumplimiento
**Decisiones:**
- Contraseñas con bcrypt (passlib), sesiones JWT HS256 firmadas, `SECRET_KEY` por entorno.
- CORS restringido por variable; archivos privados en `STORAGE_DIR` (compatible con S3 en producción);
  nombres de archivo sanitizados y límite de 25 MB con whitelist de formatos.
- **No hay presentación automática de propuestas en SECOP** (el flujo termina en "listo para carga manual").
- LicitaIA **no es una plataforma oficial del Gobierno colombiano**: sin emblemas institucionales,
  con aviso visible en landing y footer.
- Se respetan los términos de datos.gov.co (app token, sin evasión de límites ni CAPTCHAs).
- Los pesos de viabilidad son configurables y no representan criterios oficiales de adjudicación;
  el evaluador incluye el descargo "NO constituye una probabilidad de adjudicación".

## ADR-009 — Alertas: in-app siempre + correo opcional (supuesto del alcance)
**Contexto:** el enunciado original se corta en "11. SISTEMA DE ALERTAS".
**Decisión:** implementar alertas con valores por defecto razonables: alertas in-app
(alta compatibilidad, recordatorios de cierre D-10/D-5/D-1), resumen diario a las 07:00
America/Bogota con correo opcional vía SMTP configurable, y preferencias por usuario
(umbral, días, hora). Supuesto documentado y ajustable.
**Consecuencias:** el sistema es útil sin SMTP; el correo se activa con variables de entorno.
