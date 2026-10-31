# Variables de entorno de MySECOP

Este documento lista las variables necesarias para ejecutar MySECOP. Los valores
secretos deben configurarse en el servidor o en un gestor de secretos; **no deben
subirse a GitHub ni compartirse por chat**.

## Configuración mínima para producción

```env
ENVIRONMENT=production
SECRET_KEY=genera-una-clave-larga-aleatoria
DATABASE_URL=postgresql+psycopg2://USUARIO:CONTRASENA@db:5432/licitaia
REDIS_URL=redis://redis:6379/0
STORAGE_DIR=/var/lib/licitaia/storage
CORS_ORIGINS=https://licitaia.centralspike.com
ALLOW_DEMO_SEED=false
```

`SECRET_KEY` debe ser diferente en cada instalación. Se puede generar con:

```bash
openssl rand -hex 32
```

## Base de datos y servicios

```env
POSTGRES_DB=licitaia
POSTGRES_USER=licitaia
POSTGRES_PASSWORD=contraseña-larga-y-unica
DATABASE_URL=postgresql+psycopg2://licitaia:contraseña-larga-y-unica@db:5432/licitaia
REDIS_URL=redis://redis:6379/0
STORAGE_DIR=/var/lib/licitaia/storage
```

## SECOP / datos.gov.co

```env
SECOP_APP_TOKEN=
SECOP_DOMAIN=www.datos.gov.co
SECOP_PAGE_SIZE=200
SECOP_MAX_PAGES_PER_RUN=25
SECOP_SYNC_EVERY_MINUTES=30
SECOP_DATASET_PROCESOS=p6dx-8zbt
SECOP_DATASET_CONTRATOS=jbjy-vk9h
SECOP_DATASET_SECOP1=e985-4d7e
```

`SECOP_APP_TOKEN` es opcional, pero recomendable para evitar límites estrictos de
Socrata. Se obtiene en el perfil de desarrollador de datos.gov.co/Socrata.

## Mercado Pago — sandbox

Para probar la suscripción de **MySECOP Pro ($59.900 COP/mes)**:

```env
BILLING_PROVIDER=mercadopago
MERCADOPAGO_ACCESS_TOKEN=APP_USR-...
MERCADOPAGO_PUBLIC_KEY=APP_USR-...
MERCADOPAGO_WEBHOOK_SECRET=
MERCADOPAGO_BACK_URL=https://licitaia.centralspike.com/app/plan
```

El Access Token debe existir únicamente en el backend. La Public Key puede ser
usada por el frontend si posteriormente se integra Checkout Bricks.

Configura en Mercado Pago el webhook:

```text
https://licitaia.centralspike.com/api/billing/mercadopago/webhook
```

El plan Pro solo se activa cuando el webhook verifica que la suscripción está en
estado `authorized`.

Para producción se deben reemplazar las credenciales de prueba por credenciales
de producción y revisar la cuenta comercial, impuestos, términos y política de
cancelación.

## Correo y alertas

```env
SMTP_HOST=smtp.tu-proveedor.com
SMTP_PORT=587
SMTP_USER=usuario-smtp
SMTP_PASSWORD=contraseña-smtp
ALERTS_FROM_EMAIL=alertas@tudominio.com
ALERT_HIGH_SCORE=70
ALERT_CLOSE_DAYS=10,5,1
DIGEST_HOUR=7
TIMEZONE=America/Bogota
```

Si `SMTP_HOST` queda vacío, las alertas dentro de la aplicación siguen activas,
pero no se envían correos.

## Inteligencia artificial

Configuración económica para iniciar:

```env
EMBEDDING_PROVIDER=fake
EMBEDDING_DIM=768
LLM_PROVIDER=heuristic
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

Si se habilita OpenAI:

```env
EMBEDDING_PROVIDER=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

## Cuotas y planes

```env
QUOTA_FREE_ANALYSES=20
QUOTA_PRO_ANALYSES=500
CONTACT_EMAIL=contacto@tudominio.com
```

## Protección contra saturación

```env
MAX_CONCURRENT_REQUESTS=32
OVERLOAD_WAIT_SECONDS=0.05
```

Estos valores limitan solicitudes simultáneas para evitar consumo excesivo de
CPU y respuestas `502` del proxy. Si el servidor tiene pocos recursos, comienza
con `16`; si tiene más capacidad, puede probarse `32` o `64` con monitoreo.

## Frontend

```env
NEXT_PUBLIC_API_URL=https://licitaia.centralspike.com
```

Esta variable se incorpora durante el build de Next.js.

## Checklist antes de producción

- Cambiar `SECRET_KEY`.
- Usar contraseña nueva para PostgreSQL.
- Mantener `ALLOW_DEMO_SEED=false`.
- Configurar `CORS_ORIGINS` solo con dominios autorizados.
- Configurar `BILLING_PROVIDER=mercadopago` únicamente cuando el webhook HTTPS esté publicado.
- Ejecutar migraciones:

  ```bash
  docker compose run --rm migrate
  ```

- Verificar:

  ```bash
  curl https://licitaia.centralspike.com/health
  ```

- No imprimir variables secretas en logs ni incluir el archivo `.env` en Git.
