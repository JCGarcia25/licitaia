# Configuración de Gmail para alertas de LicitaIA

Esta guía configura una cuenta de Google para que LicitaIA pueda enviar correos de verificación, alertas y resúmenes diarios a los usuarios.

## 1. Crear o elegir la cuenta remitente

Recomendado: usar una cuenta exclusiva para el sistema, por ejemplo:

```text
alertas@tudominio.com
```

También puede utilizarse una cuenta Gmail:

```text
tu-cuenta@gmail.com
```

No se recomienda usar la cuenta personal de un desarrollador.

## 2. Activar la verificación en dos pasos

1. Entrar a [myaccount.google.com](https://myaccount.google.com/).
2. Abrir **Seguridad**.
3. En **Cómo inicias sesión en Google**, seleccionar **Verificación en dos pasos**.
4. Completar la activación con teléfono, aplicación autenticadora o llave de seguridad.

La verificación en dos pasos es necesaria para crear una contraseña de aplicación.

## 3. Crear una contraseña de aplicación

1. Volver a **Seguridad** en la cuenta de Google.
2. Abrir **Contraseñas de aplicaciones**.
3. Confirmar la identidad si Google lo solicita.
4. Crear una nueva contraseña.
5. Usar como nombre `LicitaIA`.
6. Copiar la contraseña de 16 caracteres que Google muestra.

La contraseña de aplicación funciona como `SMTP_PASSWORD`. No debe usarse la contraseña normal de Gmail.

La contraseña de aplicación debe guardarse en el servidor y nunca subirse a GitHub ni compartirse por chat.

## 4. Variables del servidor

En `~/licitaia/.env` configurar:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=CUENTA_REMITENTE@gmail.com
SMTP_PASSWORD=CONTRASENA_DE_APLICACION
ALERTS_FROM_EMAIL=CUENTA_REMITENTE@gmail.com
TIMEZONE=America/Bogota
DIGEST_HOUR=7
```

`SMTP_USER` y `ALERTS_FROM_EMAIL` deben ser la misma cuenta, salvo que exista un alias autorizado en Gmail o Google Workspace.

## 5. Reiniciar LicitaIA

Después de modificar `.env`:

```bash
cd ~/licitaia
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --force-recreate api worker beat
```

## 6. Requisitos para que un usuario reciba alertas

El usuario debe cumplir estas condiciones:

- Tener un correo válido registrado.
- Tener el correo verificado (`email_verified=true`).
- Tener activada la opción de correo (`email_enabled=true`).
- Tener permisos para las funciones de alertas.

El resumen automático se programa a las `07:00` según `America/Bogota`.

## 7. Probar el envío

Desde la aplicación, activar las alertas de correo y ejecutar el resumen manual. También puede probarse con:

```bash
curl -X POST https://licitaia.centralspike.com/api/alerts/digest \
  -H "Authorization: Bearer TOKEN_DEL_USUARIO"
```

Revisar los logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=100 api worker beat
```

## 8. Errores frecuentes

- **535 Authentication failed**: se usó la contraseña normal; generar una contraseña de aplicación.
- **SMTP no configurado**: falta `SMTP_HOST` o el contenedor no fue recreado después de cambiar `.env`.
- **No llega el resumen**: revisar `email_verified`, `email_enabled` y la zona horaria.
- **El remitente no coincide**: hacer que `ALERTS_FROM_EMAIL` coincida con `SMTP_USER`.

## Seguridad

No subir `.env` al repositorio. Si una contraseña de aplicación se expone, revocarla inmediatamente desde la sección **Contraseñas de aplicaciones** de Google y generar otra.
