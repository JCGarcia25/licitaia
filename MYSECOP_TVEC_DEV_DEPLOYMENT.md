# TVEC: despliegue DEV autorizado, 2026-11-17

Destino exclusivo: develop / development / https://dev.mysecop.co / licitaia-dev.
Se conserva el flujo GitHub Actions existente; el agente no accede al VPS por SSH.

La extensión optativa enable_tvec_dev se activa únicamente en deploy-development.yml.
Antes de construir o migrar, scripts/tvec-dev-deploy.sh valida contenedores, redes y
volumen PostgreSQL sin compartir con otros proyectos, configuración efectiva de API,
base real, revisión 0014/0015 y conexión Redis. Exige la ingesta apagada.
Crea un pg_dump completo privado en backups/tvec-<commit>/database.dump, conserva
.env anterior y verifica la restauración completa en un PostgreSQL temporal de la
misma imagen, sin red. Elimina únicamente ese contenedor/volumen temporal.
Ningún respaldo ni credencial se publica en GitHub. Si falla, no migra ni despliega.

Después del despliegue estándar y migración aditiva 0015, construye una lista exacta
de destinos sin contraseñas, registra una identidad aislada (reutiliza una identidad
existente con igual huella y propósito, sin sobrescribirla), habilita TVEC en DEV y
verifica el guard con la base real. Configura como proxies de confianza sólo localhost
y el gateway exacto de la red Docker de DEV, para conservar el origen HTTPS. Prueba
una lectura TVEC por HTTPS con un token administrativo de un minuto en memoria,
sin modificar cuentas ni imprimir tokens o datos de usuarios. Mantiene TVEC_INGEST_ENABLED=false, sin crear runs,
importar registros ni añadir horarios. Las vistas muestran inicialmente datos vacíos.
Si falla la activación, restaura la configuración previa y recrea sólo API/worker/beat
DEV; conserva el esquema aditivo y cualquier identidad registrada para revisión.

## Rollback

Deshabilitar TVEC_ENABLED y TVEC_INGEST_ENABLED en la configuración de DEV y recrear
sus servicios mediante el flujo operativo existente. Revertir sólo el cambio TVEC
en develop y volver a desplegar; conservar Contacto y WhatsApp. El rollback habitual
conserva 0015 y sus tablas: no restaura la base ni borra datos. El downgrade a 0014
sólo se permite con las cinco tablas TVEC vacías; Alembic bloquea tablas con datos.
La restauración del respaldo es una recuperación excepcional y requiere revisar las
escrituras posteriores; no se ejecuta automáticamente sobre la base activa.

## Validación

El informe MYSECOP_TVEC_INTEGRACION_DEV.md contiene las pruebas previas de PostgreSQL,
Redis y E2E local (estos últimos usan API simulada). En esta publicación se repiten
la suite backend y TypeScript. GitHub Actions registra adicionalmente la restauración,
migración e identidad reales de DEV y el build. El resultado final y sus enlaces
se guardan en MYSECOP_TVEC_DEV_DEPLOYMENT.json después de terminar el flujo.
No se despliega STG/producción ni se ejecuta ingesta de prueba en DEV.
