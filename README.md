# LicitaIA — SaaS de agentes inteligentes para contratación pública en Colombia

> "La inteligencia detrás de tu próxima licitación."
>
> "LicitaIA encuentra las oportunidades de contratación pública que encajan con tu empresa, analiza sus requisitos y te ayuda a decidir dónde competir."

**LicitaIA no es una plataforma oficial del Gobierno colombiano.** Consume fuentes
públicas oficiales (SECOP en datos.gov.co) y mantiene siempre el enlace al expediente original.

## Stack

| Capa | Tecnología |
|---|---|
| Frontend | Next.js 15 + TypeScript + Tailwind CSS + estilo shadcn/ui + Recharts |
| Backend | Python 3.12 + FastAPI (OpenAPI en `/docs`) + SQLAlchemy 2.0 + Alembic |
| Datos | PostgreSQL 16 con pgvector (SQLite en desarrollo) + Redis |
| Procesamiento | Celery (worker + beat) con ejecución en línea de respaldo |
| IA | Embeddings configurables (fake ↔ OpenAI), matching semántico + léxico, RAG preparado |
| Operación | Docker Compose, CI (GitHub Actions), pruebas con pytest, logs estructurados |

## Arranque rápido (Docker)

```bash
cp .env.example .env          # ajustar SECRET_KEY y, opcionalmente, SMTP y OPENAI_API_KEY
docker compose up --build
# Frontend:  http://localhost:3000
# API docs: http://localhost:8000/docs
```

## Despliegue en VPS

Para desplegar en un servidor que ya aloja otros proyectos, usa el script
`scripts/deploy.sh`. No ejecuta `docker compose down` ni detiene contenedores
de otros proyectos; utiliza puertos locales separados y un volumen persistente
para documentos.

```bash
DOMAIN=licitaia.centralspike.com ./scripts/deploy.sh
```

El script crea o actualiza `.env`, genera `SECRET_KEY` y `POSTGRES_PASSWORD`
si todavía tienen valores de ejemplo, ejecuta las migraciones y valida
`/health`. Nginx debe dirigir `/api/` al puerto local `8001` y el resto al
puerto local `3000`. Para usar otros puertos:

```bash
DOMAIN=licitaia.centralspike.com \
LICITAIA_API_PORT=8001 \
LICITAIA_FRONTEND_PORT=3001 \
./scripts/deploy.sh
```

## Arranque rápido (local, sin Docker)

```bash
# Backend
cd backend
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./licitaia.db ENVIRONMENT=development
uvicorn app.main:app --reload            # http://localhost:8000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev                              # http://localhost:3000
```

**Cuenta de demostración** (se crea sola en el primer arranque con datos de ejemplo):
`demo@licitaia.co` / `LicitAIA2026`

## Los cuatro agentes

1. **Cazador de Oportunidades** — puntúa cada proceso SECOP (0-100) contra el perfil
   empresarial con razones verificables (keywords, UNSPSC, ubicación, cuantía, modalidad,
   similitud semántica). `POST /api/rescore`.
2. **Analista de Pliegos** — extrae objeto, presupuesto, cierre, requisitos, garantías y
   riesgos de PDF/DOCX/XLSX con cita documental (documento, página/sección), nivel de
   confianza y estados `Cumple / No cumple / Por verificar / Información insuficiente`.
   Resultado orientativo, siempre en borrador y con validación humana. `POST /api/opportunities/{id}/analyze`.
3. **Evaluador de Viabilidad** — puntaje global ponderado (30/25/20/15/10, configurable),
   requisitos críticos, fortalezas, debilidades, documentos faltantes, costo estimado de
   preparar la oferta y recomendación participar/revisar/descartar. Incluye el descargo:
   **no es una probabilidad de adjudicación**. `POST /api/opportunities/{id}/viability`.
4. **Preparador de Ofertas** — checklist documental, borradores (carta de presentación,
   matriz de cumplimiento), cronograma interno, comentarios, versiones y exportación
   DOCX/XLSX/PDF. Nunca inventa certificaciones, experiencia ni firmas; no presenta en SECOP.

## Sistema de alertas

- In-app: alta compatibilidad (umbral configurable), recordatorios de cierre D-10/D-5/D-1.
- Resumen diario 07:00 (America/Bogota) con correo opcional (SMTP configurable).
- Preferencias por usuario: `GET/PUT /api/alerts/prefs`, ciclo manual: `POST /api/alerts/digest`.

## Fuentes oficiales

Verificadas el 2026-10-27 — detalle completo en [`docs/fuentes-secop.md`](docs/fuentes-secop.md):

- SECOP II — Procesos de Contratación: dataset `p6dx-8zbt` (datos.gov.co, Socrata)
- SECOP II — Contratos Electrónicos: dataset `jbjy-vk9h`
- SECOP I: dataset `e985-4d7e`
- Catálogo oficial: https://www.colombiacompra.gov.co/transparencia/datos-abiertos/conjuntos-de-datos-abiertos

## Estructura

```
licitaia/
├── backend/
│   ├── app/
│   │   ├── agents/        # pliegos.py, viability.py
│   │   ├── routers/       # auth, profile, opportunities, agents, sync, documents, alerts
│   │   ├── services/      # secop_client, ingest, matcher, embeddings, nlq, alerts, notifier, exporter, demo
│   │   ├── workers/       # celery_app + tareas programadas
│   │   ├── core/          # config (12-factor), security (JWT/bcrypt)
│   │   └── db/            # modelos, sesión
│   ├── alembic/           # migraciones
│   └── tests/             # pytest (unitarios + flujo integral)
├── frontend/              # Next.js: landing comercial + app privada
├── docs/                  # fuentes-secop.md, decisiones-arquitectonicas.md
├── docker-compose.yml     # db+pgvector, redis, api, worker, beat, migrate, frontend
└── .github/workflows/ci.yml
```

## Limitaciones conocidas (honestas)

- El dataset `p6dx-8zbt` **no expone fecha de cierre** de procesos: los recordatorios usan
  la fecha analizada en pliegos o ingresada manualmente.
- Los anexos/pliegos no vienen por la API: se adjuntan manualmente o por enlace público legal.
- El buscador NLQ es un parser heurístico auditable (sustituible por LLM con `LLM_PROVIDER=openai`).
- En el sandbox de desarrollo no hay Docker; el `docker-compose.yml` está validado y el stack
  se probó de forma nativa (pytest + build Next.js).
